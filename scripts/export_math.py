"""导出七上标准题型地图及本机覆盖报告；只读数据库，不调用模型。"""
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.course_catalog import BOOK_MAP
from app.math_catalog import BOOK_ID,TYPES,VERSION
from app.math_learning import coverage


def render_map():
    lines=['# 七上数学题型地图','',f'版本：{VERSION}。{len(TYPES)}个标准题型，覆盖六个章节的起步能力结构。',
        '', '知识目标、具体题型、作答形式和难度分别记录。固定题型ID独立于来源标签；别名只做明确同义映射，不自动语义合并未知AI题型。目标由项目编写，尚未教师审定；地图不是全部教材细目的覆盖认证。',
        '', '原有26个模板题型映射与新增11类基础题共同覆盖37个标准编号的起步练习；未知AI新题型保留待审核来源。试卷识别可复用标准题型及别名，确认后才保留学习线索，不凑足可信独立题量。外部题库的知识标签不能直接证明某个细分题型已核对。','']
    for u in BOOK_MAP[BOOK_ID]['units']:
        lines += [f'## {u["name"]}','','| 标准ID | 题型 | 需要会什么 | 前置题型 |','| --- | --- | --- | --- |']
        for t in TYPES:
            if t['unit_id']==u['id']:
                lines.append(f'| `{t["id"]}` | {t["name"]} | {t["can_do"]} | {"、".join(t["prerequisites"]) or "—"} |')
        lines.append('')
    lines += ['## 当前练习与补强入口','','学生界面默认进入“AI老师”，另有“题库”；顶部提供学情报告与学习设置。题型地图和覆盖报告作为维护文档保留，不再提供单独的诊断导航。',
        '', '题库按当前学生与册次汇总细分题型，至少5道不同的独立核验题才能结合近期重复错误形成可靠的薄弱判断；自由答疑随时可用；不显示掌握百分比。辅助作答、AI讨论、照片评阅和未核验来源题保留记录，不凑足可信题量。规则见[学生流程](student-flow.md)。',
        '', 'AI老师支持知识提问、拍照问题与习题导入；对话自动更新带原话依据的题型学习线索。对话不增加独立核验题量，回题库完成新题后重算练习状态。',
        '', '## 维护入口','','- `app/math_catalog.py`：标准题型、别名、目标对应、前置关系。','- `app/study.py`：当前学生独立证据与练习状态。','- `app/teacher.py`、`app/observations.py`：自由答疑、题型与可纠正的学习线索。','- `app/reports.py`、`app/report_pdf.py`：家长报告、AI分析与中文PDF。','- `app/math_learning.py`：历史诊断业务与核验题覆盖，保留回归测试。','- `web/js/student.js`：当前两模式学生页面。',
        '- `scripts/export_math.py`：本文件与只读覆盖报告。','- `tests/test_student.py`、`scripts/browser_student.py`：当前业务与隔离浏览器验收。','',
        '历史诊断表`math_diagnostics`和`math_diagnostic_items`保留；schema9新增自由答疑、学习线索和报告缓存；schema8账号与旧讨论表保留，原作答仍在`attempts`。缓存、备份和学生数据不提交Git。','']
    return '\n'.join(lines)


def main():
    target=ROOT/'docs/math-type-map.md'
    text=render_map()
    if '--check' in sys.argv:
        if not target.exists() or target.read_text()!=text:
            raise SystemExit('数学题型地图与代码不一致，请重新导出')
        return
    target.write_text(text)
    path=ROOT/'data/ai-teacher.sqlite3'
    if path.exists():
        with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            db.create_function('current_student',0,lambda:'demo')
            data=coverage(db)
        lines=['# 七上数学题型覆盖报告','',f'题型版本：{VERSION}。按本机题库只读生成；不是学生成绩报告。','',
            f"共{data['summary']['types']}个标准题型，{data['summary']['with_verified_questions']}个有规则核验题，{data['summary']['diagnosable']}个可作基础/进阶诊断，{data['summary']['missing_verified']}个待补核验题。",'',data['note'],'',
            '| 题型 | 基础 | 进阶 | 挑战 | 关联目标外部候选（可重叠） | 状态 |','| --- | --- | --- | --- | --- | --- |']
        lines += [f"| {t['name']} | {t['difficulty_counts']['1']} | {t['difficulty_counts']['2']} | {t['difficulty_counts']['3']} | {t['candidate_goal_questions']} | {t['coverage_status']} |" for t in data['types']]
        lines += ['','## 新增基础题的实际覆盖','','每类包含以下3个子任务，按子任务补足6道未提交参数变式。数字变式不等于不同解法；概念题的最终答案核验也不能替代推理过程检查。','']
        for t in data['types']:
            if t['verified_structures']:
                lines.append(f"- {t['name']}：{'；'.join(t['verified_structures'])}。")
        lines += ['','展开图当前仅覆盖正方体，不包括全部立体图形；列代数式当前限单变量一次式，不覆盖分段、分式或多字母关系；整式概念暂不检查文字定义；近似数检查四舍五入及指定小数位数，尚不覆盖有效数字与误差界。','',
                  '## 后续补题','','优先为仅有挑战题的12类补对应起步题及不同解题结构，再扩充概念解释、几何图形和文字建模的过程评价。37类有题不等于37类已完整覆盖或教师审定。','']
        (ROOT/'docs/math-coverage.md').write_text('\n'.join(lines))
        print('已导出题型地图及本机覆盖报告（未写入数据库）。')


if __name__=='__main__':
    main()
