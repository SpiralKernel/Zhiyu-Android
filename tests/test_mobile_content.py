import copy,json,sqlite3
from pathlib import Path
import pytest
from app.db import initialize,connect
from app import bank,mobile_content
from scripts.build_mobile_content import build


def source(qid):
    return {'id':qid,'subject':'math','stage':'junior','grade':7,'term':1,'stem':'求1+1的值。','options':[{'key':'A','text':'2'},{'key':'B','text':'3'}],
            'kind':'single_choice','status':'ready','answer':'A','steps':['1+1=2'],'difficulty':1,'knowledge_tags':['有理数加法'],'type_tags':['加法'],
            'tags_source':'source','provenance':{'dataset':'mobile-test','source_id':qid}}


def test_signed_mobile_seed_has_only_content_and_preserves_learner_state(tmp_path,monkeypatch):
    src=tmp_path/'src.sqlite3';dst=tmp_path/'dst.sqlite3';initialize(src);initialize(dst)
    with connect(src) as db:bank.import_records(db,'mobile-test',[source('signed-q')],{})
    out=tmp_path/'release';pub=tmp_path/'public.pem'
    manifest=build(src,out,1,tmp_path/'private.pem',pub);monkeypatch.setattr(mobile_content,'PUBLIC_KEY',pub)
    raw=(out/'bank-1.jsonl.gz').read_bytes()
    import gzip
    rows=[json.loads(s) for s in gzip.decompress(raw).splitlines()]
    assert {r['kind'] for r in rows}<={'source','tag','question','retired'}
    with connect(dst) as db:
        before=[tuple(r) for r in db.execute('select * from students')]
        result=mobile_content.install(db,raw,manifest)
        assert result['count']==1 and result['updated']
        assert [tuple(r) for r in db.execute('select * from students')]==before
        q=json.loads(db.execute("select data from bank_questions where id='signed-q'").fetchone()[0])
        assert q['answer']=='A' and q['quality']['mobile_release']['version']==1
        assert mobile_content.install(db,raw,manifest)['updated'] is False
        assert mobile_content.installed(db)==1
    bad=copy.deepcopy(manifest);bad['version']=2
    with connect(dst) as db:
        with pytest.raises(Exception):mobile_content.install(db,raw,bad)
        assert mobile_content.installed(db)==1
    with connect(dst) as db:
        with pytest.raises(ValueError):mobile_content.install(db,raw+b'bad',manifest)
        assert mobile_content.installed(db)==1
