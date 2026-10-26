"""Remove rejected source families while preserving referenced learning history."""
import json

from app.db import audit, dumps

REGISTRY_KEY = 'bank_pruned_content_v1'


def blocked_content(db):
    row = db.execute('SELECT value FROM content_meta WHERE key=?', (REGISTRY_KEY,)).fetchone()
    return {tuple(item) for item in json.loads(row[0])} if row else set()


def prune_sources(db, source_ids, *, subject, stage, batch_id):
    """Caller owns the transaction. Keep snapshots referenced by student/editor data.

    Compact content hashes prevent ordinary source reimports resurrecting removed
    questions. A changed stem/options/answer has a different hash and may be imported.
    Audit evidence files and source caches are not deleted.
    """
    from app.bank import content_hash

    if not db.in_transaction:
        raise ValueError('题库清理必须在事务中执行')
    roots = set(source_ids)
    rows = db.execute('SELECT id,data FROM bank_questions WHERE subject=? AND stage=?',
                      (subject, stage)).fetchall()
    targets = []
    for row in rows:
        q = json.loads(row['data'])
        if (q.get('annotation_source_question_id') or q['id']) in roots:
            targets.append((row['id'], q))
    protected = set()
    # These mappings can be rebuilt; all other declared references protect history.
    rebuildable = {'bank_question_tags', 'course_question_links', 'course_mapping_state'}
    for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        if table in rebuildable:
            continue
        quoted_table = '"' + table.replace('"', '""') + '"'
        for fk in db.execute(f'PRAGMA foreign_key_list({quoted_table})').fetchall():
            if fk['table'] == 'bank_questions':
                column = '"' + fk['from'].replace('"', '""') + '"'
                protected.update(r[0] for r in db.execute(f'SELECT {column} FROM {quoted_table}'))
    # Training references intentionally have no SQL foreign key.
    protected.update(r[0] for r in db.execute("SELECT question_id FROM training_items WHERE source='bank'"))
    protected.update(r[0] for r in db.execute("SELECT source_id FROM bank_editor_items WHERE source_kind='bank'"))
    registry = blocked_content(db)
    for _, q in targets:
        registry.add((q['subject'], content_hash(q)))
    db.execute('INSERT INTO content_meta(key,value) VALUES(?,?) '
               'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
               (REGISTRY_KEY, dumps(sorted(registry))))
    removed, retained = [], []
    for qid, q in targets:
        if qid in protected:
            q.update(status='superseded', can_practice=False, evidence_invalidated=True)
            db.execute("UPDATE bank_questions SET status='superseded',data=? WHERE id=?", (dumps(q), qid))
            retained.append(qid)
            continue
        for table in sorted(rebuildable):
            db.execute(f'DELETE FROM {table} WHERE question_id=?', (qid,))
        db.execute('DELETE FROM bank_questions WHERE id=?', (qid,))
        removed.append(qid)
    result = dict(batch_id=batch_id, subject=subject, stage=stage,
                  source_count=len(roots), deleted_snapshots=len(removed),
                  retained_history=retained, blocked_hashes=len(registry))
    audit(db, 'bank_sources_pruned', result)
    return result
