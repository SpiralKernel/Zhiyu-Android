"""一次真实 API 验证；只打印模型和讲解，不打印密钥或请求头。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.config import Settings
from app.questions import make_question
from app.tutor import respond


async def main():
    settings = Settings()
    if not settings.deepseek_api_key:
        raise SystemExit("尚未配置 DEEPSEEK_API_KEY")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(settings.deepseek_base_url.rstrip("/") + "/models",
                                    headers={"Authorization": f"Bearer {settings.deepseek_api_key}"})
    if response.status_code != 200:
        raise SystemExit(f"模型列表请求失败，HTTP {response.status_code}；请检查 Key、余额及服务状态。")
    models = [item["id"] for item in response.json().get("data", [])]
    print("可用模型：" + ", ".join(models))
    if settings.deepseek_model not in models:
        raise SystemExit("配置的模型不在可用模型列表，请调整 DEEPSEEK_MODEL 后重试。")
    result = await respond(settings, make_question("absolute", 0), "绝对值为什么不能是负数？先给我一点思路，不直接报这题答案。",
                           {"attempts": 0, "mastery": None, "status": "尚未练习"}, [])
    if result["provider"] != "deepseek":
        raise SystemExit("真实对话未成功，已降级为题库提示。请检查模型兼容性、余额或超时配置。")
    print("真实 DeepSeek 对话成功（结构化响应通过校验）。")
    print(result["reply"])
    print(result["check_question"])


if __name__ == "__main__":
    asyncio.run(main())
