"""下载本地研究题库缓存，不调用模型、不修改学生数据库。"""
import argparse
import csv
import hashlib
import io
import json
import zipfile
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import httpx

from app.config import Settings


def fetch(root, dataset):
    folder = root / dataset
    folder.mkdir(parents=True, exist_ok=True)
    downloads = []
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        def get(url):
            response = client.get(url)
            response.raise_for_status()
            downloads.append({"url": url, "sha256": hashlib.sha256(response.content).hexdigest(), "bytes": len(response.content)})
            return response.content

        if dataset == "tal":
            revision = json.loads(get("https://huggingface.co/api/datasets/math-eval/TAL-SCQ5K"))["sha"]
            for file in ["README.md", "TAL-SCQ5K-CN/train.jsonl", "TAL-SCQ5K-CN/test.jsonl"]:
                out = folder / file
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(get(f"https://huggingface.co/datasets/math-eval/TAL-SCQ5K/resolve/{revision}/" + file))
        elif dataset == "cmm":
            # Pin metadata and content to the same immutable upstream revision.
            meta = json.loads(get("https://huggingface.co/api/datasets/ecnu-icalk/cmm-math"))
            revision = meta["sha"]
            for file in ["README.md", "train_data.jsonl", "test_data.jsonl"]:
                (folder / file).write_bytes(get(
                    f"https://huggingface.co/datasets/ecnu-icalk/cmm-math/resolve/{revision}/{file}"))
        elif dataset == "cjeval":
            revision = json.loads(get("https://api.github.com/repos/SmileWHC/CJEval/commits/main"))["sha"]
            payload = get(f"https://codeload.github.com/SmileWHC/CJEval/zip/{revision}")
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                for member in archive.infolist():
                    relative = Path(*Path(member.filename).parts[1:])
                    if member.is_dir() or ".." in relative.parts or relative.is_absolute():
                        continue
                    if str(relative).startswith("data/CJEval_data/") and relative.suffix == ".json" or relative.name in {"README.md", "LICENSE"}:
                        out = folder / relative
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(archive.read(member))
        elif dataset == "ceval":
            (folder / "README.md").write_bytes(get("https://raw.githubusercontent.com/SJTU-LIT/ceval/main/README.md"))
            for split in ["dev", "val"]:
                url = f"https://datasets-server.huggingface.co/rows?dataset=ceval%2Fceval-exam&config=middle_school_politics&split={split}&offset=0&length=100"
                payload = get(url)
                (folder / (split + "-original.json")).write_bytes(payload)
                rows = [r["row"] for r in json.loads(payload)["rows"]]
                out = folder / split / f"middle_school_politics_{split}.csv"
                out.parent.mkdir(parents=True, exist_ok=True)
                with out.open("w", encoding="utf-8", newline="") as file:
                    writer = csv.DictWriter(file, fieldnames=["id", "question", "A", "B", "C", "D", "answer", "explanation"])
                    writer.writeheader()
                    writer.writerows(rows)
        else:
            raise ValueError("未知题库")
    (folder / "DOWNLOAD.json").write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "downloads": downloads}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已下载 {dataset} → {folder}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["tal", "cjeval", "ceval", "cmm", "math", "all"], default="all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.output or Settings().database_path.parent / "sources"
    datasets = (["tal", "cjeval", "ceval", "cmm"] if args.dataset == "all" else
                ["cjeval", "tal", "cmm"] if args.dataset == "math" else [args.dataset])
    for dataset in datasets:
        fetch(root, dataset)


if __name__ == "__main__":
    main()
