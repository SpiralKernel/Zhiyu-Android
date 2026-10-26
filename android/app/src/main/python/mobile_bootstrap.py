"""Private loopback ASGI backend running entirely inside the Android process."""
import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path

_lock=threading.Lock()
_running=None


def start(root):
    global _running
    with _lock:
        if _running:return json.dumps(_running)
        root=Path(root);data=root/'data';data.mkdir(exist_ok=True)
        token=secrets.token_urlsafe(32)
        os.environ.update(AI_TEACHER_ROOT=str(root),DATABASE_PATH=str(data/'ai-teacher.sqlite3'),MOBILE_MODE='true',MOBILE_TOKEN=token,
                          AUTH_REQUIRED='true',REGISTRATION_ENABLED='true',REGISTRATION_REQUIRES_INVITE='false',
                          AI_API_KEY='',DEEPSEEK_API_KEY='',LOCAL_AUDIT_ENABLED='true',DIAGNOSTIC_CORE_ENABLED='false')
        from app.db import initialize,connect
        path=data/'ai-teacher.sqlite3';initialize(path)
        from app.mobile_content import installed,install
        seed=json.loads((root/'seed/manifest.json').read_text())
        with connect(path) as db:
            if installed(db)<seed['version']:
                install(db,(root/'seed'/f"bank-{seed['version']}.bank").read_bytes(),seed)
        from app.main import app
        import uvicorn
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        config=uvicorn.Config(app,host='127.0.0.1',port=port,loop='asyncio',http='h11',access_log=False,log_level='warning',lifespan='on')
        server=uvicorn.Server(config)
        worker=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);worker.start()
        for _ in range(600):
            if server.started:
                _running={'url':f'http://127.0.0.1:{port}','token':token};return json.dumps(_running)
            if not worker.is_alive():raise RuntimeError('本地服务启动失败')
            time.sleep(.05)
        raise RuntimeError('本地服务启动超时')
