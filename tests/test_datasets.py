import csv
import json
from pathlib import Path

import pytest

import app.datasets as datasets
from app.datasets import iter_dataset, source_manifest


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def test_cmm_source_grade_conservative_option_repair_and_missing_figures(tmp_path):
    row = {'id':'1','question':'-3的绝对值是（）','answer':'C','options':'-3\nB. -1/3\nC. 3\nD. 1/3',
           'analysis':'绝对值是距离。','image':[],'level':'七年级','subject':'算术'}
    _write_jsonl(tmp_path/'cmm/train_data.jsonl', [row,
        {**row,'id':'2','image':['a.jpg']}, {**row,'id':'3','options':'A. -3\nC. 3\nD. 1/3'},
        {**row,'id':'4','level':'高二'}, {**row,'id':'5','level':'未知年级'},
        {**row,'id':'6','answer':'null'}, {**row,'id':'7','image':[],'question':'如图选择<ImageHere>'}])
    qs=list(iter_dataset(tmp_path,'cmm'))
    assert qs[0]['grade']==7 and qs[0]['term'] is None
    assert qs[0]['stage']=='junior' and qs[0]['status']=='ready'
    assert qs[0]['format_repairs']==['restored_missing_first_option_label']
    assert qs[0]['options'][0]=={'key':'A','text':'-3'}
    assert qs[1]['has_missing_assets'] and qs[1]['source_images']==['a.jpg']
    assert qs[1]['status']=='reference' and qs[2]['status']=='quarantine'
    assert qs[3]['stage']=='senior' and qs[4]['stage']=='unknown'
    assert qs[5]['status']=='quarantine' and qs[6]['has_missing_assets']
    assert source_manifest(tmp_path,'cmm')['count']==7


def test_tal_adapter_maps_explicit_stage_and_keeps_invalid_image_quarantined(tmp_path):
    root = tmp_path / "tal"
    sample = {
        "dataset_name": "junior_math_competition", "queId": "stable-1", "difficulty": "2",
        "problem": "选出正确答案。", "answer_option_list": [[
            {"aoVal": "A", "content": "甲"}, {"aoVal": "B", "content": "乙"},
        ]], "answer_value": "B", "knowledge_point_routes": ["代数->方程"],
        "answer_analysis": ["解题步骤"],
    }
    bad_image = {**sample, "queId": "bad-image", "problem": "如图所示，求值。", "answer_value": ""}
    _write_jsonl(root / "TAL-SCQ5K-CN" / "train.jsonl", [sample, bad_image])
    (root / "README.md").write_text("TAL source README", encoding="utf-8")

    rows = list(iter_dataset(root, "tal"))
    assert rows[0]["id"] == "bank:tal:stable-1"
    assert rows[0]["stage"] == "junior"
    assert rows[0]["grade"] is rows[0]["term"] is None
    assert rows[0]["answer"] == "B" and rows[0]["knowledge_tags"] == ["代数->方程"]
    assert rows[0]["provenance"]["url"] == "https://huggingface.co/datasets/math-eval/TAL-SCQ5K"
    assert rows[1]["status"] == "quarantine"
    assert rows[1]["has_missing_assets"] is True
    assert "image_or_figure_requires_asset_review" in rows[1]["issues"]
    manifest = source_manifest(root, "tal")
    assert manifest["count"] == 2
    assert manifest["metadata_files"][0]["source_file"] == "README.md"


def test_tal_luna_annotations_only_fill_empty_source_tags_and_require_matching_hash(tmp_path, monkeypatch):
    stem = "数列问题？"
    digest = datasets.hashlib.sha256(stem.encode("utf-8")).hexdigest()
    monkeypatch.setattr(datasets, "_tal_annotation_data", lambda: {
        "annotation_model": "gpt-6-luna",
        "annotation_model_note": "Luna-authored fallback.",
        "annotations": {
            "qid-empty": {"knowledge_tags": ["数列"], "type_tags": ["数列计数"],
                          "origin": "luna", "annotation_model": "gpt-6-luna", "question_sha256": digest},
            "qid-source": {"knowledge_tags": ["wrong"], "type_tags": ["wrong"],
                           "origin": "luna", "question_sha256": digest},
            "qid-stale": {"knowledge_tags": ["stale"], "type_tags": ["stale"],
                          "origin": "luna", "question_sha256": "0" * 64},
        },
    })
    common = {"dataset_name": "mid_math_competition", "difficulty": "1",
              "problem": stem, "answer_option_list": [[
                  {"aoVal": "A", "content": "一"}, {"aoVal": "B", "content": "二"},
              ]], "answer_value": "A"}
    rows = [
        {**common, "qid": "qid-empty"},
        {**common, "qid": "qid-source", "knowledge_point_routes": ["来源知识点"]},
        {**common, "qid": "qid-stale"},
    ]
    _write_jsonl(tmp_path / "TAL-SCQ5K-CN" / "train.jsonl", rows)
    converted = list(iter_dataset(tmp_path, "tal"))
    assert converted[0]["knowledge_tags"] == ["数列"]
    assert converted[0]["type_tags"] == ["数列计数"]
    assert converted[0]["annotation_origin"] == "luna"
    assert converted[0]["annotation_model"] == "gpt-6-luna"
    assert converted[1]["knowledge_tags"] == ["来源知识点"]
    assert converted[1]["type_tags"] == ["competition_math", "single_choice"]
    assert "annotation_origin" not in converted[1]
    assert converted[2]["knowledge_tags"] == []
    assert "annotation_origin" not in converted[2]


def test_gaokao_adapter_has_senior_stage_preserves_written_answer_and_strict_answer_parse(tmp_path):
    root = tmp_path / "gaokao"
    objective = {"year": "2020", "category": "甲卷", "index": 0,
                 "question": "Which option is correct?\nA. first\nB. second",
                 "answer": ["B"], "analysis": "Because B."}
    bad_image = {"year": "2020", "category": "甲卷", "index": 1,
                 "question": "如图所示，选正确答案 A. one B. two", "answer": [], "analysis": ""}
    subjective = {"year": "2020", "category": "甲卷", "index": 2,
                  "question": "Explain why.", "answer": "The answer is not A; it is a written response.",
                  "analysis": "Reference explanation."}
    objective_path = root / "Data" / "Objective_Questions" / "2020_Physics_MCQs.json"
    subjective_path = root / "Data" / "Subjective_Questions" / "2020_Physics_Open-ended_Questions.json"
    objective_path.parent.mkdir(parents=True)
    subjective_path.parent.mkdir(parents=True)
    objective_path.write_text(json.dumps({"example": [objective, bad_image]}, ensure_ascii=False), encoding="utf-8")
    subjective_path.write_text(json.dumps({"example": [subjective]}, ensure_ascii=False), encoding="utf-8")

    rows = list(iter_dataset(root, "gaokao"))
    assert rows[0]["stage"] == "senior"
    assert rows[0]["status"] == "ready" and rows[0]["answer"] == "B"
    assert rows[1]["status"] == "quarantine" and rows[1]["has_missing_assets"] is True
    assert rows[2]["status"] == "reference"
    assert rows[2]["answer"] == "The answer is not A; it is a written response."


def test_cjeval_adapter_deduplicates_and_derives_types_from_source_knowledge(tmp_path):
    root = tmp_path / "cjeval"
    base = root / "data" / "CJEval_data"
    choice = {"subject": "初中数学", "ques_type": "单选题", "ques_difficulty": "容易",
              "ques_content": "题目？选项: A. 甲 B. 乙", "ques_answer": ["B"],
              "ques_analyze": "解析", "ques_knowledges": ["代数->一次方程", "方程应用"]}
    written = {"subject": "初中数学", "ques_type": "问答题", "ques_difficulty": "一般",
               "ques_content": "如图求解 x。", "ques_answer": ["x=2"],
               "ques_analyze": "步骤", "ques_knowledges": ["一次方程"]}
    _write_jsonl(base / "train" / "train_初中数学.json", [choice, written])
    _write_jsonl(base / "test" / "test_初中数学.json", [choice])

    rows = list(iter_dataset(root, "cjeval"))
    assert len(rows) == 2
    mc = next(row for row in rows if row["kind"] == "single_choice")
    assert mc["stage"] == "junior" and mc["knowledge_tags"] == choice["ques_knowledges"]
    assert mc["type_tags"] == ["单选题"]
    assert mc["derived_type_tags"] == ["单选题 · 一次方程", "单选题 · 方程应用"]
    essay = next(row for row in rows if row["kind"] == "reference")
    assert essay["status"] == "reference" and essay["answer_mode"] == "choice"
    assert essay["has_missing_assets"] is True
    assert source_manifest(root, "cjeval")["unique_count"] == 2


def test_ceval_annotations_and_split_qualified_ids(tmp_path):
    root = tmp_path / "ceval"
    root.mkdir()
    annotation = {"annotation_model": "Luna", "annotation_model_note": "Review suggested tags.",
                  "annotations": {"dev/middle_school_politics_dev.csv:0": {
                      "knowledge_tags": ["资源地区分布"], "type_tags": ["单项选择题", "材料分析"], "origin": "luna"}}}
    (root / "annotations.json").write_text(json.dumps(annotation, ensure_ascii=False), encoding="utf-8")
    for split in ("dev", "val", "test"):
        folder = root / split
        folder.mkdir(parents=True)
        path = folder / f"middle_school_politics_{split}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "question", "A", "B", "C", "D", "answer", "explanation"])
            writer.writeheader()
            writer.writerow({"id": "0", "question": "材料表明？", "A": "甲", "B": "乙",
                             "C": "丙", "D": "丁", "answer": "B", "explanation": "因为乙。"})
    rows = list(iter_dataset(root, "ceval"))
    assert [row["id"] for row in rows] == ["bank:ceval:dev:0", "bank:ceval:val:0"]
    assert rows[0]["knowledge_tags"] == ["资源地区分布"]
    assert rows[0]["annotation_origin"] == "luna"
    assert rows[0]["annotation_model"] == "Luna"
    assert rows[0]["annotation_model_note"] == "Review suggested tags."
    assert rows[1]["knowledge_tags"] == []
    assert source_manifest(root, "ceval")["unique_count"] == 2


def test_real_cjeval_count_when_source_is_available():
    root = Path(__file__).resolve().parents[1] / "data" / "sources" / "cjeval"
    if not (root / "data" / "CJEval_data").is_dir():
        pytest.skip("local CJEval source data is optional")
    assert len(list(iter_dataset(root, "cjeval"))) == 26136


@pytest.mark.parametrize(("dataset", "count"), [("tal", 5000), ("gaokao", 2811), ("ceval", 26)])
def test_real_optional_corpora_when_source_is_available(dataset, count):
    root = Path(__file__).resolve().parents[1] / "data" / "sources"
    try:
        manifest = source_manifest(root, dataset)
    except FileNotFoundError:
        pytest.skip(f"local {dataset} source data is optional")
    assert manifest["count"] == count


def test_grouped_reading_choices_use_written_review(tmp_path):
    path=tmp_path/'cjeval/data/CJEval_data/train/train_初中英语.json'
    row={"ques_type":"单选题","ques_content":"Read the passage. 1. choose A. first B. second C. third D. fourth 2. choose A. one B. two C. three D. four", "ques_answer":["A","A"],"ques_knowledges":["阅读理解"]}
    _write_jsonl(path,[row])
    converted=list(iter_dataset(tmp_path,'cjeval'))[0]
    assert converted['kind']=='reference' and converted['answer_mode']=='written'
    assert converted['answer']=='A\nA'
    assert 'grouped_subquestions_written_review' in converted['issues']
