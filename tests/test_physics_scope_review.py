import copy
import hashlib
import json

import pytest

from app.physics_scope_review import record_hash, validate_finding, validate_peer, inspect_batch


@pytest.fixture
def review():
    source = dict(question_id='p1',snapshot_sha256='a'*64,
                  question={'stem':'求该电阻的阻值并说明测量误差'},
                  parts=[{'index':1,'prompt':'求阻值'}, {'index':2,'prompt':'说明测量误差'}])
    catalog = {'types':{'ohm':{'book_id':'physics-9-1'}, 'measure':{'book_id':'physics-8-1'}}}
    raw = dict(question_id='p1',snapshot_sha256='a'*64,decision='aligned',primary_book_id='physics-9-1',
        parts=[dict(index=1,type_ids=['ohm'],evidence_quote='求阻值',basis='对应电阻定量求解'),
               dict(index=2,type_ids=['measure'],evidence_quote='测量误差',basis='分析测量操作误差')],
        reason='逐问选择受控目录已有题型',issues=[],reviewer='/root/physics_scope_a',model='gpt-6-luna')
    return source,catalog,raw


@pytest.mark.parametrize('change', ['stale','unknown','missing_part','future','fake_quote','unresolved','repeat'])
def test_rejects_invalid_scope_without_writing_bank(review, change):
    source,cat,raw=review
    if change=='stale':raw['snapshot_sha256']='b'*64
    elif change=='unknown':raw['parts'][0]['type_ids']=['invented']
    elif change=='missing_part':raw['parts'].pop()
    elif change=='future':raw['primary_book_id']='physics-8-1'
    elif change=='fake_quote':raw['parts'][0]['evidence_quote']='来源答案中的一句话'
    elif change=='unresolved':raw['issues']=['目录存在缺项']
    elif change=='repeat':raw['parts'][0]['type_ids']=['ohm','ohm']
    with pytest.raises(ValueError):validate_finding(raw,source,cat)


def test_hold_retains_each_question_part_and_explains_gap(review):
    source,cat,raw=review
    raw.update(decision='hold',primary_book_id=None,issues=['题型库缺少量程读数专项'])
    for p in raw['parts']:p['type_ids']=[]
    assert validate_finding(raw,source,cat).decision=='hold'


def test_peer_requires_different_author_current_hash_and_full_correction(review):
    source,cat,raw=review
    first=validate_finding(raw,source,cat)
    peer=dict(question_id='p1',snapshot_sha256='a'*64,primary_record_sha256=record_hash(first.model_dump()),
              decision='accept',reason='独立重新阅读原题后同意逐问归属',correction=None,
              reviewer='/root/physics_scope_c',model='gpt-6-luna')
    assert validate_peer(peer,first,source,cat).decision=='accept'
    for updates in ({'reviewer':first.reviewer},{'primary_record_sha256':'b'*64},{'decision':'revise'}):
        with pytest.raises(ValueError):validate_peer({**peer,**updates},first,source,cat)
    fix=copy.deepcopy(raw);fix['reviewer']=peer['reviewer']
    assert validate_peer({**peer,'decision':'revise','correction':fix},first,source,cat).correction


def test_checkpoint_binds_adjudication_without_faking_luna_authorship(tmp_path, review):
    source,cat,raw=review
    for phase in ('primary-a','peer-a'):(tmp_path/phase).mkdir()
    (tmp_path/'input-a.jsonl').write_text(json.dumps(source)+'\n')
    (tmp_path/'catalog.json').write_text(json.dumps(cat))
    pins={n:hashlib.sha256((tmp_path/n).read_bytes()).hexdigest() for n in ('input-a.jsonl','catalog.json')}
    (tmp_path/'manifest.json').write_text(json.dumps({'total':1,'shards':{'a':1},
        'catalog_sha256':pins['catalog.json'],'input_sha256':{'a':pins['input-a.jsonl']}}))
    (tmp_path/'primary-a/000.jsonl').write_text(json.dumps(raw)+'\n')
    first=validate_finding(raw,source,cat)
    peer=dict(question_id='p1',snapshot_sha256='a'*64,primary_record_sha256=record_hash(first.model_dump()),
        decision='accept',reason='独立核对后认可该归属',correction=None,reviewer='/root/physics_scope_c',model='gpt-6-luna')
    (tmp_path/'peer-a/000.jsonl').write_text(json.dumps(peer)+'\n')
    assert inspect_batch(tmp_path)['counts']['final_aligned']==1
    fixed=copy.deepcopy(raw);fixed.update(decision='hold',primary_book_id=None,issues=['需重新核对'],
        reason='主任务发现未解决条件',reviewer='/root',model='orchestrator')
    adjud=dict(question_id='p1',snapshot_sha256='a'*64,primary_record_sha256=record_hash(first.model_dump()),
        peer_record_sha256=record_hash(peer),reason='补充来源条件核对后留置',finding=fixed,reviewer='/root',model='orchestrator')
    path=tmp_path/'adjudications.jsonl';path.write_text(json.dumps(adjud)+'\n')
    assert inspect_batch(tmp_path)['counts']['final_hold']==1
    adjud['finding']['model']='gpt-6-luna'
    path.write_text(json.dumps(adjud)+'\n')
    with pytest.raises(ValueError):inspect_batch(tmp_path)


def test_checkpoint_accepts_plan_bound_deepseek_reviewers(tmp_path, review):
    source,cat,raw=review
    for phase in ('primary-a','peer-a'):(tmp_path/phase).mkdir()
    (tmp_path/'input-a.jsonl').write_text(json.dumps(source)+'\n')
    (tmp_path/'catalog.json').write_text(json.dumps(cat))
    pins={n:hashlib.sha256((tmp_path/n).read_bytes()).hexdigest() for n in ('input-a.jsonl','catalog.json')}
    (tmp_path/'manifest.json').write_text(json.dumps({'total':1,'shards':{'a':1},
        'catalog_sha256':pins['catalog.json'],'input_sha256':{'a':pins['input-a.jsonl']}}))
    model='opencode/deepseek-v4.1-flash-free'
    plan={'primary_unit_reviewers':{'a:000':'/root/deepseek_scope_a'},
          'primary_unit_models':{'a:000':model},
          'peer_unit_reviewers':{'a:000':'/root/deepseek_scope_c'},
          'peer_unit_models':{'a:000':model}}
    (tmp_path/'run-plan.json').write_text(json.dumps(plan))
    primary={**raw,'reviewer':'/root/deepseek_scope_a','model':model}
    (tmp_path/'primary-a/000.jsonl').write_text(json.dumps(primary)+'\n')
    first=validate_finding(primary,source,cat)
    peer=dict(question_id='p1',snapshot_sha256='a'*64,primary_record_sha256=record_hash(first.model_dump()),
        decision='accept',reason='独立核对后认可该归属',correction=None,
        reviewer='/root/deepseek_scope_c',model=model)
    (tmp_path/'peer-a/000.jsonl').write_text(json.dumps(peer)+'\n')
    result=inspect_batch(tmp_path)
    assert result['counts']['primary_done']==1
    assert result['counts']['peer_accept']==1
    with pytest.raises(ValueError):
        validate_peer({**peer,'model':'gpt-6-luna'},first,source,cat,expected_model=model)
