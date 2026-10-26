import json

import pytest

from app import bank
from app.bank_pruning import prune_sources
from app.db import connect, initialize, now
from tests.test_math_full_import import math


def test_prune_preserves_other_subject_and_blocks_source_resurrection(tmp_path):
    path = tmp_path / 'bank.sqlite3'
    initialize(path)
    bad = math('bad', answer='B')
    other = math('physics', subject='physics')
    with connect(path) as db:
        bank.import_records(db, 'test', [bad, other], {})
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        result = prune_sources(db, ['bad'], subject='math', stage='junior', batch_id='test')
        assert result['deleted_snapshots'] == 1
        assert db.execute("SELECT 1 FROM bank_questions WHERE id='physics'").fetchone()
        assert not db.execute("SELECT 1 FROM bank_questions WHERE id='bad'").fetchone()
        assert not db.execute("SELECT 1 FROM bank_question_tags WHERE question_id='bad'").fetchone()
    with connect(path) as db:
        # A different source ID cannot bypass the content decision either.
        r = bank.import_records(db, 'test', [bad, {**bad, 'id': 'renamed'}], {})
        assert r['inserted'] == 0 and r['pruned'] == 2
    with connect(path) as db:
        r = bank.import_records(db, 'test', [{**bad, 'answer': 'A'}], {})
        assert r['inserted'] == 1


def test_prune_keeps_referenced_attempt_snapshot_but_retires_evidence(tmp_path):
    path = tmp_path / 'bank.sqlite3'
    initialize(path)
    with connect(path) as db:
        bank.import_records(db, 'test', [math('bad')], {})
        db.execute('INSERT INTO students VALUES(?,?,?)', ('s', 'student', now()))
        db.execute('INSERT INTO bank_attempts(id,student_id,question_id,status,created_at) '
                   'VALUES(?,?,?,?,?)', ('attempt', 's', 'bad', 'assigned', now()))
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        r = prune_sources(db, ['bad'], subject='math', stage='junior', batch_id='test')
        assert r['retained_history'] == ['bad'] and r['deleted_snapshots'] == 0
        q = json.loads(db.execute("SELECT data FROM bank_questions WHERE id='bad'").fetchone()[0])
        assert q['status'] == 'superseded' and q['evidence_invalidated'] and not q['can_practice']
        assert db.execute("SELECT question_id FROM bank_attempts WHERE id='attempt'").fetchone()[0] == 'bad'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_prune_rolls_back_registry_and_deletions_together(tmp_path):
    path = tmp_path / 'bank.sqlite3'
    initialize(path)
    with connect(path) as db:
        bank.import_records(db, 'test', [math('bad')], {})
    with pytest.raises(RuntimeError), connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        prune_sources(db, ['bad'], subject='math', stage='junior', batch_id='test')
        raise RuntimeError('cancel transaction')
    with connect(path) as db:
        assert db.execute("SELECT 1 FROM bank_questions WHERE id='bad'").fetchone()
        assert not db.execute("SELECT 1 FROM content_meta WHERE key='bank_pruned_content_v1'").fetchone()
