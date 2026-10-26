"""Full junior physics textbook requirements and controlled task definitions.

Only authored requirements and source metadata are shipped, never PDF contents.
Lexical alignment is a maintenance candidate, not approved curriculum scope.
"""
import copy
import json
import unicodedata
from pathlib import Path

DATA = json.loads((Path(__file__).parent / 'data/physics_textbook_catalog.json').read_text())
VERSION = DATA['version']
MODES = {
    'concept': ('概念辨析与现象解释', '说明判断所用的物理条件和证据。'),
    'calculation': ('定量建模与计算', '列出对应物理量、适用公式、代入、单位及结果检验。'),
    'drawing': ('作图与图示分析', '标明对象、方向与对应关系，不能仅凭图形外观判断。'),
    'experiment': ('实验设计与数据分析', '交代变量、操作、数据、误差与可支持的结论；不认证实际操作。'),
    'practice': ('实践方案与证据评价', '按目标、方案、记录、评价与改进分别给出证据；不认证实物完成。'),
}


def requirements(book_id):
    for book in DATA['books']:
        if book_id in book['internal_book_ids']:
            chapters = [copy.deepcopy(c) for c in book['chapters'] if c['book_id'] == book_id]
            return dict(version=VERSION, physical_book_id=book['id'],
                        source_sha256=book['sha256'], term_split=book['term_split'],
                        chapters=chapters,
                        introduction=copy.deepcopy(DATA['introduction']) if book_id == 'physics-8-1' else None,
                        guidance='逐节要求由项目改写；目录与页码已核对，不表示全文或难度已审定。'
                                 '九年级学期边界为项目建议。实践必须有过程证据，不能用书面分数代替操作表现。')
    return None


def types_for_book(book_id):
    req = requirements(book_id)
    if not req:
        return []
    result = []
    for chapter in req['chapters']:
        for section in chapter['sections']:
            for mode in section['modes']:
                suffix, check = MODES[mode]
                result.append(dict(id=f"ft:{section['id']}:{mode}", name=section['name']+'：'+suffix,
                    can_do=section['can_do']+'；'+check+'；'+'；'.join(section['checks']),
                    goal_id=chapter['goal_id'], unit_id=chapter['goal_id'].rsplit(':', 1)[0],
                    book_id=book_id, section_id=section['id'], aliases=section['aliases']))
    return result


def normalize(text):
    return ''.join(unicodedata.normalize('NFKC', str(text)).split()).casefold()


def alignment_candidates(question):
    """Scan all volumes; never infer correctness, confidence scores or mastery.

    Labels are stronger evidence than stem mentions. No matching on answers or
    solutions. A mention can still be incidental, so even a unique hit stays a
    candidate and never changes the stored grade/term.
    """
    if question.get('subject') != 'physics' or question.get('stage') != 'junior':
        return []
    ann = question.get('annotation') or {}
    labels = list(question.get('knowledge_tags', [])) + list(question.get('derived_knowledge_tags', []))
    labels += list(ann.get('fine_types', []))
    for kind in ('primary', 'supporting'):
        labels += ann.get('knowledge', {}).get(kind, [])
    labels = [normalize(x) for x in labels]
    stem = normalize(question.get('stem', ''))
    hits = []
    for book in DATA['books']:
        for chapter in book['chapters']:
            for section in chapter['sections']:
                evidence = []
                for alias in section['aliases']:
                    key = normalize(alias)
                    if key in labels:
                        evidence.append(dict(alias=alias, field='label_exact'))
                    elif len(key) >= 2 and any(key in x for x in labels):
                        evidence.append(dict(alias=alias, field='label_phrase'))
                    elif len(key) >= 3 and key in stem:
                        evidence.append(dict(alias=alias, field='stem_phrase'))
                if evidence:
                    hits.append(dict(section_id=section['id'], book_id=chapter['book_id'],
                        physical_book_id=book['id'], goal_id=chapter['goal_id'], evidence=evidence,
                        status='lexical_candidate', source_sha256=book['sha256']))
    return hits
