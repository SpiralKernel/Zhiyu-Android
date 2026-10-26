"""Normalize Android extension suffix for Chaquopy and regenerate wheel RECORD hashes."""
import base64,csv,hashlib,io,os,zipfile,json
from pathlib import Path

def normalize(path):
    with zipfile.ZipFile(path) as z:files={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
    for name in list(files):
        if name.startswith('pydantic_core/_pydantic_core.') and name.endswith('.so'):
            target='pydantic_core/_pydantic_core.cpython-312.so';files[target]=files.pop(name)
    record=next(n for n in files if n.endswith('.dist-info/RECORD'));files.pop(record)
    out=io.StringIO();writer=csv.writer(out,lineterminator='\n')
    for name,data in sorted(files.items()):writer.writerow([name,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('='),len(data)])
    writer.writerow([record,'','']);files[record]=out.getvalue().encode()
    temp=path.with_suffix('.tmp')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    os.replace(temp,path)
    return {'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]/'android/wheels'
    result=[normalize(p) for p in root.glob('*android_24*.whl')]
    (root/'checksums.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
