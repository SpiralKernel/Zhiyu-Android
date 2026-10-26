"""Read-only junior physics inventory against all three local textbook volumes."""
import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.diagnostic_core import verified
from app.physics_textbooks import DATA, VERSION, alignment_candidates, types_for_book


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=Path('data/ai-teacher.sqlite3'))
    parser.add_argument('--output', type=Path, default=Path('data/reports/physics-textbooks-20261022'))
    args = parser.parse_args()
    db = sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    records, counts, coverage = [], Counter(), Counter()
    inventory_hash = hashlib.sha256()
    for row in db.execute("SELECT id,data FROM bank_questions WHERE subject='physics' AND stage='junior' "
                          "AND status!='superseded' ORDER BY id"):
        inventory_hash.update(row['data'].encode())
        q = json.loads(row['data'])
        usable = bool(q.get('can_practice')) and q['status'] != 'quarantine'
        candidates = alignment_candidates(q) if usable else []
        books = sorted({hit['physical_book_id'] for hit in candidates})
        counts['current'] += 1
        counts['usable' if usable else 'isolated'] += 1
        if usable:
            counts['no_candidate' if not books else 'one_volume_candidate' if len(books) == 1 else 'multi_volume_candidate'] += 1
            for hit in candidates:
                coverage[hit['section_id']] += 1
        records.append(dict(question_id=q['id'], snapshot_sha256=hashlib.sha256(row['data'].encode()).hexdigest(),
            usable=usable, stored_grade=q.get('grade'), stored_term=q.get('term'),
            stored_book_id=q.get('curriculum_book_id'), rule_core_verified=verified(q),
            candidates=candidates, candidate_volumes=books, needs_scope_review=usable and not verified(q)))
    db.close()
    sections = [dict(id=s['id'], name=s['name'], book_id=c['book_id'], physical_book_id=b['id'],
                     candidate_count=coverage[s['id']], practice='practice' in s['modes'])
                for b in DATA['books'] for c in b['chapters'] for s in c['sections']]
    summary = dict(version=VERSION, counts=dict(counts), source_inventory_sha256=inventory_hash.hexdigest(),
        textbooks=[dict(id=b['id'], sha256=b['sha256'], chapters=len(b['chapters']),
                        sections=sum(len(c['sections']) for c in b['chapters'])) for b in DATA['books']],
        controlled_types=sum(len(types_for_book(bid)) for b in DATA['books'] for bid in b['internal_book_ids']),
        sections=sections, no_lexical_candidates=[s['id'] for s in sections if not s['candidate_count']],
        writes_bank=False, changes_student_state=False,
        limitations=['Keyword matches are scope candidates, not reviewed assignments or full problem-type coverage.',
                     'No lexical hits do not prove missing questions; manual/model semantic classification is still required.',
                     'Grade-nine term split is a project suggestion within one physical volume.',
                     'No new answer review, empirical difficulty calibration or diagram validation was performed.'])
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'candidates.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records))
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ['counts','textbooks','controlled_types','no_lexical_candidates','writes_bank']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
