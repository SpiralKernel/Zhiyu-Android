import json

import httpx

from scripts import fetch_textbooks as books


def record(rid="new", subject="数学", grade="七年级", volume="上册", stage="初中", publisher="人民教育出版社", annual=None):
    tags = {"zxxxk": subject, "zxxnj": grade, "zxxcc": volume, "zxxxd": stage, "zxxbb": "人教版"}
    if annual:
        tags["bknd"] = annual
    return {"id": rid, "title": "根据2022年版课程标准修订·教材", "status": "ONLINE",
            "resource_type_code": "assets_document", "provider_list": [{"name": publisher}],
            "tag_list": [{"tag_dimension_id": key, "tag_name": value} for key, value in tags.items()]}


def test_excludes_other_publisher_stage_arts_and_supplemental_reader():
    rows = [record(), record("other", publisher="其他出版社"), record("54", stage="初中（五•四学制）"),
            record("pe", subject="体育与健康"), record("reader", subject="道德与法治", grade="学生读本")]
    preferred, alternate = books.select_books(rows)
    assert [b["id"] for b in preferred] == ["new"] and not alternate
    assert preferred[0]["status"] == "catalog_only_pdf_not_downloaded"


def test_annual_versions_are_preserved_and_full_volume_spans_two_terms():
    rows = [record("2024", subject="英语", annual="2024年度"), record("2026", subject="英语", annual="2026年度"),
            record("whole", subject="物理", grade="九年级", volume="全一册")]
    preferred, alternate = books.select_books(rows)
    assert {b["id"] for b in preferred} == {"2026", "whole"}
    assert alternate[0]["id"] == "2024"
    assert next(b for b in preferred if b["id"] == "whole")["terms"] == [1, 2]


def test_refresh_uses_source_shard_names_and_ignores_stale_cached_parts(tmp_path, monkeypatch):
    version = {"urls": "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/resources/tch_material/part_410.json"}
    def handler(request):
        return httpx.Response(200, json=version if str(request.url) == books.VERSION_URL else [record()])
    real_client = httpx.Client
    monkeypatch.setattr(books.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    (tmp_path / "part_999.json").write_text(json.dumps([record("stale")]))
    books.refresh(tmp_path)
    result = books.inventory(tmp_path)
    assert [b["id"] for b in result["preferred_books"]] == ["new"]
    assert result["pdf_downloaded"] == 0
    assert (tmp_path / "part_410.json").exists()
    assert len(json.loads((tmp_path / "DOWNLOAD.json").read_text())["downloads"]) == 2
