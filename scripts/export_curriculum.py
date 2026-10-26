"""从运行时课程目录导出供人工检查的基础文档，不联网。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.bank import SUBJECTS
from app.course_catalog import BOOKS, GOALS, STAGE_OUTCOMES, UNITS, VERSION


def render():
    junior_books = [b for b in BOOKS if b.get('stage','junior')=='junior']
    junior_units = [u for b in junior_books for u in b['units']]
    lines = ["# 初中学段与学习阶段要求", "", f"版本：{VERSION}。{len(junior_books)} 个学习阶段，{len(junior_units)} 个单元，{sum(len(u['goals']) for u in junior_units)} 项目标。", "",
        "包含语文、数学、英语、物理、化学、生物、历史、地理、道德与法治、科学、信息技术；按用户要求不含体音美。科学与分科理化生可按学校实际选用，不要求同时学习两套课程。", "",
        "## 使用边界", "",
        "教育部2022年版课标规定学段方向，不能直接当作每个学期的教学进度。本目录的目标、检查表现和前置关系由项目整理，尚未教师审定，也不是逐条覆盖全部课标的认证清单。", "",
        "已核对数学七上、七下、八上、八下，以及物理八上、八下、九年级全一册的用户提供PDF目录（文件内版次年份未确认），以及人教社公开语文八下（2025）、英语九上（2026）目录。物理九年级前半/后半是全一册的建议进度，不是两本独立教材。九下数学PDF目录另行保存，其章节安排与当前建议进度不同，尚未切换。其余学期和单元拆分是项目建议。信息科技九年级为可选复习/项目安排，并非统一开课要求。", "",
        "题库通过来源知识标签建立候选目标映射，保留来源年级/学期空值，不把映射反写为官方教材标签。候选题可能跨阶段或未覆盖整个目标，需要内容复核；无候选题表示待补题，无作答表示待诊断。", "",
        "练习表现只摘要可追溯的有效作答；实验、朗读、听说、项目作品和行为表现需要相应任务与观察，不能仅用选择题判断掌握。", "",
        "## 页面与AI使用", "",
        "在全科题库选择学习阶段、当前单元；勾选‘仅练当前学习范围’后，手动与AI选题均限制到候选映射范围。阶段和单元按科目保存。辅导、模型选题与大题评阅会收到目标、检查表现、前置知识及练习证据摘要。超出当前范围的题应解释所需前置知识；不能把后续内容假定为已学。", "",
        "[来源核对清单](../app/data/curriculum_sources.json)记录官方附件地址、缓存指纹和已检查页码（PDF页从1计）。只将自编目标和来源元数据纳入仓库，不附带整本教材或课标副本。", ""]
    for subject, name in SUBJECTS.items():
        lines += [f"## {name}", "", "贯穿初中阶段的方向（不代表当前学期已学）：", ""]
        lines += [f"- {text}" for text in STAGE_OUTCOMES[subject]]
        lines.append("")
        for book in (b for b in junior_books if b["subject"] == subject):
            lines += [f"### {book['grade']}年级{'上' if book['term'] == 1 else '下'} · {book['id']}", "", book["edition"], "", book["scope_note"], ""]
            for unit in book["units"]:
                lines += [f"#### {unit['name']}", ""]
                for goal in unit["goals"]:
                    lines += [f"- **{goal['name']}**（`{goal['id']}`）：{goal['can_do']}",
                              f"  - 检查表现：{'；'.join(goal['checks'])}"]
                    if goal["prerequisites"]:
                        lines += [f"  - 前置知识：{'、'.join(goal['prerequisites'])}"]
                    if goal["practical"]:
                        lines += ["  - 需要实际任务或观察，纸笔练习仅提供部分证据。"]
                lines.append("")
            lines += ["依据：" + "、".join(f"[{s['title']}]({s['url']})" if s.get("url") else s["title"] for s in book["sources"]), ""]
    lines += ["## 更新", "", "编辑 `app/course_catalog.py`（物理目标为 `app/data/physics_curriculum.json`）并递增版本，运行本导出脚本；启动时按版本及题目知识标签重建候选映射，新增入库题增量映射。人工核对的册次须在来源清单中记录版本和目录页。物理PDF指纹与核对信息见 `app/data/physics_textbook_reviews.json`。原有数学模板地图见 [原地图范围](curriculum.md)。", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    target = ROOT / "docs/junior-curriculum.md"
    content = render()
    if "--check" in sys.argv:
        if not target.exists() or target.read_text() != content:
            raise SystemExit("课程文档与运行时目录不一致，请重新导出")
    else:
        target.write_text(content)
        print(f"已导出 {target}")
