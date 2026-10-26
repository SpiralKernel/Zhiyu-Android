"""Apply source-pinned scope candidates without certifying answers or mastery."""
import copy
import hashlib
import json
from pathlib import Path

from app.physics_scope_review import ScopeAdjudication, ScopeFinding, inspect_batch, record_hash, validate_finding
from app.question_annotation import source_fingerprint, validate_for_question

SCOPE_FIELDS = ('grade', 'term', 'curriculum_book_id', 'curriculum_goal_ids',
                'curriculum_minimum_grade', 'curriculum_minimum_book',
                'annotation', 'fine_type_annotations')


def payload_hash(q):
    fields = (*SCOPE_FIELDS, 'id', 'subject', 'stage', 'stem', 'options', 'answer',
              'steps', 'status', 'can_practice', 'knowledge_tags', 'type_tags')
    return record_hash({k: q.get(k) for k in fields})


def preserve_scope(incoming, saved):
    """Called only after the importer's original-source fingerprint check."""
    if saved.get('subject') != 'physics' or saved.get('stage') != 'junior':
        return False
    stamp = saved.get('quality', {}).get('textbook_scope', {})
    if not stamp or stamp.get('applied_payload_sha256') != payload_hash(saved):
        return False
    for field in SCOPE_FIELDS:
        if field in saved:
            incoming[field] = copy.deepcopy(saved[field])
    incoming.setdefault('quality', {})['textbook_scope'] = copy.deepcopy(stamp)
    return True


def resolved_findings(directory):
    root = Path(directory)
    report = inspect_batch(root)
    if report['pending_revisions'] or report['counts']['primary_done'] != report['counts']['peer_done']:
        raise ValueError('存在未完成双轮审核或未裁定分歧，不回写')
    def pinned(name):
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != report['file_sha256'].get(name):
            raise ValueError('校验后审核证据发生变化：' + name)
        return data.decode()

    catalog = json.loads(pinned('catalog.json'))
    sources = {}
    findings = {}
    for shard in 'abc':
        sources.update({x['question_id']: x for x in map(json.loads, pinned(f'input-{shard}.jsonl').splitlines())})
        for path in (root / f'primary-{shard}').glob('*.jsonl'):
            for line in pinned(str(path.relative_to(root))).splitlines():
                item = ScopeFinding.model_validate_json(line)
                findings[item.question_id] = item
    for line in pinned('adjudications.jsonl').splitlines():
        item = ScopeAdjudication.model_validate_json(line)
        findings[item.question_id] = item.finding
    for item in findings.values():
        validate_finding(item.model_dump(), sources[item.question_id], catalog)
    if len(findings) != report['counts']['peer_done']:
        raise ValueError('已校验题目集合发生变化')
    return catalog, sources, findings, report


def annotated_question(q, finding, catalog, catalog_hash):
    from app.course_catalog import BOOK_MAP
    result = copy.deepcopy(q)
    book = BOOK_MAP[finding.primary_book_id]
    types = list(dict.fromkeys(t for p in finding.parts for t in p.type_ids))
    goals = list(dict.fromkeys(catalog['types'][t]['goal_id'] for t in types
                               if catalog['types'][t]['book_id'] == finding.primary_book_id))
    result.update(grade=book['grade'], term=book['term'], curriculum_book_id=finding.primary_book_id,
                  curriculum_goal_ids=goals, curriculum_minimum_grade=book['grade'],
                  curriculum_minimum_book=finding.primary_book_id)
    annotation = result.get('annotation')
    if not annotation:
        raise ValueError('缺少既有逐问标注，不凭册次批注生成答案')
    if len(annotation['parts']) != len(finding.parts):
        raise ValueError('既有标注小问数量变化')
    annotation['fine_types'] = [catalog['types'][t]['name'] for t in types]
    annotation['curriculum'].update(grade=book['grade'], term=book['term'], book_id=finding.primary_book_id,
                                    goal_ids=goals, scope_status='candidate',
                                    basis='来源双轮册次与受控题型批注；仅模型候选，非答案或难度认证')
    for part, scope in zip(annotation['parts'], finding.parts):
        part['type_tags'] = [catalog['types'][t]['name'] for t in scope.type_ids]
    annotation['review']['issues'] = [i for i in annotation['review']['issues'] if i != 'curriculum_unknown']
    # Replace only prior fine-type labels, preserving original form/knowledge tags.
    result['fine_type_annotations'] = [dict(id=t, label=catalog['types'][t]['name'], origin='model_review',
                                          basis='source_pinned_textbook_scope', needs_review=True) for t in types]
    stamp = dict(status='model_reviewed_candidate', catalog_version=catalog['version'],
                 catalog_sha256=catalog_hash, source_snapshot_sha256=finding.snapshot_sha256,
                 source_fingerprint=source_fingerprint(q), finding_sha256=record_hash(finding.model_dump()),
                 finding=finding.model_dump(), type_ids=types,
                 previous_fine_types=q['annotation'].get('fine_types', []),
                 previous_part_type_tags=[p.get('type_tags', []) for p in q['annotation']['parts']],
                 dependency_goal_ids=list(dict.fromkeys(catalog['types'][t]['goal_id'] for t in types)),
                 answer_certified=False, difficulty_calibrated=False, human_reviewed=False)
    result.setdefault('quality', {})['textbook_scope'] = stamp
    validate_for_question(annotation, result)
    stamp['applied_payload_sha256'] = payload_hash(result)
    return result


def apply_scope(db, directory, *, dry_run=False):
    """One transaction; fail on any source drift; caller must back up first."""
    from app.bank import register_tag
    from app.courses import sync_questions
    catalog, sources, findings, report = resolved_findings(directory)
    catalog_hash = report['file_sha256']['catalog.json']
    changes, skipped = [], 0
    db.execute('BEGIN IMMEDIATE')
    try:
        for qid, finding in findings.items():
            if finding.decision != 'aligned':
                continue
            raw = db.execute('SELECT data FROM bank_questions WHERE id=?', (qid,)).fetchone()
            if not raw:
                raise ValueError('来源题不存在：' + qid)
            q = json.loads(raw[0])
            stamp = q.get('quality', {}).get('textbook_scope', {})
            if (stamp.get('finding_sha256') == record_hash(finding.model_dump())
                    and stamp.get('catalog_sha256') == catalog_hash
                    and stamp.get('applied_payload_sha256') == payload_hash(q)):
                skipped += 1
                continue
            if hashlib.sha256(raw[0].encode()).hexdigest() != sources[qid]['snapshot_sha256']:
                raise ValueError('来源快照已变化，整批不写入：' + qid)
            if q.get('subject') != 'physics' or q.get('stage') != 'junior' or not q.get('can_practice'):
                raise ValueError('来源已退出可练范围：' + qid)
            changes.append((q, annotated_question(q, finding, catalog, catalog_hash)))
        for old, q in changes:
            prior = {x['label'] for x in old.get('fine_type_annotations', [])}
            q['tags'] = [t for t in q.get('tags', []) if not (t['kind'] == 'type' and t['label'] in prior
                         and t.get('origin') in {'luna', 'model_review', 'ai'})]
            for item in q['fine_type_annotations']:
                tid = register_tag(db, 'physics', 'junior', 'type', item['label'], 'model_review')
                if not any(t['id'] == tid for t in q['tags']):
                    q['tags'].append(dict(id=tid, kind='type', label=item['label'], origin='model_review'))
            db.execute('UPDATE bank_questions SET data=? WHERE id=?', (json.dumps(q, ensure_ascii=False), q['id']))
            db.execute('DELETE FROM bank_question_tags WHERE question_id=?', (q['id'],))
            db.executemany('INSERT INTO bank_question_tags VALUES(?,?)', [(q['id'], t['id']) for t in q['tags']])
        sync_questions(db, [q['id'] for _, q in changes], force=True)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('外键检查失败')
        from app.db import audit
        audit(db, 'physics_textbook_scope_writeback', dict(applied=len(changes), already_applied=skipped,
              source_reviewed=len(findings), catalog_sha256=catalog_hash,
              adjudications_sha256=report['file_sha256']['adjudications.jsonl']))
        db.rollback() if dry_run else db.commit()
    except Exception:
        db.rollback()
        raise
    return dict(applied=0 if dry_run else len(changes), would_apply=len(changes), dry_run=dry_run, already_applied=skipped,
                held=sum(f.decision == 'hold' for f in findings.values()),
                source_reviewed=len(findings), changes_student_state=False,
                questions=[dict(question_id=q['id'], before_sha256=sources[q['id']]['snapshot_sha256'],
                                after_sha256=hashlib.sha256(json.dumps(q, ensure_ascii=False).encode()).hexdigest()) for old, q in changes])
