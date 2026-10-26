"""用原创已答示例验证真实识图；独立数据库，不影响学生学习记录。"""
import asyncio
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw,ImageFont
from app.config import ROOT,Settings
from app.db import connect,initialize
from app.materials import create_import,get_import,process_import
from app.questions import parse_number


def sample_image():
    image=Image.new("RGB",(1250,900),"white")
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",36)
    rows=[("七年级数学 · 已作答示例",70,"black"),
          ("1. 计算 -8 - (-7)。",190,"black"),("学生答案：-15",260,"#2454a0"),
          ("2. 计算 |-7|。",380,"black"),("学生答案：7",450,"#2454a0"),
          ("3. 解方程 2x + 1 = 7。",570,"black"),("学生答案：x = 4",640,"#2454a0"),
          ("原创合成测试页，不代表真实手写识别准确率。",790,"#777777")]
    for text,y,color in rows:draw.text((70,y),text,font=font,fill=color)
    output=io.BytesIO();image.save(output,"PNG");return output.getvalue()


async def main():
    settings=Settings()
    if not settings.deepseek_api_key:raise SystemExit("未配置 DeepSeek Key")
    with tempfile.TemporaryDirectory(prefix="ai-teacher-real-vision-") as temp:
        settings.database_path=Path(temp)/"test.sqlite3"
        initialize(settings.database_path)
        content=sample_image()
        preview = ROOT / "output/evals/vision-test-sample.png"
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_bytes(content)
        import_id=create_import(settings,[("原创已答示例.png",content)],"completed",1,0)
        with connect(settings.database_path) as db:db.execute("UPDATE imports SET status='processing' WHERE id=?",(import_id,))
        await process_import(settings,import_id,asyncio.Semaphore(1))
        with connect(settings.database_path) as db:value=get_import(db,import_id)
        if value["status"]!="review":raise SystemExit("真实识图未完成："+(value["error"]or"未知原因"))
        items=value["items"]
        assert len(items)==3,f"预期3题，识别到{len(items)}题"
        first=next(i for i in items if "-8" in i["stem"].replace("−","-"))
        assert parse_number(first["student_answer"])==-15
        assert parse_number(first["reference_answer"])==-1 and first["suggested_verdict"]=="incorrect"
        assert all(i["question_type_id"] for i in items)
        print("真实 DeepSeek 识图通过：3题已作答内容、参考答案及细分题型；未写入真实学生状态。")
        print(json.dumps([{k:i[k] for k in ("label","student_answer","reference_answer","suggested_verdict","question_type_name")} for i in items],ensure_ascii=False))


if __name__=="__main__":asyncio.run(main())
