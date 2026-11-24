from __future__ import annotations
import mimetypes, os, re, time
from pathlib import Path
from .store import Store

MAX_CLIP_BYTES=250*1024*1024
ID_RE=re.compile(r"^[0-9a-f-]{36}$")

def save_uploaded_clip(store:Store,incident_id:str,filename:str,stream,content_length:int,claimant:str|None=None)->dict:
    if not ID_RE.fullmatch(incident_id): raise ValueError("Nieprawidłowy identyfikator incydentu")
    row=store.db.execute("SELECT status,claimed_by,claimed_at FROM replay_clips WHERE incident_id=?",(incident_id,)).fetchone()
    if not row or row[0]!="CLAIMED" or (claimant and row[1]!=claimant) or row[2]<time.time()-600: raise ValueError("Klip nie ma aktywnej rezerwacji")
    if content_length<=0 or content_length>MAX_CLIP_BYTES: raise ValueError("Klip musi mieć od 1 bajta do 250 MiB")
    suffix=Path(filename).suffix.lower()
    if suffix not in {".mp4",".mkv",".mov",".webm"}: raise ValueError("Nieobsługiwany format klipu")
    root=Path(os.getenv("ACEC_REPLAY_DIR","var/replays")); root.mkdir(parents=True,exist_ok=True)
    dest=root/(incident_id+suffix); tmp=dest.with_suffix(dest.suffix+".part")
    remaining=content_length
    try:
        with tmp.open("wb") as out:
            while remaining:
                chunk=stream.read(min(1024*1024,remaining))
                if not chunk: raise ValueError("Niekompletny upload klipu")
                out.write(chunk); remaining-=len(chunk)
            out.flush();os.fsync(out.fileno())
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp,dest)
    rel=os.path.relpath(dest,Path.cwd())
    now=time.time(); cur=store.db.execute("UPDATE replay_clips SET status='SAVED',relative_path=?,file_size=?,mime_type=?,updated_at=? WHERE incident_id=? AND status='CLAIMED'",(rel,content_length,mimetypes.guess_type(dest.name)[0] or "application/octet-stream",now,incident_id))
    if not cur.rowcount:
        dest.unlink(missing_ok=True); raise ValueError("Zadanie klipu zmieniło stan podczas uploadu")
    store.audit("replay-recorder","replay.attach","incident",incident_id,{"file_size":content_length,"format":suffix})
    return {"incident_id":incident_id,"status":"SAVED","file_size":content_length}
