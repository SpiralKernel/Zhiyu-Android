"""Export reproducible, topic-ranked candidate inventory for senior high math.

Topic matching is only a screening aid. It never sets item_read or answer_checked.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.datasets import iter_dataset, source_manifest
from app.question_annotation import source_fingerprint

TOPICS = {
    "sets_logic": [r"集合", r"命题", r"充分条件", r"必要条件", r"量词"],
    "inequalities": [r"不等式", r"基本不等式", r"绝对值不等式"],
    "functions": [r"函数", r"单调性", r"奇偶性", r"零点", r"定义域", r"值域"],
    "exponential_logarithmic": [r"指数", r"对数", r"幂函数", r"\blog\b", r"\bln\b"],
    "trigonometry": [r"三角函数", r"正弦", r"余弦", r"正切", r"诱导公式", r"解三角形"],
    "plane_vectors": [r"平面向量", r"向量.*数量积", r"数量积", r"向量.*坐标"],
    "complex_numbers": [r"复数", r"虚部", r"实部", r"共轭复数", r"\bi\b.*复数"],
    "solid_geometry": [r"立体几何", r"三棱锥", r"四棱锥", r"直棱柱", r"球.*体积", r"空间几何体"],
    "spatial_vectors": [r"空间向量", r"法向量", r"空间直角坐标系", r"线面角", r"二面角"],
    "lines_circles": [r"直线与圆", r"圆的方程", r"直线.*圆", r"圆心", r"圆锥曲线"],
    "conics": [r"椭圆", r"双曲线", r"抛物线", r"圆锥曲线", r"焦点.*准线"],
    "statistics": [r"统计", r"频率分布", r"样本", r"茎叶图", r"中位数", r"方差"],
    "probability": [r"概率", r"随机事件", r"条件概率", r"独立事件", r"古典概型"],
    "counting_binomial": [r"排列", r"组合", r"二项式", r"\bC\(", r"\bA\("],
    "sequences": [r"数列", r"等差数列", r"等比数列", r"递推", r"前.?n.?项和"],
    "derivatives": [r"导数", r"切线", r"极值", r"最值", r"单调区间"],
    "distributions_regression": [r"正态分布", r"二项分布", r"超几何分布", r"回归方程", r"线性回归", r"相关系数"],
}
PATTERNS = {k: [re.compile(x, re.I) for x in values] for k, values in TOPICS.items()}


def screen(q: dict) -> dict:
    text = "\n".join([q.get("stem", ""), q.get("answer", ""), *q.get("steps", []),
                      *q.get("knowledge_tags", []), *q.get("type_tags", [])])
    matched = [topic for topic, patterns in PATTERNS.items() if any(p.search(text) for p in patterns)]
    # Rank only; all exclusions remain visible in the complete inventory.
    penalty = 0
    if q.get("has_missing_assets"):
        penalty += 100
    if not q.get("stem") or not q.get("answer"):
        penalty += 100
    if q.get("status") == "quarantine":
        penalty += 50
    score = (12 if q.get("steps") else 0) + (3 if q.get("options") else 4)
    score += min(len(q.get("stem", "")), 1400) // 300
    score -= penalty
    if re.search(r"(?:证明|求证|解答|求|计算|说明|\n\s*[（(]?[二三四123][）)、.、])", q.get("stem", "")):
        score += 5
    if not matched:
        matched = ["unclassified"]
    return {"topic_candidates": matched, "screen_score": score,
            "screen_reasons": ["source_analysis_present" if q.get("steps") else "no_source_analysis",
                               "has_options" if q.get("options") else "written_response_candidate",
                               *(["figure_or_image_marker"] if q.get("has_missing_assets") else []),
                               *(["source_quarantine"] if q.get("status") == "quarantine" else [])]}


def export(source_root: Path, out_dir: Path) -> dict:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite review basis: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {name: source_manifest(source_root, name) for name in ("cmm", "gaokao")}
    all_rows = []
    seen = set()
    for dataset in ("cmm", "gaokao"):
        for q in iter_dataset(source_root, dataset):
            if q["subject"] != "math" or q["stage"] != "senior":
                continue
            if q["id"] in seen:
                raise ValueError(f"duplicate source id: {q['id']}")
            seen.add(q["id"])
            all_rows.append({"question_id": q["id"], "source_sha256": source_fingerprint(q),
                             "provenance": q["provenance"], "question": q, **screen(q)})
    with (out_dir / "candidates.jsonl").open("x", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    by_topic = {}
    for topic in (*TOPICS, "unclassified"):
        rows = [r for r in all_rows if topic in r["topic_candidates"]]
        rows.sort(key=lambda r: (-r["screen_score"], r["question_id"]))
        by_topic[topic] = [{"question_id": r["question_id"], "source_sha256": r["source_sha256"],
                            "score": r["screen_score"], "status": r["question"]["status"],
                            "response_kind": r["question"]["kind"], "has_analysis": bool(r["question"]["steps"]),
                            "topic_candidates": r["topic_candidates"], "screen_reasons": r["screen_reasons"]}
                           for r in rows]
    (out_dir / "topic_candidates.json").write_text(json.dumps(by_topic, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = Counter(topic for r in all_rows for topic in r["topic_candidates"])
    summary = {"batch_id": "senior-20261015-math", "inventory_count": len(all_rows),
               "source_counts": dict(Counter(r["question_id"].split(":")[1] for r in all_rows)),
               "topic_candidate_counts": dict(counts), "all_questions_reviewed": False,
               "note": "Topic ranking is heuristic; it does not imply item_read or answer_checked."}
    (out_dir / "screen_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT / "data/sources")
    parser.add_argument("--out", type=Path, default=ROOT / "data/annotations/senior-20261015/math")
    args = parser.parse_args()
    print(json.dumps(export(args.source_root, args.out), ensure_ascii=False, indent=2))
