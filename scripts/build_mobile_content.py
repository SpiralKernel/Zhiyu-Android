"""Export only current practice content; sign mobile bank releases independently of learner DBs."""
import argparse,gzip,hashlib,json,sqlite3,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.mobile_content import canonical
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
import base64

def build(db_path,output,version,key_path,public_path):
    output.mkdir(parents=True,exist_ok=True)
    if not key_path.exists():
        key_path.parent.mkdir(parents=True,exist_ok=True);key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        with key_path.open('xb') as f:os.chmod(key_path,0o600);f.write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    key=serialization.load_pem_private_key(key_path.read_bytes(),None)
    pub=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    if public_path.exists() and public_path.read_bytes()!=pub:raise ValueError('签名密钥与固定公钥不同')
    public_path.write_bytes(pub)
    c=sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro',uri=True)
    rows=list(c.execute("SELECT * FROM bank_questions WHERE status!='superseded' AND json_extract(data,'$.can_practice')=1 ORDER BY id"))
    source_ids={x[1] for x in rows};tags={t['id'] for x in rows for t in json.loads(x[8]).get('tags',[])}
    path=output/f'bank-{version}.jsonl.gz'
    with path.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as f:
        def emit(v):f.write(json.dumps(v,ensure_ascii=False).encode()+b'\n')
        for row in c.execute('SELECT * FROM bank_sources ORDER BY id'):
            if row[0] in source_ids:emit({'kind':'source','row':list(row)})
        for row in c.execute('SELECT * FROM bank_taxonomy ORDER BY id'):
            if row[0] in tags:emit({'kind':'tag','row':list(row)})
        for row in rows:emit({'kind':'question','row':list(row)})
        row=c.execute("SELECT value FROM content_meta WHERE key='bank_pruned_content_v1'").fetchone()
        emit({'kind':'retired','hashes':json.loads(row[0]) if row else []})
    value={'schema':1,'version':version,'count':len(rows),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    value['signature']=base64.b64encode(key.sign(canonical(value),padding.PKCS1v15(),hashes.SHA256())).decode()
    (output/'manifest.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({k:v for k,v in value.items() if k!='signature'}));c.close();return value
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,default=Path('data/ai-teacher.sqlite3'));p.add_argument('--output',type=Path,required=True);p.add_argument('--version',type=int,required=True);p.add_argument('--private-key',type=Path,default=Path('data/mobile-signing/private.pem'));p.add_argument('--public-key',type=Path,default=Path('app/data/mobile-bank-public.pem'));a=p.parse_args();build(a.db,a.output,a.version,a.private_key,a.public_key)
