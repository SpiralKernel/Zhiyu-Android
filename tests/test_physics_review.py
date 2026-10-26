import copy
import json

import pytest

from app import bank, physics_review
from app.admin import validate_publish, Draft
from app.db import connect, initialize
from app.physics_review import ReviewItem, snapshot_hash, stage_batch
from app.question_annotation import source_fingerprint
from tests.test_physics_bank import physics, label


def record(q):
    annotation = label(q).annotation.model_dump()
    annotation['review'].update(method='item_read', issues=['teacher_answer_review_pending', 'curriculum_unknown'])
    annotation['parts'][0]['rubric'] = [{'id':'c1','description':'用I=U/R计算电流','evidence_required':'I=4V/2Ω=2A'}]
    form = Draft.model_validate({**q, 'annotation':annotation}).model_dump()
    return dict(question_id=q['id'], source_sha256=source_fingerprint(q), current_snapshot_id=q['id'],
                current_sha256=snapshot_hash(q), batch='B4', reviewer='gpt-6-luna',
                peer_reviewers=['independent AI review'], decision='repair_draft', quarantine_original=True,
                independent_solution=['I=U/R=4/2=2A'], remaining_issues=['人工验答案、课程范围待审'],
                rationale='来源题保留追踪，修复仅进候选草稿', proposed_form=form)


@pytest.fixture
def prepared(tmp_path):
    path=tmp_path/'db.sqlite3';initialize(path)
    with connect(path) as db:bank.import_records(db,'physics-test',[physics()],{})
    with connect(path) as db:q=json.loads(db.execute("SELECT data FROM bank_questions WHERE id='physics'").fetchone()[0])
    return path, record(q)


def test_stage_drafts_without_fake_human_review_and_is_idempotent(prepared):
    path, item=prepared
    with connect(path) as db:
        before=db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]
        assert stage_batch(db,[item])['drafts']==1
        assert db.execute('SELECT count(*) FROM bank_editor_items').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]==before
    with connect(path) as db:assert stage_batch(db,[item],dry_run=False)['drafts']==1
    with connect(path) as db:
        assert stage_batch(db,[item],dry_run=False)['already_applied']
        row=db.execute('SELECT source_id,data,state FROM bank_editor_items').fetchone()
        data=json.loads(row['data'])
        assert row['state']=='draft' and not data['ai_review']['human_approved']
        assert data['source']['status']=='quarantine' and not data['source']['can_practice']
        assert row['source_id']!='physics'  # binds the current quarantine snapshot
        assert data['form']['annotation']['review']['status']=='candidate'
        assert db.execute('SELECT count(*) FROM bank_editor_events').fetchone()[0]==0
        with pytest.raises(ValueError):validate_publish(Draft.model_validate(data['form']),data['source'])
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_late_invalid_snapshot_has_no_draft_or_question_writes(prepared):
    path,item=prepared;bad=copy.deepcopy(item);bad['question_id']='other';bad['current_sha256']='0'*64
    with connect(path) as db:
        before=db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]
        with pytest.raises(ValueError):stage_batch(db,[item,bad],dry_run=False)
        assert db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]==before
        assert db.execute('SELECT count(*) FROM bank_editor_items').fetchone()[0]==0


def test_failure_after_exclusion_rolls_back_whole_review(prepared,monkeypatch):
    path,item=prepared
    def fail(*args,**kwargs):raise RuntimeError('模拟最后审计写入失败')
    monkeypatch.setattr(physics_review,'audit',fail)
    with connect(path) as db:
        before=db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]
        with pytest.raises(RuntimeError):stage_batch(db,[item],dry_run=False)
        assert db.execute('SELECT count(*) FROM bank_questions').fetchone()[0]==before
        assert db.execute('SELECT count(*) FROM bank_editor_items').fetchone()[0]==0
        assert db.execute("SELECT status FROM bank_questions WHERE id='physics'").fetchone()[0]=='reference'


@pytest.mark.parametrize('change',['human','score','curriculum','missing_evidence'])
def test_proposals_cannot_invent_approval_scores_scope_or_empty_evidence(prepared,change):
    path,item=prepared;a=item['proposed_form']['annotation']
    if change=='human':a['review'].update(method='teacher',status='reviewed',answer_status='checked')
    if change=='score':a['parts'][0]['points']=1
    if change=='curriculum':item['proposed_form']['grade']=8
    if change=='missing_evidence':a['parts'][0]['rubric'][0]['evidence_required']=''
    with connect(path) as db:
        with pytest.raises(ValueError):stage_batch(db,[item],dry_run=False)
        assert db.execute('SELECT count(*) FROM bank_editor_items').fetchone()[0]==0


def test_different_payload_cannot_reuse_applied_batch(prepared):
    path,item=prepared
    with connect(path) as db:stage_batch(db,[item],dry_run=False)
    item['rationale']='修改后的批次'
    with connect(path) as db:
        with pytest.raises(ValueError,match='不同内容'):stage_batch(db,[item],dry_run=False)


def test_existing_manual_draft_is_never_overwritten(prepared):
    from app.db import dumps, now
    path,item=prepared;item['quarantine_original']=False
    with connect(path) as db:
        q=json.loads(db.execute("SELECT data FROM bank_questions WHERE id='physics'").fetchone()[0])
        payload=dumps({'source':q,'form':item['proposed_form'],'human_work':'keep exactly'})
        db.execute('INSERT INTO bank_editor_items VALUES(?,?,?,?,?,?,?,NULL,?)',
                   ('existing','bank','physics','original-hash',3,payload,'draft',now()))
    with connect(path) as db:
        result=stage_batch(db,[item],dry_run=False)
        assert result['drafts']==0 and result['existing_drafts_preserved']==1
        row=db.execute("SELECT revision,data FROM bank_editor_items WHERE id='existing'").fetchone()
        assert row['revision']==3 and row['data']==payload
