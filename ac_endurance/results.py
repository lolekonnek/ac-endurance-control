"""Importer for completed classic AC server result JSON files."""
from __future__ import annotations
import hashlib, json, os, time, uuid
from pathlib import Path
from .server_manager import ServerManager
from .store import Store

def _first(obj,*keys,default=None):
    for key in keys:
        if key in obj: return obj[key]
    return default

def import_result(store:Store,path:Path)->bool:
    raw=path.read_bytes()
    if len(raw)>25*1024*1024: return False
    digest=hashlib.sha256(raw).hexdigest()
    if store.db.execute("SELECT 1 FROM result_sessions WHERE file_hash=?",(digest,)).fetchone(): return False
    data=json.loads(raw)
    if not isinstance(data,dict): return False
    rows=_first(data,"Result","result","Classification","classification",default=[])
    if not isinstance(rows,list): return False
    pepper=os.getenv("ACEC_GUID_PEPPER","").encode(); safe=json.loads(raw)
    # Do not retain GUIDs in result archives or the result file payload stored in SQLite.
    def redact(value):
        if isinstance(value,dict):
            for k,v in list(value.items()):
                if k.casefold() in {"driverguid","guid","steamid"} and isinstance(v,str):
                    value[k+"Hash"]=(hashlib.sha256(pepper+v.casefold().encode()).hexdigest()[:12] if pepper else None)
                    del value[k]
                else: redact(v)
        elif isinstance(value,list):
            for item in value: redact(item)
    redact(safe)
    sid=str(uuid.uuid4()); track=_first(data,"TrackName","track","Track",default=None); stype=_first(data,"Type","SessionType","type",default=None)
    store.db.execute("INSERT INTO result_sessions VALUES(?,?,?,?,?,?,?,?)",(sid,path.name,digest,time.time(),track,str(stype) if stype is not None else None,str(_first(data,"Date","date",default="")),json.dumps(safe,ensure_ascii=False)))
    for pos,item in enumerate(rows,1):
        if not isinstance(item,dict): continue
        guid=_first(item,"DriverGuid","driverGuid","guid",default="")
        gh=hashlib.sha256(pepper+str(guid).casefold().encode()).hexdigest() if pepper and guid else None
        driver=store.db.execute("SELECT id,team_id FROM drivers WHERE guid_hash=?",(gh,)).fetchone() if gh else None
        car_id=_first(item,"CarId","carId","car_id")
        lap_rows=data.get("Laps",data.get("laps",[]))
        lap_count=sum(1 for lap in lap_rows if isinstance(lap,dict) and _first(lap,"CarId","carId","car_id")==car_id) if isinstance(lap_rows,list) else None
        store.db.execute("INSERT OR IGNORE INTO result_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),sid,driver[0] if driver else None,driver[1] if driver else None,car_id,_first(item,"CarModel","carModel","car"),_first(item,"DriverName","driverName","name"),_first(item,"Position","position",default=pos),_first(item,"TotalTime","totalTime","time"),_first(item,"BestLap","bestLap","best_lap"),_first(item,"NumLaps","laps","LapCount",default=lap_count),_first(item,"PenaltyTime","penaltyTime"),_first(item,"LapPenalty","lapPenalty"),int(bool(_first(item,"Disqualified","disqualified",default=False)))))
    return True

async def monitor(store:Store,interval:float=10.0):
    import asyncio
    root=ServerManager().root/"results"; stable={}; next_cleanup=0.0
    while True:
        if time.time()>=next_cleanup:
            try: store.cleanup_replays(int(os.getenv("ACEC_REPLAY_RETENTION_DAYS","60")))
            except OSError: pass
            next_cleanup=time.time()+3600
        if root.is_dir():
            for path in root.glob("*.json"):
                try:
                    stat=path.stat(); stamp=(stat.st_size,stat.st_mtime_ns)
                    if stable.get(str(path))==stamp: import_result(store,path)
                    stable[str(path)]=stamp
                except (OSError,ValueError,json.JSONDecodeError): pass
        await asyncio.sleep(interval)
