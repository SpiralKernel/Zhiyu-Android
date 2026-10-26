"""新题型的数学边界、表示要求、持久化及当前学生入口回归。"""
import copy
import json
from decimal import Decimal
from fractions import Fraction as F

import pytest
from fastapi.testclient import TestClient

from app.answers import equivalent, linear_expression
from app.config import Settings
from app.db import connect, initialize
from app.foundations import CATALOG, folded_normals, make_foundation
from app.main import create_app
from app.math_learning import verified_pool
from app.questions import grade, public_question, validate_question


@pytest.mark.parametrize('key', CATALOG)
def test_generated_subtasks_reject_mutated_answers(key):
    structures=set()
    for index in range(150):
        q=make_foundation(key,index)
        structures.add(q['provenance']['structure'])
        assert validate_question(q) and grade(q,q['answer'])['correct']
        bad=copy.deepcopy(q)
        if q['answer_mode']=='expression':bad['answer']='('+q['answer']+')+1'
        elif q['answer_mode']=='scientific':bad['answer']=q['answer'].rsplit('^',1)[0]+'^'+str(q['parameters']['exponent']+1)
        elif q['answer_mode']=='decimal':bad['answer']=format(Decimal(q['answer'])+1,f".{q['parameters']['places']}f")
        else:bad['answer']=str(F(q['answer'])+1)
        assert not validate_question(bad)
        assert not grade(q,bad['answer'])['correct']
        assert not {'answer','steps','hint','parameters'} & public_question(q).keys()
    assert structures==set(CATALOG[key][1])


@pytest.mark.parametrize('text,expected', [('3x+2',(3,2)),('2*(x+1)',(2,2)),
    ('(x+1)/2',(F(1,2),F(1,2))),('0.1x+0.2',(F(1,10),F(1,5))),('－2x＋4',(-2,4))])
def test_linear_equivalence_is_exact(text,expected):
    assert linear_expression(text)==expected


@pytest.mark.parametrize('text', ['x*x','1/x','x**100000000','2**100000000',
    '__import__("os")','x.__class__','[x for x in []]','1/0','y+1','2e10*x','1<<10000'])
def test_expression_parser_rejects_non_linear_and_executable_input(text):
    with pytest.raises(ValueError):linear_expression(text)


def test_representation_matters_for_scientific_and_approximate_answers():
    q=make_foundation('scientific',0)
    assert grade(q,q['answer'].replace('×10^','e'))['correct']
    value=q['parameters']['value']
    non_normal=f"{F(q['parameters']['coefficient'])*10}×10^{q['parameters']['exponent']-1}"
    assert not grade(q,non_normal)['correct']
    with pytest.raises(ValueError):grade(q,value)
    decimal={'answer_mode':'decimal','answer':'1.20','provenance':{'family':'foundations'},'steps':[],'rubric':{}}
    assert grade(decimal,'1.20')['correct']
    assert not grade(decimal,'1.2')['correct']
    assert not grade(decimal,'1.200')['correct']
    # 商/余数校验覆盖负数及跨整数进位，不能通过二进制浮点round判定。
    for index in (1,2,4,5,7,8):assert validate_question(make_foundation('approximate',index))


def test_cube_net_geometry_matches_known_opposite_faces_and_hexomino_count():
    cross=((0,1),(1,0),(1,1),(1,2),(1,3),(2,1))
    normals=folded_normals(cross)
    assert normals[(0,1)]==tuple(-n for n in normals[(2,1)])
    assert normals[(1,0)]==tuple(-n for n in normals[(1,2)])
    assert normals[(1,1)]==tuple(-n for n in normals[(1,3)])
    assert folded_normals(((0,0),(0,1),(0,2),(1,0),(1,1),(1,2))) is None
    assert folded_normals(((0,0),(1,0),(2,0),(3,0),(4,0),(8,0))) is None

    # 独立枚举所有自由六连方；旋转/镜像合并后35种，其中11种可折成立方体。
    def canonical(cells):
        forms=[]
        for flip in (-1,1):
            for rotation in range(4):
                transformed=[]
                for x,y in cells:
                    x*=flip
                    for _ in range(rotation):x,y=-y,x
                    transformed.append((x,y))
                dx=min(x for x,y in transformed);dy=min(y for x,y in transformed)
                forms.append(tuple(sorted((x-dx,y-dy) for x,y in transformed)))
        return min(forms)
    shapes={((0,0),)}
    for _ in range(5):
        shapes={canonical(set(cells)|{(x+dx,y+dy)}) for cells in shapes for x,y in cells
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)) if (x+dx,y+dy) not in cells}
    assert len(shapes)==35
    assert sum(folded_normals(shape) is not None for shape in shapes)==11
    for index in range(12):
        q=make_foundation('geometry',index)
        assert [(c['x'],c['y']) for c in q['diagram']['cells']]==list(q['parameters']['cells'])


def test_new_types_work_with_login_report_retries_hints_and_stage_isolation(tmp_path):
    settings=Settings(database_path=tmp_path/'learning.sqlite3',deepseek_api_key='',_env_file=None)
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/v1/auth/register',json={'username':'student','password':'local-test-123','grade':7,'term':1}).status_code==201
        for key in CATALOG:
            response=client.post('/api/v1/study/next',json={'type_id':'m7a:'+key,'allow_challenge':False})
            assert response.status_code==200,response.text
            attempt=response.json();public=attempt['question']
            assert not {'answer','parameters','steps'} & public.keys()
            with connect(settings.database_path) as db:
                q=json.loads(db.execute('SELECT data FROM questions WHERE id=?',(public['id'],)).fetchone()[0])
            url=f"/api/v1/attempts/{attempt['attempt_id']}/answer"
            answer=q['answer']
            if key=='expression-model':answer=f"({q['answer']})+0"
            result=client.post(url,json={'answer':answer})
            assert result.status_code==200 and result.json()['correct'],result.text
            assert client.post(url,json={'answer':q['answer']}).json()==result.json()
        state=client.get('/api/v1/study/home').json()
        assert all(next(t for t in state['types'] if t['id']=='m7a:'+key)['independent_count']==1 for key in CATALOG)
        report=client.get('/api/v1/reports').json()
        assert report['summary']['independent']==len(CATALOG)
        from app.courses import evidence
        with connect(settings.database_path) as db:
            # 首次注册学生为demo；维护接口的目标映射也须使用科学记数法目标，而非乘方锚点。
            mapped=evidence(db,'math')
            assert any(e['types']==['m7a:scientific'] for e in mapped['math-7-1:u2:g4'])
            assert not any(e['types']==['m7a:scientific'] for e in mapped['math-7-1:u2:g3'])
        snapshot={}
        with connect(settings.database_path) as db:
            snapshot=dict(db.execute('SELECT id,data FROM questions'))
        initialize(settings.database_path)
        with connect(settings.database_path) as db:
            assert dict(db.execute('SELECT id,data FROM questions'))==snapshot
            assert all(len(verified_pool(db)['m7a:'+key])>=18 for key in CATALOG)
        attempt=client.post('/api/v1/study/next',json={'type_id':'m7a:expression-model'}).json()
        assert client.post(f"/api/v1/attempts/{attempt['attempt_id']}/hint").status_code==200
        with connect(settings.database_path) as db:q=json.loads(db.execute('SELECT data FROM questions WHERE id=?',(attempt['question']['id'],)).fetchone()[0])
        result=client.post(f"/api/v1/attempts/{attempt['attempt_id']}/answer",json={'answer':q['answer']})
        assert result.json()['assisted']
        assert client.get('/api/v1/reports').json()['summary']['independent']==len(CATALOG)
        client.post('/api/v1/auth/stage',json={'grade':8,'term':1})
        assert client.post('/api/v1/study/next',json={'type_id':'m7a:geometry'}).status_code in (403,404)
        assert client.get('/api/v1/reports').json()['summary']['independent']==0
