"""Read exact handoff bytes from direct files or bounded lossless chunks."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri/source-match';SOURCE=MEDIA/'source'
def read_source(relative):
    path=SOURCE/relative
    if path.is_file():return path.read_bytes()
    record=json.loads((MEDIA/'SOURCE_STORAGE.json').read_text())['chunked'][relative]
    chunks=[]
    for part in record['parts']:
        data=(MEDIA/part['path']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=part['sha256']:raise ValueError('Changed source chunk: '+part['path'])
        chunks.append(data)
    data=b''.join(chunks)
    if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Reassembled source mismatch: '+relative)
    return data
