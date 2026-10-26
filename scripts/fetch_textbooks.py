"""缓存智慧教育平台公开目录，整理人教社初中教材清单；不访问需登录的正文。"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

from app.course_catalog import BOOKS

VERSION_URL = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/resources/tch_material/version/data_version.json"
SUBJECTS = {"数学": "math", "语文": "chinese", "英语": "english", "物理": "physics", "化学": "chemistry",
            "生物学": "biology", "历史": "history", "地理": "geography", "道德与法治": "politics",
            "科学": "science", "信息科技": "information"}
GRADES = {"七年级": 7, "八年级": 8, "九年级": 9}
VOLUMES = {"上册": [1], "下册": [2], "全一册": [1, 2], "全册": [1, 2]}


def select_books(rows):
    selected = []
    for row in rows:
        tags = {t["tag_dimension_id"]: t["tag_name"] for t in row.get("tag_list", [])}
        subject = SUBJECTS.get(tags.get("zxxxk"))
        grade = GRADES.get(tags.get("zxxnj"))
        terms = VOLUMES.get(tags.get("zxxcc"))
        if (tags.get("zxxxd") != "初中" or not subject or not grade or not terms or row.get("status") != "ONLINE"
                or not any(p.get("name") == "人民教育出版社" for p in row.get("provider_list", []))):
            continue
        selected.append({"id": row["id"], "title": row["title"], "subject": subject, "subject_name": tags["zxxxk"],
            "grade": grade, "volume": tags["zxxcc"], "terms": terms, "edition_tag": tags.get("zxxbb"),
            "annual_tag": tags.get("bknd"), "revision_2022_in_title": "2022" in row["title"],
            "format": row.get("custom_properties", {}).get("format"),
            "catalog_size_bytes": row.get("custom_properties", {}).get("size"),
            "source_updated_at": row.get("update_time"),
            "detail_url": "https://basic.smartedu.cn/tchMaterial/detail?" + urlencode({
                "contentType": row["resource_type_code"], "contentId": row["id"], "catalogType": "tchMaterial", "subCatalog": "tchMaterial"}),
            "status": "catalog_only_pdf_not_downloaded"})
    groups = defaultdict(list)
    for book in selected:
        groups[(book["subject"], book["grade"], book["volume"])].append(book)
    def rank(book):
        annual = re.search(r"\d{4}", book["annual_tag"] or "")
        return book["revision_2022_in_title"], int(annual[0]) if annual else 0, book["source_updated_at"] or "", book["id"]
    preferred, alternatives = [], []
    for _, books in sorted(groups.items()):
        books.sort(key=rank, reverse=True)
        preferred.append(books[0]); alternatives.extend(books[1:])
    return preferred, alternatives


def refresh(folder):
    folder.mkdir(parents=True, exist_ok=True)
    downloads = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        def get(url, name):
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in {"s-file-1.ykt.cbern.com.cn", "s-file-2.ykt.cbern.com.cn"}:
                raise ValueError("目录地址不是已核实的官方目录主机")
            response = client.get(url)
            response.raise_for_status()
            value = response.json()
            (folder / name).write_bytes(response.content)
            downloads.append({"url": url, "file": name, "bytes": len(response.content), "sha256": hashlib.sha256(response.content).hexdigest()})
            return value
        version = get(VERSION_URL, "data_version.json")
        for url in version["urls"].split(","):
            name = urlparse(url.strip()).path.rsplit("/", 1)[-1]
            if not re.fullmatch(r"part_\d+\.json", name):
                raise ValueError("目录分片名称不符合已核实的格式")
            get(url.strip(), name)
    (folder / "DOWNLOAD.json").write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(),
        "downloads": downloads}, ensure_ascii=False, indent=2) + "\n")


def inventory(folder):
    version = json.loads((folder / "data_version.json").read_text())
    # 按版本列出的分片读取，避免更新后旧缓存分片误入结果。
    parts = [folder / urlparse(u.strip()).path.rsplit("/", 1)[-1] for u in version["urls"].split(",")]
    rows = [row for path in parts for row in json.loads(path.read_text())]
    preferred, alternatives = select_books(rows)
    covered = {f"{b['subject']}-{b['grade']}-{term}" for b in preferred for term in b["terms"]}
    missing = [{"id": b["id"], "subject": b["subject"], "grade": b["grade"], "term": b["term"]}
               for b in BOOKS if b["id"] not in covered]
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "source": VERSION_URL,
        "catalog_records": len(rows), "preferred_books": preferred, "alternate_versions": alternatives,
        "missing_project_scopes": missing, "pdf_downloaded": 0,
        "access_check": {"method": "未登录浏览器正常打开教材详情", "sample_id": "33f98190-ed21-f303-9657-d29d792f27a9",
            "observed": "需要登录才可以查看，是否登录？", "date": "2026-10-08",
            "scope": "只验证这一本；其余仅整理公开目录，未逐册测试正文访问，也未下载PDF。"}}


def render(data):
    books = data["preferred_books"]
    lines = ["# 人教社初中电子教材获取清单", "", "整理日期：" + data["checked_at"][:10], "",
        f"智慧教育平台公开目录含{data['catalog_records']}条记录。按普通六三制初中、人民教育出版社和项目学科范围筛选后，归并年度版本得到{len(books)}册；另保留{len(data['alternate_versions'])}条年度版本候选。体音美、额外外语、五四制与学生补充读本未纳入。", "",
        "**通过本脚本下载PDF：0册。** 用户另外提供的本地教材见[归档与核对说明](local-textbooks.md)。 未登录浏览器正常打开七上英语详情时，页面要求登录后查看；其它册次未逐册检查正文。目录可读不代表PDF已获取，也不代表教材目录或内容已经核对。", "",
        "2026-10-08未登录访问记录：需要登录；旧截图已清理。", "",
        "## 版本和覆盖", "",
        "语文、历史、道德与法治在平台标为统编版，出版单位是人民教育出版社，所以包含在清单中。物理九年级为全一册，对应项目两个学期，不能重复当成两本。", "",
        "同科目/年级/册次优先保留标题标明2022课标修订的记录，再按平台年度标签选择；年度未标时明确保留空值，更新时间不当作教材版次。九下语文、数学、历史、道法的当前标题未标2022修订，不能直接标为新版。", "",
        "未找到人教社出版的九下英语；科学与信息科技的全部项目阶段在该出版社范围内未找到。这是当前公开目录的筛选结果，不代表这些学科没有其他出版社教材。", "",
        "## 待获取册次", "", "| 科目 | 年级 | 册次 | 平台版本 | 年度标签 | 标题含2022修订 | 官方详情 |",
        "| --- | --- | --- | --- | --- | --- | --- |"]
    for b in books:
        lines.append(f"| {b['subject_name']} | {b['grade']} | {b['volume']} | {b['edition_tag'] or '未标'} | {b['annual_tag'] or '未标'} | {'是' if b['revision_2022_in_title'] else '未标'} | [查看]({b['detail_url']}) |")
    lines += ["", "## 同册其他年度", ""]
    for b in data["alternate_versions"]:
        lines.append(f"- {b['subject_name']} {b['grade']}年级{b['volume']} · {b['annual_tag'] or '年度未标'} · [官方详情]({b['detail_url']})")
    lines += ["", "## 本地位置与更新", "",
        "公开目录缓存：`data/sources/textbooks/smartedu/catalog/`。筛选结果和来源清单：`data/sources/textbooks/smartedu/manifest.json`。这些缓存被Git忽略，未修改学生数据库或课程核对状态。", "",
        "```bash", "# 重新读取官方公开目录并整理清单，不获取登录态或教材正文", "uv run python scripts/fetch_textbooks.py --refresh",
        "# 使用已有缓存重新整理", "uv run python scripts/fetch_textbooks.py", "```", "",
        "后续在用户登录后通过网站允许的方式获取教材PDF，放入`data/sources/textbooks/smartedu/pdf/`，再核对文件、版次和章节；不要将整本教材或账号凭据提交Git。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    base = ROOT / "data/sources/textbooks/smartedu"
    if args.refresh:
        refresh(base / "catalog")
    if not (base / "catalog/data_version.json").exists():
        raise SystemExit("缺少公开目录缓存，请先运行 --refresh")
    data = inventory(base / "catalog")
    (base / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "docs/textbook-catalog.md").write_text(render(data))
    print(f"已整理 {len(data['preferred_books'])} 册、{len(data['alternate_versions'])} 条其他年度；PDF 0 册。")


if __name__ == "__main__":
    main()
