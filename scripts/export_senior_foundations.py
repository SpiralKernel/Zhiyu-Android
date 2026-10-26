"""Export the audited fine-skill inventory for maintainers, not textbook content."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.course_catalog import BOOKS,GOALS
from app.senior_foundations import audit_foundations


def render():
    report=audit_foundations(ROOT/'app/data')
    if not report['complete']:
        raise ValueError('基础题仍有审核或覆盖缺口，不能导出完成清单。')
    rows={s['id']:s for s in report['skills']}
    selected=report['selected']
    lines=['# 高中基础题型清单','',
        f"数学新增{selected.get('math',0)}题，物理新增{selected.get('physics',0)}题；共{len(rows)}项细技能，关联全部{len(report['goals'])}条项目教材目标。",
        '', '本清单由项目按本地教材范围拆分，经Luna初审与独立复核。每项至少两道不同任务；前置技能单列，不代替课程目标本身的覆盖。它是题库内容清单，不是学生掌握率，也不代表官方课标逐条认证。',
        '', '实验题覆盖纸面原理、步骤选择与数据解释，不能认证学生实际操作。新增原创题在来源中明确标记，模型审核仍不等于教师审核。',
        '', '维护入口与命令见[高中题库](senior-bank.md)。本文件由 `scripts/export_senior_foundations.py` 生成。','']
    for book in BOOKS:
        if book.get('stage')!='senior':continue
        subject=book['subject']
        catalog=json.loads((ROOT/f'app/data/senior_{subject}_foundation_skills.json').read_text())
        skills=[s for s in catalog['skills'] if s['book_id']==book['id']]
        lines += [f"## {book['title']}",'', '| 基础细项 | 课程目标 | 已复核题数 | 要求 |',
                  '| --- | --- | ---: | --- |']
        for skill in skills:
            name=skill['name']+('（前置）' if skill.get('role')=='prerequisite' else '')
            goals='；'.join(GOALS[g]['name'] for g in skill['goal_ids'])
            esc=lambda text:str(text).replace('|','／').replace('\n',' ')
            lines.append(f"| {esc(name)} | {esc(goals)} | {rows[skill['id']]['ready']} | {esc(skill['requirement'])} |")
        lines.append('')
    return '\n'.join(lines)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    path=ROOT/'docs/senior-foundations.md';expected=render()
    if args.check:
        if not path.exists() or path.read_text()!=expected:
            raise SystemExit('高中基础题清单与已审核数据不一致。')
    else:path.write_text(expected)
