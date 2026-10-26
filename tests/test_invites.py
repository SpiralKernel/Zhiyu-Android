from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.config import Settings
from app.db import connect, initialize
from app.invites import code_hash, create_invites
from app.main import create_app


@pytest.fixture
def invited(tmp_path):
    settings = Settings(database_path=tmp_path/'invite.sqlite3', registration_requires_invite=True, _env_file=None)
    initialize(settings.database_path)
    output = tmp_path/'codes.txt'
    create_invites(settings.database_path, 3, output)
    codes = output.read_text().splitlines()[2:]
    with TestClient(create_app(settings)) as client:
        yield client, settings, codes


def body(name, code=''):
    return dict(username=name, password='test-password-123', grade=7, term=1, invitation_code=code)


def test_invites_are_private_single_use_and_failed_registration_keeps_code(invited):
    client, settings, codes = invited
    assert client.get('/api/v1/auth/session').json()['registration_requires_invite'] is True
    for code in ('', 'made-up'):
        assert client.post('/api/v1/auth/register', json=body('alice', code)).status_code == 403
    assert client.post('/api/v1/auth/register', json=body('alice', codes[0].lower())).status_code == 201
    assert client.post('/api/v1/auth/register', json=body('bob', codes[0])).status_code == 403
    assert client.post('/api/v1/auth/register', json=body('alice', codes[1])).status_code == 409
    assert client.post('/api/v1/auth/register', json={**body('bob', codes[1]), 'password':'short'}).status_code == 422
    assert client.post('/api/v1/auth/register', json=body('bob', codes[1])).status_code == 201
    with connect(settings.database_path) as db:
        rows = [dict(r) for r in db.execute('SELECT * FROM registration_invites')]
        assert len(rows) == 3 and sum(r['consumed_at'] is not None for r in rows) == 2
        assert all(code not in str(rows) for code in codes)
        assert db.execute('SELECT count(*) FROM accounts').fetchone()[0] == 2
    assert client.post('/api/v1/auth/login', json={'username':'alice','password':'test-password-123'}).status_code == 200


def test_failure_after_invite_consumption_rolls_back_entire_registration(invited, monkeypatch):
    client, settings, codes = invited
    original = auth.session
    def fail(*args):
        raise RuntimeError('simulated session failure')
    monkeypatch.setattr(auth, 'session', fail)
    with pytest.raises(RuntimeError, match='simulated'):
        client.post('/api/v1/auth/register', json=body('alice', codes[0]))
    with connect(settings.database_path) as db:
        assert db.execute('SELECT count(*) FROM accounts').fetchone()[0] == 0
        assert db.execute('SELECT consumed_at FROM registration_invites WHERE code_hash=?', (code_hash(codes[0]),)).fetchone()[0] is None
    monkeypatch.setattr(auth, 'session', original)
    assert client.post('/api/v1/auth/register', json=body('alice', codes[0])).status_code == 201


def test_concurrent_registration_can_consume_invite_only_once(invited):
    client, settings, codes = invited
    barrier = Barrier(2)
    def attempt(name):
        barrier.wait(timeout=5)
        return client.post('/api/v1/auth/register', json=body(name, codes[0])).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ['alice', 'bob']))
    assert sorted(results) == [201, 403]
    with connect(settings.database_path) as db:
        assert db.execute('SELECT count(*) FROM accounts').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM auth_sessions').fetchone()[0] == 1


def test_invite_generation_refuses_overwrite_and_migration_preserves_accounts(invited, tmp_path):
    client, settings, codes = invited
    client.post('/api/v1/auth/register', json=body('alice', codes[0]))
    with connect(settings.database_path) as db:
        before = tuple(db.execute('SELECT * FROM accounts').fetchone())
        db.execute('DROP TABLE registration_invites')
        db.execute('PRAGMA user_version=9')
    initialize(settings.database_path)
    with connect(settings.database_path) as db:
        assert tuple(db.execute('SELECT * FROM accounts').fetchone()) == before
        assert db.execute('PRAGMA user_version').fetchone()[0] == 16
    path = tmp_path/'private.txt'
    create_invites(settings.database_path, 2, path)
    assert path.stat().st_mode & 0o777 == 0o600
    previous = path.read_bytes()
    with pytest.raises(FileExistsError):
        create_invites(settings.database_path, 1, path)
    assert path.read_bytes() == previous
