import csv
import hashlib
import json

import pytest

from app import bank
from app.db import connect, initialize
from app.math_annotations import Entry, apply_batch
from app.physics_bank import ceval_records, curate
from app.question_annotation import Annotation, source_fingerprint


def physics(qid='physics'):
    return curate(dict(id=qid,subject='physics',stage='junior',grade=None,term=None,
        stem='电阻为2Ω，电压为4V，求电流。',kind='reference',options=[],answer='2A',steps=['I=U/R=2A'],
        difficulty=1,difficulty_raw='简单',knowledge_tags=['欧姆定律'],type_tags=['计算题'],
        status='reference',provenance={'dataset':'physics-test','source_id':qid}))


def label(q, pending=False):
    value=Annotation(response_format='calculation',difficulty={'level':1,'basis':'一次欧姆定律计算'},
        fine_types=['欧姆定律已知电压电阻求电流'],
        parts=[dict(id='whole',prompt=q['stem'],reference_answer='2A')],
        review={'issues':['fine_type_pending'] if pending else []})
    return Entry(question_id=q['id'],source_sha256=source_fingerprint(q),decision='annotate',reason='候选',annotation=value)


def test_physics_import_is_idempotent_preserves_math_and_pending_is_not_playable(tmp_path):
    path=tmp_path/'db.sqlite3';initialize(path)
    p=physics();m=physics('math');m.update(subject='math',provenance={'dataset':'math-test','source_id':'math'})
    with connect(path) as db:
        bank.import_records(db,'math-test',[m],{})
    with connect(path) as db:
        bank.import_records(db,'physics-test',[p],{})
    with connect(path) as db:
        before=db.execute("SELECT data FROM bank_questions WHERE subject='math'").fetchall()
        assert apply_batch(db,[label(p,True)],subject='physics')['annotated']==1
        assert apply_batch(db,[label(p,True)],subject='physics',dry_run=False)['annotated']==1
    with connect(path) as db:
        assert apply_batch(db,[label(p,True)],subject='physics',dry_run=False)['unchanged']==1
    with connect(path) as db:
        assert bank.import_records(db,'physics-test',[p],{})['duplicates']==1
        current=json.loads(db.execute("SELECT data FROM bank_questions WHERE subject='physics' AND status!='superseded'").fetchone()[0])
        assert not current['can_practice']
        assert current['annotation']['review']['status']=='candidate'
        assert [tuple(r) for r in db.execute("SELECT data FROM bank_questions WHERE subject='math'")] == [tuple(r) for r in before]
    with connect(path) as db:
        with pytest.raises(ValueError):apply_batch(db,[label(m)],subject='physics',dry_run=False)
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_physics_late_invalid_batch_rolls_back(tmp_path,monkeypatch):
    from app import math_annotations
    monkeypatch.setattr(math_annotations,'BATCH_SIZE',1)
    path=tmp_path/'db.sqlite3';initialize(path);q=physics()
    with connect(path) as db:bank.import_records(db,'physics-test',[q],{})
    with connect(path) as db:
        bad=label(q);bad.question_id='not-found'
        with pytest.raises(ValueError):apply_batch(db,[label(q),bad],subject='physics',dry_run=False)
        assert db.execute("SELECT count(*) FROM bank_questions WHERE subject='physics'").fetchone()[0]==1
        assert 'annotation' not in json.loads(db.execute("SELECT data FROM bank_questions WHERE id='physics'").fetchone()[0])


def test_excluding_an_already_pending_physics_annotation_survives_source_reimport(tmp_path):
    path=tmp_path/'db.sqlite3';initialize(path);q=physics()
    with connect(path) as db:bank.import_records(db,'physics-test',[q],{})
    with connect(path) as db:apply_batch(db,[label(q,True)],subject='physics',dry_run=False)
    excluded=Entry(question_id=q['id'],source_sha256=source_fingerprint(q),decision='exclude',
                   reason='独立复核发现来源条件冲突',annotation=None)
    with connect(path) as db:apply_batch(db,[excluded],subject='physics',dry_run=False)
    with connect(path) as db:
        assert bank.import_records(db,'physics-test',[physics()],{})['duplicates']==1
        current=json.loads(db.execute("SELECT data FROM bank_questions WHERE subject='physics' AND status!='superseded'").fetchone()[0])
        assert current['status']=='quarantine' and not current['can_practice']


def test_ceval_only_labeled_splits_and_hash_checked(tmp_path):
    files=[]
    for split in ('dev','val'):
        path=tmp_path/f'middle_school_physics_{split}.csv'
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['id','question','A','B','C','D','answer']);writer.writeheader()
            writer.writerow(dict(id=0,question='声音由什么产生？',A='振动',B='温度',C='电压',D='压强',answer='A'))
        files.append(dict(path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (tmp_path/'DOWNLOAD.json').write_text(json.dumps(dict(revision='a'*40,files=files)))
    (tmp_path/'middle_school_physics_test.csv').write_text('unlabeled test must not import')
    qs=list(ceval_records(tmp_path));assert len(qs)==2
    assert all(q['grade'] is None and q['term'] is None and q['answer']=='A' for q in qs)
    assert len({q['id'] for q in qs})==2
    assert all(q['quality']['answer_check']['status']=='not_checked' for q in qs)
    (tmp_path/'middle_school_physics_val.csv').write_text('tampered')
    with pytest.raises(ValueError,match='校验失败'):list(ceval_records(tmp_path))
