"""导出本机数学题库质检摘要与逐题待审清单，不调用 AI，不改变学生数据。"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.db import connect
from app.math_quality import summarize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'data/reports/math-bank-quality.json')
    args = parser.parse_args()
    with connect(Settings().database_path) as db:
        records = [json.loads(row[0]) for row in db.execute(
            "SELECT data FROM bank_questions WHERE subject='math' AND stage='junior' AND status!='superseded'")]
        report = summarize(records)
        report['playable'] = sum(q.get('can_practice', False) for q in records)
        report['playable_with_solution'] = sum(q.get('can_practice', False) and bool(q.get('steps')) for q in records)
        report['playable_by_source'] = {source:sum(q.get('can_practice',False) for q in records if q['provenance']['dataset']==source)
                                        for source in report['sources']}
        report['playable_by_answer_mode'] = {mode:sum(q.get('can_practice',False) and q.get('answer_mode')==mode for q in records)
                                             for mode in ('choice','written')}
        report['books'] = {}
        from app.bank import Selection, clauses
        for grade in (7, 8, 9):
            for term in (1, 2):
                where, params = clauses(Selection(course_book_id=f'math-{grade}-{term}'), playable=True)
                report['books'][f'math-{grade}-{term}'] = db.execute('SELECT COUNT(*) FROM bank_questions q WHERE '+where, params).fetchone()[0]
        report['review_queue'] = [
            {'id': q['id'], 'source': q['provenance'], 'issues': q.get('issues'),
             'check': q.get('quality', {}).get('answer_check'), 'content_sha256': q.get('quality', {}).get('content_sha256')}
            for q in records if not q.get('can_practice')]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'review_queue'}, ensure_ascii=False, indent=2))
    print(f'逐题质检清单：{args.output.resolve()}')


if __name__ == '__main__':
    main()
