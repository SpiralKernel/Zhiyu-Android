"""Versioned small selections; AI checked candidates remain outside trusted scores."""
import json
from pathlib import Path
from app import bank

DATASET='tizhuang-curated-20261015'

def seed(db):
    value=json.loads((Path(__file__).parent/'data/curated_web_20261015.json').read_text())
    existing={r['id'] for r in db.execute('SELECT id FROM bank_questions WHERE source_id=?',(DATASET,))}
    records=[q for q in value['records'] if q['id'] not in existing]
    if not records:return {'inserted':0}
    return bank.import_records(db,DATASET,records,{'title':'人教数学物理·逐题复算精选候选','version':value['version'],
        'source':value['source'],'retrieved_at':'2026-10-15','review':'Codex editorial checks, not teacher review; no independent scoring',
        'decisions':value['decisions']},transaction=False)
