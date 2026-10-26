from pathlib import Path
import os
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(os.environ.get('AI_TEACHER_ROOT', Path(__file__).resolve().parent.parent))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", populate_by_name=True)
    ai_provider: Literal['deepseek', 'mimo'] = 'deepseek'
    auth_required: bool = True
    diagnostic_core_enabled: bool = True
    registration_enabled: bool = True
    registration_requires_invite: bool = False
    mobile_mode: bool = False
    mobile_token: str = Field(default='', repr=False)
    local_audit_enabled: bool = False
    local_audit_base_url: str = 'http://127.0.0.1:11434'
    local_audit_model: str = 'qwen38-27b-audit:latest'
    local_audit_vision_model: str = ''
    content_source_url: str = ''
    content_source_key: str = Field(default='', repr=False)
    content_feed_key: str = Field(default='', repr=False)
    database_path: Path = ROOT / "data/ai-teacher.sqlite3"
    # 保留原Python字段兼容维护脚本；通用环境变量优先，旧DEEPSEEK_*继续可用。
    deepseek_api_key: str = Field(default='', repr=False, validation_alias=AliasChoices('AI_API_KEY', 'DEEPSEEK_API_KEY'))
    deepseek_base_url: str = Field(default='https://api.deepseek.com', validation_alias=AliasChoices('AI_BASE_URL', 'DEEPSEEK_BASE_URL'))
    deepseek_model: str = Field(default='deepseek-flash', validation_alias=AliasChoices('AI_MODEL', 'DEEPSEEK_MODEL'))
    deepseek_vision_model: str = Field(default='deepseek-flash', validation_alias=AliasChoices('AI_VISION_MODEL', 'DEEPSEEK_VISION_MODEL'))
    ai_timeout_seconds: float = Field(default=35, ge=1, le=120)
    vision_timeout_seconds: float = Field(default=90, ge=5, le=180)

    @property
    def provider_name(self):
        return 'MiMo' if self.ai_provider == 'mimo' else 'DeepSeek'

    def completion_options(self, limit):
        if self.ai_provider == 'mimo':
            # MiMo的预算参数与DeepSeek不同；短结构化交互关闭思考，避免预算被推理占满。
            return {'max_completion_tokens':limit, 'thinking':{'type':'disabled'}}
        return {'max_tokens':limit}
