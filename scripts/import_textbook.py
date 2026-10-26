"""归档用户提供的本地教材，提取带PDF页码的文字；不自动认证版次或课程覆盖。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/sources/textbooks/local"


def import_pdf(source, scope_id, base=BASE):
    if not re.fullmatch(r"[a-z]+-[789]-[12]", scope_id):
        raise ValueError("学习阶段必须为 math-7-1 等科目-年级-学期标识")
    source, base = Path(source), Path(base)
    content = source.read_bytes()
    if not content.startswith(b"%PDF-"):
        raise ValueError("输入文件不是PDF")
    fingerprint = hashlib.sha256(content).hexdigest()
    count = len(PdfReader(source).pages)
    result = subprocess.run(["pdftotext", "-layout", str(source), "-"],
                            capture_output=True, check=True)
    pages = result.stdout.decode("utf-8").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    if len(pages) != count:
        raise ValueError("文字提取页数与PDF页数不符，需人工检查")
    stem = f"{scope_id}-{fingerprint[:12]}"
    pdf_path, text_path = base / "pdf" / f"{stem}.pdf", base / "text" / f"{stem}.json"
    manifest_path = base / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"books": []}
    existing = next((b for b in manifest["books"] if b["sha256"] == fingerprint and b["scope_id"] == scope_id), None)
    for folder in (pdf_path.parent, text_path.parent):
        folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, pdf_path)
    if hashlib.sha256(pdf_path.read_bytes()).hexdigest() != fingerprint:
        raise ValueError("归档副本指纹不一致")
    text_path.write_text(json.dumps({"sha256": fingerprint, "page_numbering": "PDF页，从1计",
        "note": "文字层仅供检索；公式、上下标、分式与图形须结合原页核对，不直接作为题目答案。",
        "pages": [{"pdf_page": n, "text": text} for n, text in enumerate(pages, 1)]}, ensure_ascii=False, indent=2) + "\n")
    entry = {"scope_id": scope_id, "sha256": fingerprint, "original_filename": source.name,
        "pages": count, "nonempty_text_pages": sum(bool(p.strip()) for p in pages),
        "pdf": str(pdf_path.relative_to(base)), "text": str(text_path.relative_to(base)),
        "provided_by": "user", "origin_url": None, "edition_year": None,
        "imported_at": existing["imported_at"] if existing else datetime.now(timezone.utc).isoformat(),
        "status": "text_extracted_pending_content_review",
        "extraction_warnings": result.stderr.decode("utf-8", errors="replace")[:4000]}
    manifest["books"] = [b for b in manifest["books"] if not (b["scope_id"] == scope_id and b["sha256"] == fingerprint)] + [entry]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--scope", required=True)
    args = parser.parse_args()
    entry = import_pdf(args.pdf, args.scope)
    print(f"已归档 {entry['scope_id']}：{entry['pages']}页，SHA256 {entry['sha256']}。目录与版次需单独核对。")


if __name__ == "__main__":
    main()
