import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.curriculum import NODES, VERSION
from app.questions import make_question, validate_question
from app.question_types import ensure_templates


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


@contextmanager
def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    from app.identity import student_id
    owner = student_id()
    db.create_function("current_student", 0, lambda: owner)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def audit(db, kind: str, details: dict):
    db.execute("INSERT INTO audit_events(kind,details,created_at) VALUES(?,?,?)", (kind, dumps(details), now()))


def initialize(path: Path, *, with_diagnostic_core=False):
    with connect(path) as db:
        path.chmod(0o600)
        db.execute("PRAGMA journal_mode = WAL")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > 16:
            raise RuntimeError("数据库版本高于应用支持版本，拒绝降级打开。")
        if version == 0:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE knowledge(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE questions(
                    id TEXT PRIMARY KEY, knowledge_id TEXT NOT NULL REFERENCES knowledge(id),
                    content_hash TEXT NOT NULL UNIQUE, data TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE seed_state(knowledge_id TEXT PRIMARY KEY REFERENCES knowledge(id), next_index INTEGER NOT NULL);
                CREATE TABLE students(id TEXT PRIMARY KEY, nickname TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE attempts(
                    id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
                    question_id TEXT NOT NULL REFERENCES questions(id), status TEXT NOT NULL DEFAULT 'assigned'
                    CHECK(status IN ('assigned','submitted','skipped')),
                    hint_used INTEGER NOT NULL DEFAULT 0, answer TEXT, result TEXT,
                    assigned_at TEXT NOT NULL, submitted_at TEXT);
                CREATE UNIQUE INDEX one_active_attempt ON attempts(student_id) WHERE status='assigned';
                CREATE INDEX attempts_student ON attempts(student_id,submitted_at);
                CREATE TABLE mastery(
                    student_id TEXT NOT NULL REFERENCES students(id),
                    knowledge_id TEXT NOT NULL REFERENCES knowledge(id),
                    success REAL NOT NULL DEFAULT 0, failure REAL NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0, last_seen TEXT,
                    PRIMARY KEY(student_id,knowledge_id));
                CREATE TABLE tutor_messages(
                    id INTEGER PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(id),
                    user_message TEXT NOT NULL, response TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE audit_events(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,details TEXT NOT NULL,created_at TEXT NOT NULL);
                PRAGMA user_version = 1;
                COMMIT;
            """)
        if version < 2:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE imports(
                    id TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES students(id),
                    title TEXT NOT NULL,mode TEXT NOT NULL CHECK(mode IN ('completed','blank')),
                    status TEXT NOT NULL CHECK(status IN ('uploaded','processing','review','confirmed','failed')),
                    page_count INTEGER NOT NULL,source_files TEXT NOT NULL,error TEXT,
                    model TEXT,created_at TEXT NOT NULL,confirmed_at TEXT);
                CREATE TABLE import_pages(
                    import_id TEXT NOT NULL REFERENCES imports(id),page_number INTEGER NOT NULL,
                    file_name TEXT NOT NULL,source_label TEXT NOT NULL,
                    PRIMARY KEY(import_id,page_number));
                CREATE TABLE import_items(
                    id TEXT PRIMARY KEY,import_id TEXT NOT NULL REFERENCES imports(id),
                    position INTEGER NOT NULL,data TEXT NOT NULL);
                CREATE TABLE import_evidence(
                    item_id TEXT PRIMARY KEY REFERENCES import_items(id),
                    import_id TEXT NOT NULL REFERENCES imports(id),student_id TEXT NOT NULL REFERENCES students(id),
                    fingerprint TEXT NOT NULL,knowledge_ids TEXT NOT NULL,
                    verdict TEXT NOT NULL CHECK(verdict IN ('correct','incorrect')),
                    weight REAL NOT NULL CHECK(weight>0 AND weight<=0.5),created_at TEXT NOT NULL,
                    UNIQUE(student_id,fingerprint));
                CREATE TABLE import_messages(
                    id INTEGER PRIMARY KEY,item_id TEXT NOT NULL REFERENCES import_items(id),
                    user_message TEXT NOT NULL,response TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE INDEX import_student ON imports(student_id,created_at);
                PRAGMA user_version = 2;
                COMMIT;
            """)
        if version < 3:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE question_types(id TEXT PRIMARY KEY,subject TEXT NOT NULL,
                    grade INTEGER NOT NULL,term INTEGER NOT NULL,normalized_name TEXT NOT NULL,data TEXT NOT NULL,
                    UNIQUE(subject,grade,term,normalized_name));
                CREATE TABLE challenge_state(knowledge_id TEXT PRIMARY KEY REFERENCES knowledge(id),next_index INTEGER NOT NULL);
                PRAGMA user_version = 3;
                COMMIT;
            """)
        if version < 4:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE bank_sources(id TEXT PRIMARY KEY,manifest TEXT NOT NULL,imported_at TEXT NOT NULL);
                CREATE TABLE bank_questions(
                    id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES bank_sources(id),
                    subject TEXT NOT NULL,stage TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,
                    difficulty INTEGER NOT NULL,content_hash TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL,
                    UNIQUE(subject,content_hash));
                CREATE INDEX bank_filter ON bank_questions(subject,stage,status,difficulty);
                CREATE TABLE bank_taxonomy(
                    id TEXT PRIMARY KEY,subject TEXT NOT NULL,stage TEXT NOT NULL,kind TEXT NOT NULL,
                    label TEXT NOT NULL,origin TEXT NOT NULL,needs_review INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(subject,stage,kind,label));
                CREATE TABLE bank_question_tags(
                    question_id TEXT NOT NULL REFERENCES bank_questions(id),
                    tag_id TEXT NOT NULL REFERENCES bank_taxonomy(id),PRIMARY KEY(question_id,tag_id));
                CREATE INDEX bank_tag_lookup ON bank_question_tags(tag_id,question_id);
                CREATE TABLE bank_attempts(
                    id TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES students(id),
                    question_id TEXT NOT NULL REFERENCES bank_questions(id),
                    status TEXT NOT NULL CHECK(status IN ('assigned','skipped','submitted')),
                    assisted INTEGER NOT NULL DEFAULT 0,answer TEXT,result TEXT,
                    created_at TEXT NOT NULL,submitted_at TEXT);
                CREATE UNIQUE INDEX bank_one_active ON bank_attempts(student_id) WHERE status='assigned';
                CREATE INDEX bank_attempt_student ON bank_attempts(student_id,submitted_at);
                CREATE TABLE bank_reviews(attempt_id TEXT PRIMARY KEY REFERENCES bank_attempts(id),data TEXT NOT NULL);
                CREATE TABLE bank_messages(id INTEGER PRIMARY KEY,attempt_id TEXT NOT NULL REFERENCES bank_attempts(id),
                    user_message TEXT NOT NULL,response TEXT NOT NULL,created_at TEXT NOT NULL);
                PRAGMA user_version=4;
                COMMIT;
            """)
        if version < 5:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE course_settings(
                    student_id TEXT NOT NULL REFERENCES students(id),subject TEXT NOT NULL,data TEXT NOT NULL,
                    PRIMARY KEY(student_id,subject));
                CREATE TABLE course_question_links(
                    question_id TEXT NOT NULL REFERENCES bank_questions(id),goal_id TEXT NOT NULL,
                    version TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(question_id,goal_id));
                CREATE INDEX course_goal_questions ON course_question_links(goal_id,question_id);
                CREATE TABLE course_mapping_state(
                    question_id TEXT PRIMARY KEY REFERENCES bank_questions(id),signature TEXT NOT NULL);
                PRAGMA user_version=5;
                COMMIT;
            """)
        if version < 6:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE student_preferences(
                    student_id TEXT PRIMARY KEY REFERENCES students(id),data TEXT NOT NULL);
                PRAGMA user_version=6;
                COMMIT;
            """)
        if version < 7:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS math_diagnostics(
                    id TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES students(id),
                    book_id TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('active','completed','cancelled')),
                    data TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_math_diagnostic ON math_diagnostics(student_id,book_id) WHERE status='active';
                CREATE TABLE IF NOT EXISTS math_diagnostic_items(
                    session_id TEXT NOT NULL REFERENCES math_diagnostics(id),position INTEGER NOT NULL,
                    type_id TEXT NOT NULL,question_id TEXT NOT NULL REFERENCES questions(id),
                    attempt_id TEXT UNIQUE REFERENCES attempts(id),
                    PRIMARY KEY(session_id,position),UNIQUE(session_id,question_id));
                PRAGMA user_version=7;
                COMMIT;
            """)
        if version < 8:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS accounts(
                    username TEXT PRIMARY KEY,student_id TEXT NOT NULL UNIQUE REFERENCES students(id),
                    salt TEXT NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS student_scopes(
                    student_id TEXT PRIMARY KEY REFERENCES students(id),
                    grade INTEGER NOT NULL CHECK(grade IN (7,8,9)),term INTEGER NOT NULL CHECK(term IN (1,2)));
                CREATE TABLE IF NOT EXISTS auth_sessions(
                    token_hash TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES students(id),expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS login_failures(username TEXT NOT NULL,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS study_messages(
                    id INTEGER PRIMARY KEY,student_id TEXT NOT NULL REFERENCES students(id),book_id TEXT NOT NULL,
                    type_id TEXT NOT NULL,message TEXT NOT NULL,response TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS study_owner ON study_messages(student_id,book_id,type_id,id);
                PRAGMA user_version=8;
                COMMIT;
            """)
        if version < 9:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS teacher_threads(
                    id TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES students(id),book_id TEXT NOT NULL,
                    title TEXT NOT NULL,context TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS teacher_messages(
                    id TEXT PRIMARY KEY,thread_id TEXT NOT NULL REFERENCES teacher_threads(id),
                    request_id TEXT NOT NULL,message TEXT NOT NULL,response TEXT NOT NULL,created_at TEXT NOT NULL,
                    UNIQUE(thread_id,request_id));
                CREATE TABLE IF NOT EXISTS learning_observations(
                    id TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES students(id),book_id TEXT NOT NULL,
                    type_id TEXT NOT NULL,message_id TEXT REFERENCES teacher_messages(id),
                    data TEXT NOT NULL,dismissed INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS observation_owner ON learning_observations(student_id,book_id,type_id,created_at);
                CREATE TABLE IF NOT EXISTS parent_reports(
                    student_id TEXT NOT NULL REFERENCES students(id),book_id TEXT NOT NULL,period TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL,
                    PRIMARY KEY(student_id,book_id,period));
                CREATE INDEX IF NOT EXISTS teacher_owner ON teacher_threads(student_id,book_id,updated_at);
                PRAGMA user_version=9;
                COMMIT;
            """)
        if version < 10:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS registration_invites(
                    code_hash TEXT PRIMARY KEY,created_at TEXT NOT NULL,
                    consumed_at TEXT,used_by TEXT REFERENCES students(id),
                    CHECK((consumed_at IS NULL AND used_by IS NULL) OR
                          (consumed_at IS NOT NULL AND used_by IS NOT NULL)));
                PRAGMA user_version=10;
                COMMIT;
            """)
        if version < 11:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS admin_accounts(student_id TEXT PRIMARY KEY REFERENCES accounts(student_id),created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS bank_editor_items(
                    id TEXT PRIMARY KEY,source_kind TEXT,source_id TEXT,source_hash TEXT,
                    revision INTEGER NOT NULL,data TEXT NOT NULL,state TEXT NOT NULL,
                    published_id TEXT REFERENCES bank_questions(id),updated_at TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS editor_source ON bank_editor_items(source_kind,source_id) WHERE source_id IS NOT NULL;
                CREATE TABLE IF NOT EXISTS bank_editor_events(
                    id INTEGER PRIMARY KEY,item_id TEXT NOT NULL REFERENCES bank_editor_items(id),revision INTEGER NOT NULL,
                    action TEXT NOT NULL,actor TEXT NOT NULL REFERENCES accounts(student_id),data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS content_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS content_releases(
                    version INTEGER PRIMARY KEY AUTOINCREMENT,publisher_id TEXT NOT NULL,checksum TEXT NOT NULL,
                    item_count INTEGER NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS content_installs(
                    publisher_id TEXT PRIMARY KEY,version INTEGER NOT NULL,checksum TEXT NOT NULL,installed_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS content_installed_items(
                    publisher_id TEXT NOT NULL,family TEXT NOT NULL,remote_id TEXT NOT NULL,local_id TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(publisher_id,family,remote_id));
                PRAGMA user_version=11;
                COMMIT;
            """)
        if version < 12:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS student_subjects(
                    student_id TEXT PRIMARY KEY REFERENCES students(id),
                    subject TEXT NOT NULL CHECK(subject IN ('math','physics')));
                PRAGMA user_version=12;
                COMMIT;
            """)
        if version < 13:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS student_learning_scopes(
                    student_id TEXT PRIMARY KEY REFERENCES students(id),
                    stage TEXT NOT NULL CHECK(stage IN ('junior','senior')),
                    book_id TEXT);
                CREATE TABLE IF NOT EXISTS scoped_question_types(
                    id TEXT PRIMARY KEY,book_id TEXT NOT NULL,normalized_name TEXT NOT NULL,
                    data TEXT NOT NULL,UNIQUE(book_id,normalized_name));
                PRAGMA user_version=13;
                COMMIT;
            """)
        if version < 14:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS training_plans(
                    id TEXT PRIMARY KEY,student_id TEXT NOT NULL REFERENCES students(id),book_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','completed','cancelled')),
                    data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS training_active ON training_plans(student_id,book_id) WHERE status='active';
                CREATE TABLE IF NOT EXISTS training_items(
                    plan_id TEXT NOT NULL REFERENCES training_plans(id),position INTEGER NOT NULL,
                    source TEXT NOT NULL CHECK(source IN ('verified','bank')),question_id TEXT NOT NULL,
                    identity TEXT NOT NULL,content_hash TEXT NOT NULL,
                    phase TEXT NOT NULL CHECK(phase IN ('training','retest','diagnostic')),
                    attempt_id TEXT UNIQUE,PRIMARY KEY(plan_id,position));
                PRAGMA user_version=14;
                COMMIT;
            """)
        if version < 15:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS calibration_jobs(
                    id TEXT PRIMARY KEY,book_id TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS calibration_items(
                    job_id TEXT NOT NULL REFERENCES calibration_jobs(id),question_id TEXT NOT NULL,
                    data TEXT NOT NULL,result TEXT,published_id TEXT REFERENCES bank_questions(id),
                    PRIMARY KEY(job_id,question_id));
                PRAGMA user_version=15;
                COMMIT;
            """)
        if version < 16:
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS app_profiles(
                    student_id TEXT PRIMARY KEY REFERENCES students(id), data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ai_connections(
                    id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), data TEXT NOT NULL);
                PRAGMA user_version=16;
                COMMIT;
            """)
        columns={r[1] for r in db.execute('PRAGMA table_info(imports)')}
        if 'book_id' not in columns:
            db.execute("ALTER TABLE imports ADD COLUMN book_id TEXT NOT NULL DEFAULT 'math-7-1'")
            db.commit()
        db.execute("BEGIN IMMEDIATE")
        for node in NODES:
            db.execute("INSERT INTO knowledge VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                       (node["id"], dumps(node)))
            db.execute("INSERT OR IGNORE INTO seed_state VALUES(?,0)", (node["id"],))
            db.execute("INSERT OR IGNORE INTO challenge_state VALUES(?,0)", (node["id"],))
        db.execute("INSERT OR IGNORE INTO students VALUES('demo','学习者',?)", (now(),))
        ensure_templates(db)
        audit(db, "curriculum_sync", {"version": VERSION, "nodes": len(NODES)})
        replenish(db)
        from app.diagnostic_core import seed as seed_core
        if with_diagnostic_core:
            seed_core(db)
            from app.curated_bank import seed as seed_curated
            seed_curated(db)
            from app.senior_bank import seed as seed_senior
            seed_senior(db)
        from app.courses import sync_questions
        sync_questions(db)


def replenish(db, minimum: int = 6) -> int:
    """为演示学生补足未做题；最多尝试 400 个参数，防止有限题型耗尽时死循环。"""
    added = 0
    for node in NODES:
        available = db.execute("""SELECT COUNT(*) FROM questions q WHERE knowledge_id=? AND json_extract(q.data,'$.difficulty')<3 AND json_extract(q.data,'$.provenance.family') IS NULL AND NOT EXISTS
            (SELECT 1 FROM attempts a WHERE a.question_id=q.id AND a.student_id=current_student() AND a.status='submitted')""",
                               (node["id"],)).fetchone()[0]
        needed = max(0, minimum - available)
        index = db.execute("SELECT next_index FROM seed_state WHERE knowledge_id=?", (node["id"],)).fetchone()[0]
        for _ in range(400 if needed else 0):
            q = make_question(node["id"], index)
            index += 1
            if not validate_question(q):
                raise ValueError("题目未通过校验")
            content_hash = hashlib.sha256(q["stem"].encode()).hexdigest()
            cursor = db.execute("INSERT OR IGNORE INTO questions VALUES(?,?,?,?,?)",
                                (q["id"], node["id"], content_hash, dumps(q), now()))
            added += cursor.rowcount
            needed -= cursor.rowcount
            if needed <= 0:
                break
        db.execute("UPDATE seed_state SET next_index=? WHERE knowledge_id=?", (index, node["id"]))
        from app.challenges import make_challenge
        available = db.execute("""SELECT COUNT(*) FROM questions q WHERE knowledge_id=? AND json_extract(q.data,'$.difficulty')=3 AND NOT EXISTS
            (SELECT 1 FROM attempts a WHERE a.question_id=q.id AND a.student_id=current_student() AND a.status='submitted')""", (node["id"],)).fetchone()[0]
        needed = max(0, 2-available)
        index = db.execute("SELECT next_index FROM challenge_state WHERE knowledge_id=?", (node["id"],)).fetchone()[0]
        for _ in range(100 if needed else 0):
            q = make_challenge(node["id"], index)
            index += 1
            cursor = db.execute("INSERT OR IGNORE INTO questions VALUES(?,?,?,?,?)", (q["id"], node["id"], hashlib.sha256(q["stem"].encode()).hexdigest(), dumps(q), now()))
            added += cursor.rowcount
            needed -= cursor.rowcount
            if needed <= 0:break
        db.execute("UPDATE challenge_state SET next_index=? WHERE knowledge_id=?", (index, node["id"]))
    from app.foundations import replenish_foundations
    added += replenish_foundations(db)
    if added:
        audit(db, "verified_question_replenishment", {"added": added, "template_version": "1"})
    return added
