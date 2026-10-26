import copy
import json
from fractions import Fraction

import pytest

from app import bank
from app.courses import matched_goals
from app.db import connect, initialize
from app.math_quality import annotate, answer_check, curate, exact_value


def question(**changes):
    return {'id': 'bank:test:q', 'subject': 'math', 'stage': 'junior', 'grade': None, 'term': None,
            'stem': '计算：$(-2)-(-3)$的结果是（）', 'answer': 'A', 'kind': 'single_choice',
            'options': [{'key':'A','text':'1'}, {'key':'B','text':'-1'}], 'steps':['减去负数等于加上相反数。'],
            'knowledge_tags':['有理数的减法运算'], 'type_tags':['单选题'], 'tags_source':'source',
            'status':'ready', 'issues':[], 'difficulty':1, 'difficulty_raw':'容易',
            'provenance':{'dataset':'test','source_id':'q','url':'https://example.com','license':'test'}, **changes}


@pytest.mark.parametrize(('expression','expected'), [
    (r'\frac{-1}{2}+\frac{3}{4}', Fraction(1,4)),
    (r'1-{{(-1)}^{2}}+\frac{-1\times {{(-1)}^{3}}-2}{2\times (-1)+1}', 1),
    ('-3^2', -9), ('(-3)^2',9), ('0.1+0.2',Fraction(3,10)),
])
def test_fraction_arithmetic_is_exact(expression, expected):
    assert exact_value(expression) == expected


@pytest.mark.parametrize('expression', ["__import__('os')", 'open(1)', 'x+1', '2^100000', r'\sqrt{2}', '1/0', r'\frac{1}{2'])
def test_unsupported_and_executable_expressions_abstain(expression):
    with pytest.raises((ValueError, SyntaxError, ZeroDivisionError)):
        exact_value(expression)


def test_math_answer_contradiction_quarantined_without_rewriting_source():
    source = question(answer='B')
    old = copy.deepcopy(source)
    result = annotate(source)
    assert source == old
    assert result['status'] == 'quarantine'
    assert result['answer'] == 'B'
    assert result['quality']['answer_check']['computed'] == '1'
    assert result['knowledge_tags'] == old['knowledge_tags']
    assert result['difficulty'] == old['difficulty']
    assert result['quality']['classification_reviewed'] is False
    assert 'teacher_reviewed' not in result['provenance']


def test_answer_pass_is_not_a_teacher_or_classification_review():
    result = annotate(question())
    assert result['quality']['answer_check']['status'] == 'passed'
    assert result['quality']['tier'] == 'rule_checked'
    assert result['fine_type_annotations']
    assert all(a['needs_review'] for a in result['fine_type_annotations'])
    assert not result['quality']['solution_reviewed']


def test_system_checks_original_equations_not_rewritten_explanation():
    q = question(stem=r'求解：\begin{cases}3x-2y=5\\4x+y=13\end{cases}',
                 kind='reference', options=[], answer=r'\begin{cases}x=3\\y=1\end{cases}')
    result = answer_check(q)
    assert result['status']=='failed' and result['residuals']==['2','0']
    q['answer'] = 'x=31/11,y=19/11'
    assert answer_check(q)['status']=='partial_consistency'


def test_unknown_math_and_parameterized_answers_not_accepted_by_guessing():
    q = question(stem='证明以下结论并讨论所有情况。', answer='A')
    assert answer_check(q)['status']=='unchecked'
    q.update(stem=r'\begin{cases}x+y=2a\\x-y=1\end{cases}', kind='reference',answer='x=a+1/2,y=a-1/2')
    assert answer_check(q)['status']=='unchecked'


def test_scientific_notation_checks_coefficient_form_as_well_as_value():
    q = question(stem='数13000用科学记数法表示为（）', answer='B',options=[
        {'key':'A','text':r'$13\times10^3$'}, {'key':'B','text':r'$1.3\times10^4$'},
        {'key':'C','text':r'$0.13\times10^5$'}, {'key':'D','text':r'$130\times10^2$'}])
    assert answer_check(q)['status']=='passed'
    assert answer_check({**q,'answer':'A'})['status']=='failed'
    assert answer_check({**q,'stem':'数13000用科学记数法表示为（精确到千位）'})['status']=='unchecked'


def test_duplicate_options_and_answer_explanation_conflicts_require_review():
    q = question(stem='依据题意选择。', options=[{'key':'A','text':'1'},{'key':'B','text':'1'}])
    assert annotate(q)['status']=='quarantine'
    q = question(steps=['故答案为：B。'])
    assert 'solution_choice_conflict' in annotate(q)['issues']


def test_conflicting_answers_block_both_but_distinct_figures_are_not_merged():
    a = question(stem='根据条件求解。')
    b = question(id='bank:test:other', stem=a['stem'],answer='B')
    assert all(q['status']=='quarantine' for q in curate([a,b]))
    a.update(stem='如图选择。',has_missing_assets=True,source_images=['one.jpg'])
    b.update(stem=a['stem'],has_missing_assets=True,source_images=['two.jpg'])
    assert all(q['status']=='ready' for q in curate([a,b]))


def test_course_candidates_respect_source_grade_and_later_topics():
    q = annotate(question(grade=9,knowledge_tags=['抛物线与数轴'],stem='抛物线与x轴交点。'))
    assert all(gid.startswith('math-9-') for gid,_ in matched_goals(q))
    q = annotate(question(knowledge_tags=['有理数运算','二次函数','数轴']))
    assert not any(gid.startswith('math-7-') for gid,_ in matched_goals(q))
    q = annotate(question(grade=7,knowledge_tags=['算术'],stem='-2021的相反数是（）'))
    assert q['knowledge_tags']==['算术'] and q['derived_knowledge_tags']==['相反数']
    assert any(gid.startswith('math-7-1:') for gid,_ in matched_goals(q))
    q = annotate(question(grade=7, knowledge_tags=['绝对值','二元一次方程组']))
    assert q['term'] is None
    assert not any(gid.startswith('math-7-1:') for gid,_ in matched_goals(q))


def test_math_curation_keeps_other_subjects_and_multiselect_order_unchanged():
    a=question(subject='physics',answer='A')
    b=question(subject='physics',answer='B',id='bank:test:b')
    assert curate([a,b])==[a,b]
    a=question(kind='multiple_choice',answer='AB')
    b=question(kind='multiple_choice',answer='BA',id='bank:test:b')
    assert not any('conflicting_source_answers' in q['issues'] for q in curate([a,b]))


def test_quality_upgrade_is_idempotent_and_preserves_question_snapshot(tmp_path):
    path = tmp_path/'bank.sqlite3'
    initialize(path)
    with connect(path) as db:
        raw = question()
        bank.import_records(db,'test',[raw],{})
    with connect(path) as db:
        result = bank.import_records(db,'test',[annotate(raw)],{})
        assert result['inserted']==1
        versions = db.execute("SELECT id,data,status FROM bank_questions WHERE id LIKE 'bank:test:q%'").fetchall()
        assert len(versions)==2
        old = next(r for r in versions if r['id']=='bank:test:q')
        assert old['status']=='superseded' and json.loads(old['data'])['answer']=='A'
        assert 'quality' not in json.loads(old['data'])
    with connect(path) as db:
        result = bank.import_records(db,'test',[annotate(raw)],{})
        assert result['inserted']==0 and result['duplicates']==1
        current = json.loads(db.execute("SELECT data FROM bank_questions WHERE status!='superseded'").fetchone()[0])
        assert any(t['kind']=='type' and t['label']=='有理数的减法运算' for t in current['tags'])
        assert all(r[0] for r in db.execute("SELECT needs_review FROM bank_taxonomy WHERE origin IN ('source_derived','heuristic')"))


def test_distinct_image_questions_are_not_content_deduplicated(tmp_path):
    path=tmp_path/'bank.sqlite3'
    initialize(path)
    with connect(path) as db:
        a=question(stem='如图选择。',has_missing_assets=True,source_images=['a.jpg'])
        b=question(id='bank:test:b',stem=a['stem'],has_missing_assets=True,source_images=['b.jpg'])
        assert bank.import_records(db,'test',[a,b],{})['inserted']==2
        assert all(not json.loads(r[0])['can_practice'] for r in db.execute('SELECT data FROM bank_questions'))


def test_source_grade_correction_is_versioned_even_with_same_answer_and_rules(tmp_path):
    path=tmp_path/'bank.sqlite3'
    initialize(path)
    old=annotate(question(grade=7))
    corrected=annotate(question(grade=8))
    assert old['quality']==corrected['quality']
    with connect(path) as db:
        bank.import_records(db,'test',[old],{})
    with connect(path) as db:
        assert bank.import_records(db,'test',[corrected],{})['inserted']==1
        assert json.loads(db.execute("SELECT data FROM bank_questions WHERE status!='superseded'").fetchone()[0])['grade']==8
    with connect(path) as db:
        assert bank.import_records(db,'test',[corrected],{})['duplicates']==1


def test_missing_solution_or_fine_type_does_not_enter_practice_pool(tmp_path):
    path=tmp_path/'bank.sqlite3'
    initialize(path)
    with connect(path) as db:
        a=annotate(question(steps=[]))
        b=annotate(question(id='bank:test:b',stem='根据材料判断。',knowledge_tags=['度量几何学']))
        bank.import_records(db,'test',[a,b],{})
        assert all(not json.loads(r[0])['can_practice'] for r in db.execute('SELECT data FROM bank_questions'))
