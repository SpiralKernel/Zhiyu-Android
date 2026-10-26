"""一次性注册邀请码：只存摘要；注册与消费由同一 SQLite 事务提交。"""
import base64
import hashlib
import os
import secrets
from pathlib import Path

from app.db import connect, now


def code_hash(code: str) -> str:
    normalized = ''.join(code.upper().split()).replace('-', '')
    return hashlib.sha256(normalized.encode()).hexdigest()


def create_invites(database: Path, count: int, output: Path):
    if not 1 <= count <= 100:
        raise ValueError('每批生成 1—100 个邀请码')
    codes = []
    for _ in range(count):
        raw = base64.b32encode(secrets.token_bytes(20)).decode()
        codes.append('-'.join(raw[i:i+4] for i in range(0, len(raw), 4)))
    # 不覆盖已有名单；创建时直接设为 0600，避免明文短暂暴露。
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write('AI-teacher 一次性注册邀请码（每个仅限一个账号，请私下分发）\n\n')
            stream.write('\n'.join(codes) + '\n')
        with connect(database) as db:
            db.execute('BEGIN IMMEDIATE')
            db.executemany('INSERT INTO registration_invites(code_hash,created_at) VALUES(?,?)',
                           [(code_hash(code), now()) for code in codes])
    except BaseException:
        output.unlink(missing_ok=True)
        raise
