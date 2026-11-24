"""OBS Replay Buffer worker running on the spectator PC, never on the headless AC server."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

LOG=logging.getLogger("acec.obs_recorder")

class Backend:
    def __init__(self,base:str,token:str): self.base=base.rstrip("/"); self.token=token
    def request(self,path:str,method="GET",data=None,content_type="application/json",headers=None):
        h={"Authorization":"Bearer "+self.token,"Content-Type":content_type,**(headers or {})}
        req=urllib.request.Request(self.base+path,data=data,headers=h,method=method)
        with urllib.request.urlopen(req,timeout=45) as res: return res.read(),res.headers
    def login(self):
        raw=json.dumps({"username":os.environ["ACEC_USERNAME"],"password":os.environ["ACEC_PASSWORD"]}).encode()
        req=urllib.request.Request(self.base+"/api/auth/login",data=raw,headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=20) as res: self.token=json.loads(res.read())["access_token"]

def field(obj,name): return obj.get(name) if isinstance(obj,dict) else getattr(obj,name,None)

def run():
    from obsws_python import ReqClient
    backend=Backend(os.environ["ACEC_API_URL"],"")
    backend.login()
    obs=ReqClient(host=os.getenv("OBS_HOST","127.0.0.1"),port=int(os.getenv("OBS_PORT","4455")),password=os.environ["OBS_PASSWORD"],timeout=10)
    worker=os.getenv("ACEC_RECORDER_ID",os.uname().nodename)
    post_seconds=max(0,int(os.getenv("ACEC_REPLAY_POST_SECONDS","20")))
    poll_seconds=max(1,int(os.getenv("ACEC_REPLAY_POLL_SECONDS","5")))
    max_bytes=250*1024*1024
    while True:
        try:
            if not field(obs.get_replay_buffer_status(),"output_active"):
                obs.start_replay_buffer(); LOG.info("Uruchomiono OBS Replay Buffer")
            raw,_=backend.request("/api/replay/pending")
            for item in json.loads(raw):
                incident_id=item["id"]
                if time.time()-float(item["created_at"])<post_seconds: continue
                try: backend.request(f"/api/replay/{incident_id}/claim","POST",b"{}")
                except urllib.error.HTTPError as e:
                    if e.code==409: continue
                    raise
                previous=field(obs.get_last_replay_buffer_replay(),"saved_replay_path")
                previous_mtime=Path(previous).stat().st_mtime_ns if previous and Path(previous).is_file() else 0
                obs.save_replay_buffer()
                saved=None; deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    time.sleep(.5)
                    candidate=field(obs.get_last_replay_buffer_replay(),"saved_replay_path")
                    if candidate and Path(candidate).is_file() and (candidate!=previous or Path(candidate).stat().st_mtime_ns>previous_mtime):
                        saved=candidate;break
                if not saved or not Path(saved).is_file():
                    backend.request(f"/api/replay/{incident_id}/miss","POST",json.dumps({"reason":"OBS nie zwrócił zapisanego pliku"}).encode()); LOG.warning("OBS nie zwrócił istniejącego pliku dla incydentu %s",incident_id); continue
                clip=Path(saved)
                size=clip.stat().st_size
                if size<=0 or size>max_bytes:
                    backend.request(f"/api/replay/{incident_id}/miss","POST",json.dumps({"reason":"Niedozwolony rozmiar klipu"}).encode()); LOG.warning("Klip %s ma niedozwolony rozmiar: %d",clip,size); continue
                with clip.open("rb") as f:
                    backend.request(f"/api/replay/{incident_id}/upload","POST",f.read(),"application/octet-stream",{"X-Filename":clip.name})
                LOG.info("Zapisano nagranie incydentu %s (%d B)",incident_id,size)
        except urllib.error.HTTPError as e:
            if e.code==401:
                try: backend.login()
                except Exception: LOG.exception("Ponowne logowanie do backendu nie powiodło się")
            else: LOG.exception("Błąd HTTP w recorderze: %s",e)
        except Exception:
            LOG.exception("Błąd OBS recorder; ponowię polling")
        time.sleep(poll_seconds)

if __name__=="__main__":
    logging.basicConfig(level=os.getenv("ACEC_LOG_LEVEL","INFO"),format="%(asctime)s %(levelname)s %(message)s")
    run()
