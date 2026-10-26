"""Verify a backup copy before applying a frozen local senior-bank release.

Defaults to a dry run. Never contacts GitHub, a remote server, or a model API.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config import Settings
from app.db import initialize
from scripts.audit_senior_bank import audit

# Only these content/derived tables may change during content initialization.
MUTABLE={'audit_events','sqlite_sequence','bank_sources','bank_questions','bank_question_tags',
    'bank_taxonomy','course_question_links','course_mapping_state','knowledge',
    'seed_state','challenge_state','question_types'}


def snapshot(path):
    with sqlite3.connect(path) as db:
        names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        protected={t:sorted(db.execute('SELECT * FROM "'+t+'"').fetchall(),key=repr)
                   for t in names if t not in MUTABLE}
        content={t:dict(db.execute('SELECT id,data FROM '+t))
                 for t in ('questions','bank_questions','bank_editor_items')}
    return protected,content


def verify(path,before,expected):
    protected,content=snapshot(path)
    for table,rows in before[0].items():
        if protected[table]!=rows:raise RuntimeError('学生/维护记录发生变化：'+table)
    for table,rows in before[1].items():
        if any(content[table].get(k)!=v for k,v in rows.items()):
            raise RuntimeError('已有题目正文发生变化：'+table)
    with sqlite3.connect(path) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('SQLite完整性检查失败')
        if db.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('数据库外键检查失败')
        questions=[json.loads(r[0]) for r in db.execute("SELECT data FROM bank_questions WHERE stage='senior'")]
        practice=[q for q in questions if q.get('can_practice')]
        # This installer is intended for the local project baseline. Existing
        # retirements/custom content must be reconciled explicitly, not revived.
        if len(practice)!=expected:raise RuntimeError(f'可练数量与冻结清单不同：{len(practice)} / {expected}')
        return {'schema':db.execute('PRAGMA user_version').fetchone()[0],
            'protected_tables':len(before[0]),'existing_content_preserved':{t:len(r) for t,r in before[1].items()},
            'practice':len(practice),'practice_by_subject':dict(Counter(q['subject'] for q in practice)),
            'senior_stored':len(questions),'integrity':'ok','foreign_keys':'ok',
            'legacy_attempts':db.execute('SELECT count(*) FROM attempts').fetchone()[0]}


def backup(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(source) as src,sqlite3.connect(target) as dst:src.backup(dst)
    target.chmod(0o600)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    release=json.loads((ROOT/'app/data/senior_release.json').read_text())
    report=audit(release['schema_version']==2)
    if not release.get('ready_for_import') or not report['complete']:
        raise SystemExit('发布或覆盖审核未完成，拒绝更新本地数据库。')
    expected=sum(b['selected'] for b in report['books'])
    if expected!=release['selected']:raise SystemExit('发布数量与实际审核不符。')
    live=Settings().database_path
    if not live.is_file():raise SystemExit('本地数据库不存在，请先正常启动应用初始化。')
    before=snapshot(live)
    with tempfile.TemporaryDirectory(prefix='senior-install-') as temp:
        staged=Path(temp)/'staged.sqlite3';backup(live,staged)
        initialize(staged,with_diagnostic_core=True)
        result=verify(staged,before,expected)
        first=snapshot(staged)[1]
        initialize(staged,with_diagnostic_core=True)
        verify(staged,before,expected)
        if first!=snapshot(staged)[1]:raise RuntimeError('重复初始化改写了题目。')
    result.update(applied=False,repeat_initialization='no duplicate or changed content')
    if args.apply:
        if snapshot(live)!=before:raise SystemExit('副本验证期间本地记录变化，请重新执行。')
        saved=ROOT/'data/backups'/f'{datetime.now():%Y%m%d-%H%M%S}-before-senior-foundations.sqlite3'
        backup(live,saved)
        if snapshot(saved)!=before:raise RuntimeError('备份与验证起点不同。')
        initialize(live,with_diagnostic_core=True)
        result.update(verify(live,before,expected));result.update(applied=True,backup=str(saved))
    out=ROOT/'data/annotations/senior-foundations-20261016/local-install-verification.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2));out.chmod(0o600)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
