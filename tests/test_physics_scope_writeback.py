import copy
import hashlib
import json

import pytest

from app import bank, courses
from app.db import connect, initialize
from app.physics_scope_review import record_hash
from app.physics_scope_writeback import apply_scope, payload_hash, preserve_scope
from app.question_annotation import source_fingerprint


@pytest.fixture
def bundle(tmp_path):
    dbpath = tmp_path / 'bank.sqlite3'
    initialize(dbpath)
    raw = dict(id='bank:scope:one', subject='physics', stage='junior', grade=None, term=None,
               stem='1米等于多少厘米？', kind='single_choice', status='ready',
               options=[{'key':'A','text':'100'},{'key':'B','text':'10'}], answer='A', steps=['单位换算。'],
               difficulty=1, knowledge_tags=['长度单位'], type_tags=['单选题'],
               quality={'annotation_schema_version':1}, provenance={'dataset':'scope-test','source_id':'one'})
    ann = dict(response_format='single_choice', difficulty={'level':1,'basis':'来源难度'},
               curriculum={'grade':None,'term':None,'scope_status':'unknown'}, fine_types=['旧题型'],
               answer_spec={'mode':'choice'}, parts=[{'id':'p1','prompt':'1米等于多少厘米？','reference_answer':'A'}],
               review={'status':'candidate','answer_status':'source_only','method':'item_read','issues':['curriculum_unknown']})
    from app.question_annotation import Annotation
    with connect(dbpath) as db:
        bank.import_records(db,'scope-test',[copy.deepcopy(raw)],{})
        q=json.loads(db.execute('SELECT data FROM bank_questions').fetchone()[0])
        q.update(annotation=Annotation.model_validate(ann).model_dump(),
                 annotation_source_question_id=raw['id'],annotation_source_sha256=source_fingerprint(raw))
        text=json.dumps(q,ensure_ascii=False)
        db.execute('UPDATE bank_questions SET data=? WHERE id=?',(text,q['id']))
    root=tmp_path/'evidence';root.mkdir()
    catalog={'version':'test-v1','types':{'ft:phys:c1:s1:concept':{'name':'长度单位辨析','goal_id':'physics-8-1:u1:g1','book_id':'physics-8-1'}}}
    (root/'catalog.json').write_text(json.dumps(catalog))
    source={'question_id':q['id'],'snapshot_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'question':{'stem':raw['stem']},'parts':[{'index':1,'prompt':raw['stem']}]}
    finding=dict(question_id=q['id'],snapshot_sha256=source['snapshot_sha256'],decision='aligned',
                 primary_book_id='physics-8-1',parts=[dict(index=1,type_ids=['ft:phys:c1:s1:concept'],
                 evidence_quote=raw['stem'],basis='按米与厘米的进位关系换算')],reason='长度单位换算属于八上',issues=[],
                 reviewer='/root/physics_scope_a',model='gpt-6-luna')
    peer=dict(question_id=q['id'],snapshot_sha256=source['snapshot_sha256'],primary_record_sha256=record_hash(finding),
              decision='accept',reason='核对原题与目录后认可长度单位换算归属',reviewer='/root/physics_scope_c',model='gpt-6-luna')
    pins={}
    for sh in 'abc':
        path=root/f'input-{sh}.jsonl';path.write_text(json.dumps(source)+'\n' if sh=='a' else '')
        pins[sh]=hashlib.sha256(path.read_bytes()).hexdigest()
        for phase in ['primary','peer']:(root/f'{phase}-{sh}').mkdir()
    (root/'primary-a/000.jsonl').write_text(json.dumps(finding)+'\n')
    (root/'peer-a/000.jsonl').write_text(json.dumps(peer)+'\n')
    (root/'adjudications.jsonl').write_text('')
    (root/'manifest.json').write_text(json.dumps({'total':1,'shards':{'a':1,'b':0,'c':0},'input_sha256':pins,
        'catalog_sha256':hashlib.sha256((root/'catalog.json').read_bytes()).hexdigest()}))
    return dbpath,root,raw,q


def test_apply_updates_scope_and_tags_without_promoting_answer_and_is_idempotent(bundle):
    path,root,raw,old=bundle
    with connect(path) as db:
        result=apply_scope(db,root)
        assert result['applied']==1
        q=json.loads(db.execute('SELECT data FROM bank_questions').fetchone()[0])
        assert q['curriculum_book_id']=='physics-8-1' and q['grade']==8
        assert q['annotation']['review']['status']=='candidate'
        assert q['annotation']['review']['answer_status']=='source_only'
        assert q['answer']==old['answer'] and q['steps']==old['steps']
        assert q['quality']['textbook_scope']['type_ids']==['ft:phys:c1:s1:concept']
        assert courses.matched_goals(q)[0][1]==['AI逐题核对候选']
        links=json.loads(db.execute('SELECT data FROM course_question_links').fetchone()[0])
        assert links['needs_review'] and links['method']=='model_reviewed_textbook_scope'
        assert apply_scope(db,root)['already_applied']==1
        # Repeat source import must retain the assignment, not create a stale replacement.
        imported=bank.import_records(db,'scope-test',[copy.deepcopy(raw)],{})
        assert imported['duplicates']==1
        current=json.loads(db.execute("SELECT data FROM bank_questions WHERE status!='superseded'").fetchone()[0])
        assert current['curriculum_book_id']=='physics-8-1'
        assert current['fine_type_annotations']==q['fine_type_annotations']


def test_drift_rejects_transaction_and_dry_run_leaves_database_unchanged(bundle):
    path,root,_,_=bundle
    with connect(path) as db:
        before=db.execute('SELECT data FROM bank_questions').fetchone()[0]
        assert apply_scope(db,root,dry_run=True)['would_apply']==1
        assert db.execute('SELECT data FROM bank_questions').fetchone()[0]==before
        q=json.loads(before);q['answer']='B'
        db.execute('UPDATE bank_questions SET data=?',(json.dumps(q),));db.commit()
        with pytest.raises(ValueError,match='来源快照'):
            apply_scope(db,root)
        assert not db.execute('SELECT 1 FROM audit_events WHERE kind=?',('physics_textbook_scope_writeback',)).fetchone()
        assert not json.loads(db.execute('SELECT data FROM bank_questions').fetchone()[0]).get('curriculum_book_id')


def test_tampered_saved_scope_not_carried(bundle):
    path,root,raw,_=bundle
    with connect(path) as db:
        apply_scope(db,root)
        q=json.loads(db.execute('SELECT data FROM bank_questions').fetchone()[0])
        assert payload_hash(q)==q['quality']['textbook_scope']['applied_payload_sha256']
        q['annotation']['parts'][0]['reference_answer']='B'
        assert not preserve_scope(copy.deepcopy(raw),q)


def test_late_sync_failure_rolls_back_question_and_tag_updates(bundle, monkeypatch):
    path,root,_,_=bundle
    with connect(path) as db:
        before=db.execute('SELECT data FROM bank_questions').fetchone()[0]
        tags=[tuple(r) for r in db.execute('SELECT * FROM bank_question_tags')]
        def fail(*args, **kwargs):
            raise RuntimeError('simulated mapping failure')
        monkeypatch.setattr(courses,'sync_questions',fail)
        with pytest.raises(RuntimeError,match='mapping failure'):
            apply_scope(db,root)
        assert db.execute('SELECT data FROM bank_questions').fetchone()[0]==before
        assert [tuple(r) for r in db.execute('SELECT * FROM bank_question_tags')]==tags


def test_held_records_are_not_written(bundle):
    path,root,_,_=bundle
    p=root/'primary-a/000.jsonl';f=json.loads(p.read_text())
    f.update(decision='hold',primary_book_id=None,issues=['目录暂缺类型'],reason='所需具体能力没有适用受控类型')
    p.write_text(json.dumps(f)+'\n');p=root/'peer-a/000.jsonl';peer=json.loads(p.read_text());peer['primary_record_sha256']=record_hash(f);p.write_text(json.dumps(peer)+'\n')
    with connect(path) as db:
        before=db.execute('SELECT data FROM bank_questions').fetchone()[0]
        r=apply_scope(db,root)
        assert r['held']==1 and r['applied']==0
        assert db.execute('SELECT data FROM bank_questions').fetchone()[0]==before
