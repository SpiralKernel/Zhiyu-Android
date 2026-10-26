"""本地维护入口：uv run python -m app.manage sync|backup|stats。"""
import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.db import connect, initialize, replenish


def main():
    parser = argparse.ArgumentParser(description="AI-teacher 数据维护")
    parser.add_argument("command", choices=["sync", "backup", "stats", "import-bank", "import-physics-bank", "stage-physics-review", "import-physics-full-review", "import-math-full-review", "create-invites", "grant-admin", "revoke-admin", "publish-content", "import-content", "import-math-annotations", "import-physics-annotations"])
    parser.add_argument('--annotations', type=Path, nargs='+', help='Luna 候选标注 JSONL 分片')
    parser.add_argument('--apply', action='store_true', help='通过全量检查后应用；默认只检查，不写题库')
    parser.add_argument('--username', help='授予或撤销维护权限的已有账号')
    parser.add_argument('--file', type=Path, help='离线题库更新包')
    parser.add_argument('--manifest', type=Path, help='与更新包配套的版本清单')
    parser.add_argument("--count", type=int, default=10, help="邀请码数量（1—100）")
    parser.add_argument("--output", type=Path, help="邀请码私密文件路径，必须尚不存在")
    parser.add_argument("--dataset", choices=["tal", "cjeval", "ceval", "cmm", "math", "all"], default="all")
    parser.add_argument("--subject", choices=["math", "physics", "all"], default="all")
    parser.add_argument("--math-quality", action="store_true", help="补充数学细分题型、复核并隔离异常答案")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument('--review-dir', type=Path, help='固定输入及初审、复核 JSONL 所在目录')
    parser.add_argument("--stage", choices=["junior", "primary", "senior", "unknown", "all"], default="junior")
    args = parser.parse_args()
    settings = Settings()
    if args.command not in {"backup", "import-math-annotations", "import-physics-annotations", "stage-physics-review", "import-physics-full-review", "import-math-full-review"}:
        initialize(settings.database_path, with_diagnostic_core=settings.diagnostic_core_enabled)
    if args.command == 'import-math-full-review':
        import json
        from app.math_full_import import apply_full_batch
        if not args.review_dir:parser.error('需要 --review-dir 指定完整双轮审核目录')
        if not settings.database_path.exists():parser.error('需要已有数据库；此命令不会初始化学生数据')
        with connect(settings.database_path) as db:
            print(json.dumps(apply_full_batch(db, args.review_dir, dry_run=not args.apply), ensure_ascii=False, indent=2))
    elif args.command == 'import-physics-full-review':
        import json
        from app.physics_full_import import apply_full_batch
        if not args.review_dir:parser.error('需要 --review-dir 指定完整双轮审核目录')
        if not settings.database_path.exists():parser.error('需要已有数据库；此命令不会初始化学生数据')
        with connect(settings.database_path) as db:
            print(json.dumps(apply_full_batch(db, args.review_dir, dry_run=not args.apply), ensure_ascii=False, indent=2))
    elif args.command == 'stage-physics-review':
        import json
        from app.physics_review import stage_batch
        if not args.annotations or len(args.annotations) != 1:parser.error('需要 --annotations 指定一个精审清单 JSON')
        records = json.loads(args.annotations[0].read_text())
        with connect(settings.database_path) as db:
            print(json.dumps(stage_batch(db, records, dry_run=not args.apply), ensure_ascii=False, indent=2))
    elif args.command in {'import-math-annotations','import-physics-annotations'}:
        from app.math_annotations import iter_entries, apply_batch
        import json
        if not args.annotations:parser.error('需要 --annotations 指定标注分片')
        entries = iter_entries(args.annotations)
        with connect(settings.database_path) as db:
            print(json.dumps(apply_batch(db,entries,dry_run=not args.apply,subject='physics' if args.command=='import-physics-annotations' else 'math'),ensure_ascii=False,indent=2))
    elif args.command == 'import-physics-bank':
        from app.physics_bank import manifests
        from app.bank import import_records
        import json
        records,metadata=manifests(args.source_root or settings.database_path.parent/'sources')
        # All source imports commit or roll back together; student records are untouched.
        with connect(settings.database_path) as db:
            db.execute('BEGIN IMMEDIATE')
            results={dataset:import_records(db,dataset,[q for q in records if q['provenance']['dataset']==dataset],manifest,transaction=False)
                     for dataset,manifest in metadata.items()}
        print(json.dumps(results,ensure_ascii=False,indent=2))
    elif args.command in {'grant-admin','revoke-admin'}:
        from app.admin import grant_admin
        if not args.username:parser.error('需要 --username 指定已有账号')
        with connect(settings.database_path) as db:grant_admin(db,args.username,revoke=args.command=='revoke-admin')
        print('维护权限已更新')
    elif args.command == 'publish-content':
        from app.content import publish_release
        import json
        with connect(settings.database_path) as db:print(json.dumps(publish_release(db),ensure_ascii=False))
    elif args.command == 'import-content':
        from app.content import install_package
        import json
        if not args.file or not args.manifest:parser.error('需要 --file 更新包和 --manifest 版本清单')
        with connect(settings.database_path) as db:print(install_package(db,args.file.read_bytes(),json.loads(args.manifest.read_text())))
    elif args.command == "create-invites":
        from app.invites import create_invites
        if args.output is None:
            parser.error('create-invites 需要 --output 指定私密名单路径')
        create_invites(settings.database_path, args.count, args.output)
        print(f"已生成 {args.count} 个一次性邀请码：{args.output.resolve()}")
    elif args.command == "import-bank":
        from app.bank import import_records
        from app.datasets import iter_dataset, source_manifest
        root=args.source_root or settings.database_path.parent/"sources"
        datasets = (["cjeval", "tal", "ceval", "cmm"] if args.dataset == "all" else
                    ["cjeval", "tal", "cmm"] if args.dataset == "math" else [args.dataset])
        manifests, records = {}, []
        for dataset in datasets:
            manifest=source_manifest(root,dataset)
            if not manifest["count"]:
                raise SystemExit(f"{dataset} 没有本地数据，请先运行 scripts/fetch_sources.py")
            manifests[dataset] = manifest
            records.extend(q for q in iter_dataset(root,dataset)
                           if (args.stage=="all" or q["stage"]==args.stage)
                           and (args.subject=="all" or q["subject"]==args.subject))
        if args.math_quality:
            from app.math_quality import curate, summarize
            import json
            records = curate(records)
            print(json.dumps(summarize(q for q in records if q['subject']=='math' and q['stage']=='junior'), ensure_ascii=False, indent=2))
        for dataset in datasets:
            with connect(settings.database_path) as db:
                result=import_records(db,dataset,(q for q in records if q['provenance']['dataset']==dataset),manifests[dataset])
            print(f"{dataset}: {result}；筛选学段={args.stage}")
    elif args.command == "backup":
        destination = settings.database_path.parent / "backups" / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(settings.database_path) as source, sqlite3.connect(destination) as target:
            source.backup(target)
        destination.chmod(0o600)
        print(f"备份已保存：{destination.resolve()}")
        assets = settings.database_path.parent / "imports"
        if assets.exists():
            asset_destination = destination.with_suffix(".assets")
            shutil.copytree(assets, asset_destination)
            print(f"导入页面备份：{asset_destination.resolve()}")
        answers = settings.database_path.parent / "bank_answers"
        if answers.exists():
            answer_destination=destination.with_suffix(".answers")
            shutil.copytree(answers,answer_destination)
            print(f"主观解答备份：{answer_destination.resolve()}")
        teacher_images = settings.database_path.parent / "teacher_images"
        if teacher_images.exists():
            teacher_destination = destination.with_suffix(".teacher-images")
            shutil.copytree(teacher_images, teacher_destination)
            print(f"答疑照片备份：{teacher_destination.resolve()}")
    else:
        with connect(settings.database_path) as db:
            if args.command == "sync":
                print(f"新增题目：{replenish(db)}；课程结构已同步。")
            for table in ["knowledge", "questions", "attempts", "bank_questions", "bank_taxonomy", "bank_attempts", "audit_events"]:
                print(f"{table}: {db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]}")


if __name__ == "__main__":
    main()
