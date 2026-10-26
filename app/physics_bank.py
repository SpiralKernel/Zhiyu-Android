"""Content-only, source-pinned preparation of public junior physics questions."""
import copy
import csv
import hashlib
import json
import re
from pathlib import Path

from app.datasets import iter_dataset, _base, _IMAGE_MARK


def curate(record):
    q = copy.deepcopy(record)
    if q.get('subject') != 'physics' or q.get('stage') != 'junior':
        raise ValueError('仅处理明确初中物理题')
    q['difficulty_basis'] = ('来源难度：'+str(q.get('difficulty_raw'))+'；未经实测校准'
                              if q.get('difficulty_raw') else '来源未提供难度；默认中等，待核对')
    q['quality'] = {**q.get('quality', {}), 'version':'physics-20261012',
                    'answer_check':{'status':'not_checked','basis':'来源参考答案，尚未人工核验'}}
    return q


def ceval_records(folder):
    """Only labeled dev/val CSVs. Test and other subjects cannot slip in."""
    folder=Path(folder)
    meta=json.loads((folder/'DOWNLOAD.json').read_text())
    revision=meta['revision']
    if not re.fullmatch('[0-9a-f]{40}', revision):raise ValueError('C-Eval 缓存缺少固定版本')
    expected={f['path']:f['sha256'] for f in meta['files']}
    for split in ('dev','val'):
        path=folder/f'middle_school_physics_{split}.csv'
        if not path.is_file():raise FileNotFoundError(path)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if expected.get(path.name)!=digest:raise ValueError('C-Eval CSV 来源校验失败')
        with path.open(encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                answer=str(row.get('answer','')).strip().upper()
                options=[{'key':k,'text':str(row.get(k,'')).strip()} for k in 'ABCD']
                stem=str(row.get('question','')).strip()
                issues=[]
                if not stem:issues.append('missing_stem')
                if answer not in 'ABCD' or len(answer)!=1:issues.append('missing_answer')
                if any(not o['text'] for o in options):issues.append('invalid_options')
                missing=bool(_IMAGE_MARK.search(stem+'\n'+'\n'.join(o['text'] for o in options)))
                if missing:issues.append('image_or_figure_requires_asset_review')
                source_id=f"physics:{split}:{row['id']}"
                explanation=str(row.get('explanation','')).strip()
                q=_base(id_=f'bank:ceval-physics:{source_id}',subject='physics',stem=stem,answer=answer,
                    steps=[explanation] if explanation else [],difficulty=2,difficulty_raw=None,
                    tags=[],type_tags=['单选题'],tags_source='source',source_tags=['middle_school_physics',split],
                    status='quarantine' if issues else 'ready',issues=issues,source_id=source_id,
                    source_file=str(path.relative_to(folder)),url='https://huggingface.co/datasets/ceval/ceval-exam',
                    license_='CC-BY-NC-SA-4.0',options=options,kind='single_choice')
                q.update(stage='junior',has_missing_assets=missing)
                q['provenance'].update(revision=revision,source_file_sha256=digest)
                yield curate(q)


def source_records(root, *, include_ceval=True):
    root=Path(root)
    folder=root/'cjeval'
    metadata=json.loads((folder/'DOWNLOAD.json').read_text())
    revisions=[d['url'].rsplit('/',1)[-1] for d in metadata['downloads'] if 'codeload.github.com/SmileWHC/CJEval/zip/' in d['url']]
    if len(revisions)!=1 or not re.fullmatch('[0-9a-f]{40}',revisions[0]):raise ValueError('CJEval 缓存缺少固定来源版本')
    hashes={}
    for q in iter_dataset(root,'cjeval'):
        if q['subject']!='physics' or q['stage']!='junior':continue
        path=folder/q['provenance']['source_file']
        if path not in hashes:hashes[path]=hashlib.sha256(path.read_bytes()).hexdigest()
        q['provenance'].update(revision=revisions[0],source_file_sha256=hashes[path])
        yield curate(q)
    if include_ceval:yield from ceval_records(root/'ceval-physics')


def manifests(root):
    root=Path(root)
    records=list(source_records(root))
    result={}
    for dataset in ('cjeval','ceval-physics'):
        qs=[q for q in records if q['provenance']['dataset']==dataset]
        first=qs[0]['provenance']
        result[dataset]={'dataset':dataset,'subject':'physics','stage':'junior','count':len(qs),
                         'revision':first['revision'],'url':first['url'],'license':first['license'],
                         'files':[{ 'source_file':p,'sha256':h} for p,h in sorted({
                             (q['provenance']['source_file'],q['provenance']['source_file_sha256']) for q in qs})]}
        if dataset=='cjeval':
            from app.datasets import source_manifest
            result[dataset]={**source_manifest(root,'cjeval'),'revision':first['revision'],
                             'selection':{'subject':'physics','stage':'junior','count':len(qs)}}
    return records,result
