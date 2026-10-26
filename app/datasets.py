"""Pure adapters for the locally cached public question bank sources."""

from __future__ import annotations

import hashlib
import json
import re
import csv
from pathlib import Path
from typing import Any, Iterator
from functools import lru_cache

TAL_URL = "https://huggingface.co/datasets/math-eval/TAL-SCQ5K"
GAOKAO_URL = "https://github.com/OpenLMLab/GAOKAO-Bench"
CMM_URL = "https://huggingface.co/datasets/ecnu-icalk/cmm-math"
SUBJECTS = {
    "math", "physics", "chemistry", "biology", "chinese", "english",
    "history", "geography", "politics", "science", "information",
}

_SUBJECT_FILE = (
    ("Math", "math"), ("Physics", "physics"), ("Chemistry", "chemistry"),
    ("Biology", "biology"), ("Chinese", "chinese"), ("English", "english"),
    ("History", "history"), ("Geography", "geography"),
    ("Political_Science", "politics"),
)
_OPTION_MARK = re.compile(r"(?<![A-Za-z])([A-H])\s*[.．、:：)]\s*")
_IMAGE_MARK = re.compile(r"如图|如下图|见图|图示|图中|图片|下图|<img\b|!\[|\.(?:png|jpe?g|gif|svg|webp)(?:\b|$)", re.I)


def _dataset_dir(root: Path, dataset: str) -> Path:
    root = Path(root)
    if dataset not in {"tal", "gaokao", "cjeval", "ceval", "cmm"}:
        raise ValueError("unsupported dataset")
    candidates = (root / dataset, root)
    for candidate in candidates:
        if dataset == "tal" and (candidate / "TAL-SCQ5K-CN").is_dir():
            return candidate
        if dataset == "gaokao" and (candidate / "Data").is_dir():
            return candidate
        if dataset == "cjeval" and (candidate / "data" / "CJEval_data").is_dir():
            return candidate
        if dataset == "cmm" and (candidate / "train_data.jsonl").is_file():
            return candidate
        if dataset == "ceval" and any(candidate.glob("*/middle_school_politics*.csv")):
            return candidate
    # Also accept data/sources as root where directories may be named normally.
    raise FileNotFoundError(f"Could not find {dataset} source under {root}")


def _files(root: Path, dataset: str) -> list[Path]:
    folder = _dataset_dir(root, dataset)
    if dataset == "tal":
        base = folder / "TAL-SCQ5K-CN"
        return [p for p in (base / "train.jsonl", base / "test.jsonl") if p.is_file()]
    if dataset == "gaokao":
        return sorted((folder / "Data").rglob("*.json"))
    if dataset == "cjeval":
        return sorted((folder / "data" / "CJEval_data").rglob("*.json"))
    if dataset == "cmm":
        return [p for p in (folder / "train_data.jsonl", folder / "test_data.jsonl") if p.is_file()]
    return sorted(p for p in folder.rglob("*.csv") if "middle_school_politics" in p.name.lower() and any(x in p.parts for x in ("dev", "val")))


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(_text(v) for v in value if v is not None).strip()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _answer_letters(value: Any) -> str:
    values = value if isinstance(value, list) else [value]
    answer = []
    for value in values:
        raw = _text(value).upper()
        raw = re.sub(r"^(?:答案|ANSWER)\s*[:：]?\s*", "", raw, flags=re.I).strip()
        # Accept only a compact sequence of option tokens, never letters found
        # inside an explanation or an English sentence.
        if re.fullmatch(r"[A-H](?:[\s,，、/|;；]*[A-H])*", raw):
            answer.extend(re.findall(r"[A-H]", raw))
    return "".join(dict.fromkeys(answer))


def _options_from_tal(raw: Any) -> list[dict[str, str]]:
    options = []
    for group in raw or []:
        items = group if isinstance(group, list) else [group]
        for item in items:
            if not isinstance(item, dict):
                continue
            key = _text(item.get("aoVal")).upper()
            text = _text(item.get("content"))
            if key and text:
                options.append({"key": key, "text": text})
    return options


def _options_from_text(stem: str) -> tuple[str, list[dict[str, str]]]:
    all_marks = list(_OPTION_MARK.finditer(stem))
    if len(all_marks) < 2:
        return stem.strip(), []
    intro = re.search(r"(?:选项|options?)\s*[:：]?", stem, re.I)
    candidates = [i for i, mark in enumerate(all_marks)
                  if mark.group(1) == "A" and (intro is None or mark.start() >= intro.end())]
    if not candidates:
        return stem.strip(), []

    best: list[re.Match[str]] = []
    for start in candidates:
        sequence = []
        expected = ord("A")
        for mark in all_marks[start:]:
            if mark.group(1) != chr(expected):
                break
            sequence.append(mark)
            expected += 1
        if len(sequence) > len(best):
            best = sequence
    if len(best) < 2 or best[0].start() < max(0, len(stem) - 2500):
        return stem.strip(), []
    chunks = []
    for i, match in enumerate(best):
        end = best[i + 1].start() if i + 1 < len(best) else len(stem)
        body = stem[match.end():end].strip()
        if body:
            chunks.append({"key": match.group(1), "text": body})
    if len(chunks) >= 2 and all(len(x["text"]) < 2000 for x in chunks):
        return stem[:best[0].start()].rstrip(), chunks
    return stem.strip(), []


def _base(*, id_: str, subject: str, stem: str, answer: str, steps: list[str],
          difficulty: int, difficulty_raw: Any, tags: list[str], type_tags: list[str],
          tags_source: str, source_tags: list[str], status: str, issues: list[str],
          source_id: str, source_file: str, url: str, license_: str,
          options: list[dict[str, str]] | None = None, kind: str = "reference") -> dict[str, Any]:
    return {
        "id": id_, "subject": subject, "stage": "unknown", "grade": None,
        "term": None, "stem": stem, "options": options or [], "answer": answer,
        "kind": kind, "steps": steps, "difficulty": difficulty,
        "difficulty_raw": difficulty_raw, "knowledge_tags": tags,
        "type_tags": type_tags, "tags_source": tags_source,
        "source_tags": source_tags, "status": status, "issues": issues,
        "provenance": {"dataset": id_.split(":", 2)[1],
                       "source_id": source_id, "url": url, "license": license_,
                       "source_file": source_file},
    }


def _tal_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


@lru_cache(maxsize=1)
def _tal_annotation_data() -> dict[str, Any]:
    path = Path(__file__).parent / "data" / "tal_annotations.json"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _tal_record(row: dict[str, Any], path: Path) -> dict[str, Any]:
    source_id = _text(row.get("queId") or row.get("qid"))
    if not source_id:
        source_id = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    stem = _text(row.get("problem"))
    options = _options_from_tal(row.get("answer_option_list"))
    answer = _answer_letters(row.get("answer_value"))
    issues: list[str] = []
    status = "ready"
    if not answer:
        issues.append("missing_answer")
    if len(options) < 2 or len({x["key"] for x in options}) != len(options):
        issues.append("invalid_options")
    elif answer and not set(answer).issubset({x["key"] for x in options}):
        issues.append("answer_not_in_options")
    if issues:
        status = "quarantine"
    has_missing_assets = bool(_IMAGE_MARK.search(stem) or _IMAGE_MARK.search(json.dumps(row.get("competition_source_list", []), ensure_ascii=False)))
    if has_missing_assets:
        issues.append("image_or_figure_requires_asset_review")
        if status != "quarantine":
            status = "reference"
    raw_diff = row.get("difficulty")
    try:
        difficulty = max(1, min(3, int(raw_diff) + 1))
    except (TypeError, ValueError):
        difficulty = 2
    source_tags = [*_as_list(row.get("dataset_name")), *_as_list(row.get("competition_source_list")), *_as_list(row.get("knowledge_point_routes"))]
    route_tags = [_text(x) for x in _as_list(row.get("knowledge_point_routes")) if _text(x)]
    type_tags = ["competition_math", "single_choice"]
    annotation: dict[str, Any] = {}
    annotation_data = _tal_annotation_data()
    if not route_tags:
        candidate = annotation_data.get("annotations", {}).get(source_id, {})
        question_hash = hashlib.sha256(stem.encode("utf-8")).hexdigest()
        if candidate and candidate.get("question_sha256") == question_hash:
            annotation = candidate
            route_tags = [_text(x) for x in candidate.get("knowledge_tags", []) if _text(x)]
            type_tags = [_text(x) for x in candidate.get("type_tags", []) if _text(x)] or type_tags
    steps = [_text(x) for x in _as_list(row.get("answer_analysis")) if _text(x)]
    stage = "unknown"
    joined_tags = " ".join(source_tags)
    if re.search(r"小学|小学生|primary", joined_tags, re.I):
        stage = "primary"
    elif re.search(r"初中|初中生|junior\s*high", joined_tags, re.I):
        stage = "junior"
    elif re.search(r"高中|高中生|senior\s*high", joined_tags, re.I):
        stage = "senior"
    dataset_name = _text(row.get("dataset_name")).lower()
    if "prime_math" in dataset_name:
        stage = "primary"
    elif "junior_math" in dataset_name or "mid_math" in dataset_name:
        stage = "junior"
    elif "high_math" in dataset_name:
        stage = "senior"
    record = _base(id_=f"bank:tal:{source_id}", subject="math", stem=stem,
                   answer=answer, steps=steps, difficulty=difficulty, difficulty_raw=raw_diff,
                   tags=route_tags, type_tags=type_tags,
                   tags_source="luna" if annotation else "source", source_tags=source_tags, status=status,
                   issues=issues, source_id=source_id, source_file=path.name,
                   url=TAL_URL, license_="MIT", options=options, kind="single_choice")
    record["stage"] = stage
    record["has_missing_assets"] = has_missing_assets
    if annotation:
        record["annotation_origin"] = annotation.get("origin")
        record["annotation_model"] = annotation.get("annotation_model") or annotation_data.get("annotation_model")
        record["annotation_model_note"] = annotation_data.get("annotation_model_note")
        record["question_sha256"] = annotation.get("question_sha256")
    return record


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _gaokao_subject(path: Path) -> str:
    for marker, subject in _SUBJECT_FILE:
        if marker.lower() in path.name.lower():
            return subject
    return "chinese" if "Chinese" in path.name else "english"


def _gaokao_knowledge(subject: str, stem: str) -> list[str]:
    # Only emit narrow tags when an unambiguous domain term occurs.
    rules = {
        "math": [("数列", "数列"), ("导数", "导数"), ("概率", "概率"), ("函数", "函数"), ("向量", "向量"), ("集合", "集合"), ("圆锥曲线", "圆锥曲线")],
        "physics": [("牛顿定律", "牛顿定律"), ("电磁感应", "电磁感应"), ("动量", "动量"), ("原子核", "原子核"), ("电场", "电场")],
        "chemistry": [("氧化还原", "氧化还原"), ("化学平衡", "化学平衡"), ("离子方程式", "离子方程式"), ("有机", "有机化学")],
        "biology": [("细胞", "细胞"), ("遗传", "遗传"), ("生态", "生态"), ("免疫", "免疫")],
        "history": [("改革开放", "改革开放"), ("分封制", "分封制"), ("工业革命", "工业革命")],
        "geography": [("沙尘暴", "沙尘暴"), ("气候", "气候"), ("地震", "地震"), ("洋流", "洋流")],
        "politics": [("市场经济", "市场经济"), ("政府职能", "政府职能"), ("劳动生产率", "劳动生产率")],
        "chinese": [("文言文", "文言文阅读"), ("古诗", "古诗阅读"), ("成语", "词语运用")],
        "english": [("阅读理解", "阅读理解"), ("短文改错", "短文改错"), ("完形填空", "完形填空")],
    }
    return list(dict.fromkeys(tag for token, tag in rules.get(subject, []) if token in stem))


def _gaokao_records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    examples = payload.get("example", []) if isinstance(payload, dict) else payload
    if not isinstance(examples, list):
        return
    subject = _gaokao_subject(path)
    subjective = "Subjective_Questions" in path.parts or any(x in path.name.lower() for x in ("open-ended", "fill-in-the-blank", "error_correction", "cloze_passage"))
    file_type = "subjective" if subjective else "objective"
    for ordinal, row in enumerate(examples):
        if not isinstance(row, dict):
            continue
        question = _text(row.get("question"))
        source_id = f"{row.get('year', 'unknown')}:{row.get('category', '')}:{row.get('index', ordinal)}"
        digest = hashlib.sha256(f"{path.name}\0{source_id}\0{question}".encode()).hexdigest()[:20]
        source_tags = [file_type, path.stem]
        stem, options = _options_from_text(question)
        raw_answer = row.get("answer")
        answer = _text(raw_answer) if subjective else _answer_letters(raw_answer)
        issues: list[str] = []
        kind = "reference"
        status = "reference"
        if subjective:
            issues.append("subjective_question_reference_only")
            if not answer:
                issues.append("missing_answer")
                status = "quarantine"
        elif options:
            kind = "single_choice" if len(answer) <= 1 else "multiple_choice"
            if not answer:
                issues.append("missing_answer")
            if not set(x["key"] for x in options).issuperset(answer):
                if answer:
                    issues.append("answer_not_in_options")
            if len({x["key"] for x in options}) != len(options):
                issues.append("invalid_options")
            status = "quarantine" if issues else "ready"
        else:
            issues.append("no_parseable_options_reference_only")
            if not answer:
                issues.append("missing_answer")
                status = "quarantine"
        # A question relying on figures is unsafe to score even when answer text exists.
        has_missing_assets = bool(_IMAGE_MARK.search(question))
        if has_missing_assets:
            issues.append("image_or_figure_requires_asset_review")
            if status != "quarantine":
                status = "reference"
                kind = "reference"
        score_raw = row.get("score")
        try:
            difficulty = 1 if float(score_raw) <= 3 else (2 if float(score_raw) <= 8 else 3)
        except (TypeError, ValueError):
            difficulty = 2
        steps = [x for x in (_text(row.get("analysis")),) if x]
        record = _base(id_=f"bank:gaokao:{digest}", subject=subject, stem=question,
                    answer=answer, steps=steps, difficulty=difficulty, difficulty_raw=score_raw,
                    tags=_gaokao_knowledge(subject, question),
                    type_tags=[subject, file_type], tags_source="heuristic",
                    source_tags=source_tags, status=status, issues=issues,
                    source_id=source_id, source_file=str(path.name), url=GAOKAO_URL,
                    license_="Apache-2.0", options=options, kind=kind)
        record.update(stage="senior", has_missing_assets=has_missing_assets)
        yield record


def _cjeval_subject(value: Any) -> str:
    mapping = {
        "数学": "math", "物理": "physics", "化学": "chemistry", "生物": "biology",
        "语文": "chinese", "英语": "english", "历史": "history", "地理": "geography",
        "道德与法治": "politics", "政治": "politics", "科学": "science",
        "信息技术": "information",
    }
    name = _text(value)
    return next((subject for label, subject in mapping.items() if label in name), "math")


def _cjeval_records(path: Path) -> Iterator[dict[str, Any]]:
    subject = _cjeval_subject(path.stem)
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            original_stem = _text(row.get("ques_content"))
            stem, options = _options_from_text(original_stem)
            qtype = _text(row.get("ques_type"))
            raw_answer = row.get("ques_answer")
            answer_text = _text(raw_answer)
            answer = _answer_letters(raw_answer)
            is_multi = "多选" in qtype or len(answer) > 1
            is_choice = any(x in qtype for x in ("选择", "单选", "多选")) and "非选择" not in qtype
            # 一段材料可能包含多组 A-D 子题，不能当成一道普通多选题。
            option_labels=[match.group(1) for match in _OPTION_MARK.finditer(original_stem)]
            grouped_options=option_labels.count("A")>1
            if grouped_options:
                is_choice=False
            issues: list[str] = []
            if grouped_options:
                issues.append("grouped_subquestions_written_review")
            has_missing_assets = bool(_IMAGE_MARK.search(original_stem))
            if not is_choice:
                kind, status = "reference", "reference"
                issues.append("non_choice_or_options_unparsed_reference_only")
                if not answer_text:
                    status = "quarantine"
                    issues.append("missing_answer")
            elif len(options) < 2:
                kind, status = ("multiple_choice" if is_multi else "single_choice"), "quarantine"
                issues.append("invalid_options")
            else:
                kind = "multiple_choice" if is_multi else "single_choice"
                if not answer:
                    status = "quarantine"
                    issues.append("missing_answer")
                elif not set(answer).issubset({x["key"] for x in options}):
                    status = "quarantine"
                    issues.append("answer_not_in_options")
                else:
                    status = "ready"
            if has_missing_assets:
                issues.append("image_or_figure_requires_asset_review")
                if status != "quarantine":
                    kind, status = "reference", "reference"
            difficulty_raw = row.get("ques_difficulty")
            difficulty = {"容易": 1, "简单": 1, "一般": 2, "中等": 2, "困难": 3, "较难": 3}.get(_text(difficulty_raw), 2)
            knowledge = [_text(x) for x in _as_list(row.get("ques_knowledges")) if _text(x)]
            derived_type_tags = [f"{qtype} · {tag.split('->')[-1].strip()}" for tag in knowledge[:3] if qtype]
            explanation = _text(row.get("ques_analyze"))
            source_id = hashlib.sha256((subject + "\0" + original_stem).encode()).hexdigest()[:24]
            answer_mode = "written" if kind == "reference" and bool(answer_text) and not has_missing_assets else "choice"
            record = _base(id_=f"bank:cjeval:{source_id}", subject=subject,
                           stem=original_stem, answer=answer_text if kind == "reference" else answer,
                           steps=[explanation] if explanation else [], difficulty=difficulty,
                           difficulty_raw=difficulty_raw, tags=knowledge,
                           type_tags=[qtype] if qtype else [], tags_source="source",
                           source_tags=[x for x in (qtype, _text(difficulty_raw)) if x],
                           status=status, issues=issues, source_id=source_id,
                           source_file=str(path.relative_to(path.parents[3])), url="https://github.com/SmileWHC/CJEval",
                           license_="Academic/research use only", options=options, kind=kind)
            record.update(stage="junior", answer_mode=answer_mode, display_stem=stem if options else original_stem,
                          has_missing_assets=has_missing_assets,
                          derived_type_tags=derived_type_tags,
                          derived_type_tags_source="source_derived")
            yield record


def _ceval_records(path: Path) -> Iterator[dict[str, Any]]:
    folder = next((ancestor for ancestor in path.parents
                   if (ancestor / "annotations.json").is_file()
                   or ((ancestor / "dev").is_dir() and (ancestor / "val").is_dir())), path.parents[1])
    annotation_path = folder / "annotations.json"
    if not annotation_path.is_file():
        annotation_path = Path(__file__).parent / "data" / "ceval_annotations.json"
    annotations = {}
    annotation_meta = {}
    if annotation_path.is_file():
        with annotation_path.open(encoding="utf-8") as f:
            data = json.load(f)
        annotations = data.get("annotations", {})
        annotation_meta = {key: value for key, value in data.items() if key != "annotations"}
    split = next((part for part in path.parts if part in {"dev", "val"}), path.parent.name)
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for ordinal, row in enumerate(reader):
            question = _text(row.get("question"))
            options = [{"key": key, "text": _text(row.get(key))}
                       for key in "ABCD" if _text(row.get(key))]
            answer = _answer_letters(row.get("answer"))
            issues: list[str] = []
            if not answer:
                issues.append("missing_answer")
            if len(options) < 2:
                issues.append("invalid_options")
            elif answer and not set(answer).issubset({x["key"] for x in options}):
                issues.append("answer_not_in_options")
            stem = question + "\n" + "\n".join(f"{x['key']}. {x['text']}" for x in options)
            has_missing_assets = bool(_IMAGE_MARK.search(stem))
            status = "quarantine" if issues else "ready"
            kind = "single_choice"
            if has_missing_assets:
                issues.append("image_or_figure_requires_asset_review")
                if status != "quarantine":
                    status, kind = "reference", "reference"
            raw_id = _text(row.get("id")) or hashlib.sha256(stem.encode()).hexdigest()[:24]
            source_id = f"{split}:{raw_id}"
            explanation = _text(row.get("explanation"))
            annotation_key = f"{split}/{path.name}:{raw_id}"
            annotation = annotations.get(annotation_key, {})
            if annotation.get("question_sha256"):
                question_hash=hashlib.sha256(json.dumps({key:row[key].replace("\r\n","\n").replace("\r","\n") for key in ["question","A","B","C","D"]},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                if question_hash != annotation["question_sha256"]:
                    annotation = {}
            knowledge_tags = [_text(x) for x in annotation.get("knowledge_tags", []) if _text(x)]
            type_tags = [_text(x) for x in annotation.get("type_tags", []) if _text(x)] or ["单选题"]
            yield _base(id_=f"bank:ceval:{source_id}", subject="politics", stem=stem,
                        answer=answer, steps=[explanation] if explanation else [], difficulty=2,
                        difficulty_raw=None, tags=knowledge_tags, type_tags=type_tags,
                        tags_source="luna" if annotation else "heuristic", source_tags=[path.name], status=status,
                        issues=issues, source_id=source_id, source_file=str(path.name),
                        url="https://github.com/SJTU-LIT/ceval", license_="CC-BY-NC-SA-4.0",
                        options=options, kind=kind) | {"stage": "junior", "grade": None, "term": None,
                                                       "answer_mode": "choice", "has_missing_assets": has_missing_assets,
                                                       "annotation_origin": annotation.get("origin"),
                                                       "annotation_model": annotation_meta.get("annotation_model"),
                                                       "annotation_model_note": annotation_meta.get("annotation_model_note")}


def _cmm_records(path: Path) -> Iterator[dict[str, Any]]:
    grades = {"一年级": 1, "二年级": 2, "三年级": 3, "四年级": 4, "五年级": 5,
              "六年级": 6, "七年级": 7, "八年级": 8, "九年级": 9,
              "高一": 10, "高二": 11, "高三": 12}
    for line in path.open(encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        grade = grades.get(row.get("level"))
        stage = "unknown" if grade is None else "primary" if grade < 7 else "junior" if grade < 10 else "senior"
        question, option_text = _text(row.get("question")), _text(row.get("options"))
        repairs = []
        # The source often omits just the first A marker. Only recover an otherwise
        # complete ordered B/C/D list with nonempty leading text, never invent content.
        markers = list(_OPTION_MARK.finditer(option_text))
        if [m.group(1) for m in markers] == ["B", "C", "D"] and option_text[:markers[0].start()].strip():
            option_text = "A. " + option_text
            repairs.append("restored_missing_first_option_label")
        _, options = _options_from_text(option_text)
        answer_text = _text(row.get("answer"))
        letters = _answer_letters(answer_text)
        kind = ("single_choice" if len(letters) == 1 else "multiple_choice") if option_text else "reference"
        issues = []
        if not question or not answer_text or answer_text.lower() in {"null", "none"}:
            issues.append("missing_stem_or_answer")
        if option_text and (not letters or len(options) != 4 or not set(letters).issubset({o['key'] for o in options})):
            issues.append("invalid_choice_options_or_answer")
        images = row.get("image") or []
        if isinstance(images, str):
            try:
                images = json.loads(images)
            except ValueError:
                images = [images]
        missing = bool(images) or bool(_IMAGE_MARK.search(question + option_text)) or "<ImageHere>" in question + option_text
        status = "quarantine" if issues else "reference" if missing or kind == "reference" else "ready"
        if missing:
            issues.append("image_or_figure_requires_asset_review")
        analysis = _text(row.get("analysis"))
        if analysis.lower() in {"null", "none"}:
            analysis = ""
        source_id = str(row["id"])
        record = _base(id_=f"bank:cmm:{source_id}", subject="math", stem=question,
                       answer=letters if option_text else answer_text, steps=[analysis] if analysis else [],
                       difficulty=2, difficulty_raw=None, tags=[_text(row.get("subject"))],
                       type_tags=[], tags_source="source", source_tags=[row.get("level"), row.get("subject")],
                       status=status, issues=issues, source_id=source_id, source_file=path.name,
                       url=CMM_URL, license_="BSD-3-Clause", options=options, kind=kind)
        record.update(stage=stage, grade=grade, term=None, source_level=row.get("level"),
                      source_images=images, has_missing_assets=missing, format_repairs=repairs,
                      difficulty_basis="unknown_default_not_calibrated")
        yield record


def iter_dataset(root: Path, dataset: str) -> Iterator[dict[str, Any]]:
    """Yield normalized records. ``root`` may be data/sources or the dataset folder."""
    dataset = dataset.lower()
    files = _files(Path(root), dataset)
    if dataset == "tal":
        for path in files:
            for row in _tal_rows(path):
                yield _tal_record(row, path)
    elif dataset == "gaokao":
        for path in files:
            yield from _gaokao_records(path)
    elif dataset == "cjeval":
        seen: set[str] = set()
        for path in files:
            for record in _cjeval_records(path):
                if record["id"] not in seen:
                    seen.add(record["id"])
                    yield record
    elif dataset == "cmm":
        for path in files:
            yield from _cmm_records(path)
    else:
        for path in files:
            yield from _ceval_records(path)


def source_manifest(root: Path, dataset: str) -> dict[str, Any]:
    """Return provenance, source-file checksums/counts, and README/license hashes."""
    dataset = dataset.lower()
    files = _files(Path(root), dataset)
    entries = []
    count = 0
    for path in files:
        if dataset == "tal":
            file_count = sum(1 for line in path.open(encoding="utf-8") if line.strip())
        elif dataset == "gaokao":
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
            rows = payload.get("example", []) if isinstance(payload, dict) else payload
            file_count = len(rows) if isinstance(rows, list) else 0
        elif dataset in {"cjeval", "cmm"}:
            file_count = sum(1 for line in path.open(encoding="utf-8") if line.strip())
        else:
            with path.open(encoding="utf-8-sig", newline="") as f:
                file_count = sum(1 for _ in csv.DictReader(f))
        count += file_count
        entries.append({"source_file": str(path.relative_to(_dataset_dir(Path(root), dataset))),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "count": file_count})
    unique_count = len({record["id"] for record in iter_dataset(root, dataset)})
    folder = _dataset_dir(Path(root), dataset)
    metadata_files = []
    for path in sorted(folder.iterdir()):
        if path.is_file() and (path.name.lower().startswith("readme") or path.name.lower().startswith("license") or path.name == 'DOWNLOAD.json'):
            metadata_files.append({"source_file": path.name,
                                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    annotation_path = folder / "annotations.json"
    if dataset=="ceval" and not annotation_path.is_file():
        annotation_path=Path(__file__).parent / "data" / "ceval_annotations.json"
    if dataset=="tal" and not annotation_path.is_file():
        annotation_path=Path(__file__).parent / "data" / "tal_annotations.json"
    if annotation_path.is_file():
        metadata_files.append({"source_file": annotation_path.name,
                               "sha256": hashlib.sha256(annotation_path.read_bytes()).hexdigest()})
    urls = {"tal": TAL_URL, "gaokao": GAOKAO_URL,
            "cjeval": "https://github.com/SmileWHC/CJEval",
            "ceval": "https://github.com/SJTU-LIT/ceval", "cmm": CMM_URL}
    licenses = {"tal": "MIT", "gaokao": "Apache-2.0",
                "cjeval": "Academic/research use only", "ceval": "CC-BY-NC-SA-4.0", "cmm": "BSD-3-Clause"}
    return {"dataset": dataset, "url": urls[dataset], "license": licenses[dataset],
            "count": count, "unique_count": unique_count, "files": entries,
            "metadata_files": metadata_files}
