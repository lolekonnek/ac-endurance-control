from __future__ import annotations
import json, re, time, uuid
from wsgiref.simple_server import make_server
from .auth import login
from .store import Store

FLAGS={"GREEN","YELLOW","DOUBLE_YELLOW","BLUE","RED","WHITE","BLACK_WHITE","BLACK","CHEQUERED","SC","VSC","FCY"}
PENALTIES={"DRIVE_THROUGH","STOP_GO","TIME","WARNING","TRACK_LIMITS","UNSAFE_DRIVING","COLLISION","PIT","DRIVER_SWAP","DISQUALIFICATION"}
DECISIONS={"NEW","QUEUED","IN_REVIEW","NO_PENALTY","WARNING","PENALTY","CLOSED"}

def application(store: Store):
    def app(env, start_response):
        path,method=env.get("PATH_INFO","/"),env.get("REQUEST_METHOD","GET")
        status,payload="200 OK",{"service":"AC Endurance Control","language":"pl"}
        try:
            if path in {"/","/panel"} and method=="GET":
                from pathlib import Path
                page=(Path(__file__).resolve().parents[1]/"frontend"/"index.html").read_bytes()
                start_response("200 OK",[("Content-Type","text/html; charset=utf-8"),("Content-Length",str(len(page))),("Cache-Control","no-store"),("Content-Security-Policy","default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; media-src 'self' blob:; connect-src 'self' ws: wss:")])
                return [page]
            auth=env.get("HTTP_AUTHORIZATION","")
            user=store.user_for_token(auth[7:]) if auth.startswith("Bearer ") else None
            upload_match=re.fullmatch(r"/api/replay/([0-9a-f-]{36})/(upload|manual-upload)",path)
            if upload_match and method=="POST":
                require(user,{"admin","race_control","steward"})
                iid=upload_match.group(1); manual=upload_match.group(2)=="manual-upload"
                if manual and not store.claim_manual_replay(iid,user["id"]): raise ApiError(409,"Sprawa nie oczekuje na ręczny klip")
                length=int(env.get("CONTENT_LENGTH") or 0)
                from .replays import save_uploaded_clip
                try:
                    payload=save_uploaded_clip(store,iid,env.get("HTTP_X_FILENAME","clip.mp4"),env["wsgi.input"],length,user["id"])
                    if manual: store.audit(user["id"],"replay.manual_attach","incident",iid,{"file_size":length})
                except ValueError as exc:
                    if manual: store.db.execute("UPDATE replay_clips SET status='MISSED',updated_at=? WHERE incident_id=? AND claimed_by=?",(time.time(),iid,user["id"]))
                    raise ApiError(400,str(exc))
                data=json.dumps(payload).encode();start_response("201 Created",[("Content-Type","application/json"),("Content-Length",str(len(data))),("Cache-Control","no-store")]);return [data]
            length=int(env.get("CONTENT_LENGTH") or 0)
            if length>65536: raise ApiError(413,"Żądanie jest za duże")
            body=json.loads(env["wsgi.input"].read(length) or b"{}") if length else {}
            if path=="/api/health": payload={"status":"ok",**store.status()}
            elif path=="/api/server/status" and method=="GET":
                require(user,{"admin","race_control","steward"})
                from .server_manager import ServerManager
                payload=ServerManager().config()
            elif path=="/api/auth/login" and method=="POST":
                token=login(store,str(body.get("username","")),str(body.get("password","")))
                if not token: raise ApiError(401,"Dane logowania są nieprawidłowe")
                payload={"access_token":token,"token_type":"Bearer","expires_in":43200}
            elif path=="/api/auth/me" and method=="GET":
                if not user: raise ApiError(401,"Wymagane logowanie")
                payload={"id":user["id"],"username":user["username"],"role":user["role"],"driver_id":user["driver_id"],"team_id":user.get("team_id")}
            elif path=="/api/live" and method=="GET":
                race=store.live_state(); race["messages"]=[]
                payload=race
            elif path=="/api/results" and method=="GET":
                payload=[dict(r) for r in store.db.execute("SELECT id,source_file,imported_at,track,session_type,race_date FROM result_sessions ORDER BY imported_at DESC LIMIT 50")]
            elif path=="/api/live-timing" and method=="GET": payload=store.live_timing()
            elif path=="/api/laps" and method=="GET": payload=store.recent_laps()
            elif path=="/api/seasons" and method=="GET": payload=[dict(r) for r in store.db.execute("SELECT id,name,starts_at,ends_at FROM seasons ORDER BY created_at DESC")]
            elif path=="/api/seasons" and method=="POST":
                require(user,{"admin"}); name=str(body.get("name","")).strip()
                if not name or len(name)>100: raise ApiError(400,"Nazwa sezonu jest wymagana (maks. 100 znaków)")
                sid=str(uuid.uuid4()); store.db.execute("INSERT INTO seasons VALUES(?,?,?,?,?,?)",(sid,name,body.get("starts_at"),body.get("ends_at"),user["id"],time.time())); store.audit(user["id"],"season.create","season",sid,{"name":name}); status,payload="201 Created",{"id":sid,"name":name}
            elif path=="/api/events" and method=="GET": payload=[dict(r) for r in store.db.execute("SELECT id,season_id,name,track,track_config,duration_seconds,status,created_at,started_at,ended_at FROM events ORDER BY created_at DESC LIMIT 100")]
            elif path=="/api/events" and method=="POST":
                require(user,{"admin"}); name=str(body.get("name","")).strip(); track=str(body.get("track","")).strip(); duration=int(body.get("duration_seconds",0)); season=body.get("season_id") or None
                if not name or not track or len(name)>120 or duration<60 or duration>604800: raise ApiError(400,"Wymagana nazwa, tor i czas 60–604800 sekund")
                if season and not store.db.execute("SELECT 1 FROM seasons WHERE id=?",(season,)).fetchone(): raise ApiError(400,"Nie znaleziono sezonu")
                eid=str(uuid.uuid4()); rules=body.get("rules",{})
                store.db.execute("INSERT INTO events(id,season_id,name,track,track_config,duration_seconds,rules_json,status,created_by,created_at) VALUES(?,?,?,?,?,?,?,'DRAFT',?,?)",(eid,season,name,track,body.get("track_config"),duration,json.dumps(rules,ensure_ascii=False),user["id"],time.time()))
                store.audit(user["id"],"event.create","event",eid,{"name":name,"track":track,"duration_seconds":duration}); status,payload="201 Created",{"id":eid,"status":"DRAFT"}
            elif re.fullmatch(r"/api/events/[0-9a-f-]+/transition",path) and method=="POST":
                require(user,{"admin","race_control"}); eid=path.split("/")[3]; event=store.db.execute("SELECT * FROM events WHERE id=?",(eid,)).fetchone()
                if not event: raise ApiError(404,"Nie znaleziono wydarzenia")
                new=body.get("status"); allowed={"DRAFT":{"STAGING"},"STAGING":{"LIVE","DRAFT"},"LIVE":{"PAUSED","FINISHED"},"PAUSED":{"LIVE","FINISHED"},"FINISHED":set()}
                if new not in allowed.get(event["status"],set()): raise ApiError(409,"Niedozwolone przejście stanu wydarzenia")
                now=time.time(); started=event["started_at"] or (now if new=="LIVE" else None); ended=now if new=="FINISHED" else event["ended_at"]
                store.db.execute("UPDATE events SET status=?,started_at=?,ended_at=? WHERE id=?",(new,started,ended,eid))
                state=store.live_state(); state.update({"event_id":eid,"name":event["name"],"track":event["track"],"duration_seconds":event["duration_seconds"],"started_at":started,"status":new.lower(),"updated_at":now})
                store.db.execute("INSERT INTO app_state VALUES('race_state',?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",(json.dumps(state,ensure_ascii=False),now)); store.audit(user["id"],"event.transition","event",eid,{"from":event["status"],"to":new}); payload={"id":eid,"status":new,"started_at":started,"ended_at":ended}
            elif re.fullmatch(r"/api/results/[0-9a-f-]+",path) and method=="GET":
                sid=path.rsplit("/",1)[1]
                if not store.db.execute("SELECT 1 FROM result_sessions WHERE id=?",(sid,)).fetchone(): raise ApiError(404,"Nie znaleziono wyników")
                payload=[dict(r) for r in store.db.execute("SELECT e.position,e.car_model,e.driver_name,e.total_time,e.best_lap,e.laps,e.penalty_time,e.lap_penalty,e.disqualified,t.name AS team FROM result_entries e LEFT JOIN teams t ON t.id=e.team_id WHERE e.session_id=? ORDER BY e.position",(sid,))]
            elif path=="/api/teams" and method=="GET":
                payload=[dict(r) for r in store.db.execute("SELECT id,name,car_model,car_number,color,captain_driver_id FROM teams ORDER BY name")]
            elif path=="/api/drivers" and method=="GET":
                payload=[dict(r) for r in store.db.execute("SELECT d.id,d.nickname,d.team_id,t.name AS team FROM drivers d LEFT JOIN teams t ON t.id=d.team_id ORDER BY d.nickname")]
            elif path=="/api/teams" and method=="POST":
                require(user,{"admin"}); name=str(body.get("name","")).strip()
                if not name or len(name)>80: raise ApiError(400,"Nazwa zespołu jest wymagana (maks. 80 znaków)")
                tid=str(uuid.uuid4()); store.db.execute("INSERT INTO teams VALUES(?,?,?,?,?,?,?)",(tid,name,body.get("car_model"),body.get("car_number"),body.get("color"),None,time.time()))
                store.audit(user["id"],"team.create","team",tid,{"name":name}); status,payload="201 Created",{"id":tid,"name":name}
            elif path=="/api/drivers" and method=="POST":
                require(user,{"admin"}); nickname=str(body.get("nickname","")).strip(); guid=str(body.get("guid","")).strip(); team_id=body.get("team_id") or None
                pepper=__import__("os").getenv("ACEC_GUID_PEPPER","").encode()
                if not pepper: raise ApiError(503,"Administrator musi skonfigurować ACEC_GUID_PEPPER")
                if not nickname or len(nickname)>64 or not guid or len(guid)>128: raise ApiError(400,"Wymagany nick (maks. 64) i GUID (maks. 128)")
                if team_id and not store.db.execute("SELECT 1 FROM teams WHERE id=?",(team_id,)).fetchone(): raise ApiError(400,"Nie znaleziono zespołu")
                import hashlib
                did=str(uuid.uuid4()); gh=hashlib.sha256(pepper+guid.casefold().encode()).hexdigest()
                store.db.execute("INSERT INTO drivers VALUES(?,?,?,?,?)",(did,nickname,gh,team_id,time.time()))
                store.audit(user["id"],"driver.create","driver",did,{"nickname":nickname,"team_id":team_id}); status,payload="201 Created",{"id":did,"nickname":nickname,"team_id":team_id}
            elif path=="/api/control/state" and method=="POST":
                require(user,{"admin","race_control"}); state=store.live_state()
                if "flag" in body:
                    if body["flag"] not in FLAGS: raise ApiError(400,"Nieznany stan flagi")
                    state["flag"]=body["flag"]
                for key in ("message","next_driver","penalty"):
                    if key in body: state[key]=str(body[key])[:500]
                state["updated_at"]=time.time()
                store.db.execute("INSERT INTO app_state VALUES('race_state',?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",(json.dumps(state,ensure_ascii=False),time.time()))
                store.audit(user["id"],"race.state","race","active",state); payload=state
            elif path=="/api/control/messages" and method=="POST":
                require(user,{"admin","race_control"}); scope=body.get("scope","global"); team_id=body.get("team_id"); driver_id=body.get("driver_id"); text=str(body.get("body","")).strip()
                if scope not in {"global","team","driver"} or not text or len(text)>500: raise ApiError(400,"Nieprawidłowy zakres lub treść komunikatu")
                if scope=="team" and not store.db.execute("SELECT 1 FROM teams WHERE id=?",(team_id,)).fetchone(): raise ApiError(400,"Nie znaleziono zespołu")
                if scope=="driver" and not store.db.execute("SELECT 1 FROM drivers WHERE id=?",(driver_id,)).fetchone(): raise ApiError(400,"Nie znaleziono kierowcy")
                mid=str(uuid.uuid4()); store.db.execute("INSERT INTO race_messages VALUES(?,?,?,?,?,?,?)",(mid,time.time(),user["id"],scope,team_id if scope=="team" else None,driver_id if scope=="driver" else None,text))
                store.audit(user["id"],"message.send","message",mid,{"scope":scope}); status,payload="201 Created",{"id":mid,"scope":scope}
            elif path=="/api/team/messages" and method=="GET":
                require(user,{"admin","race_control","captain","driver"})
                team_id=body.get("team_id") if user["role"] in {"admin","race_control"} else user.get("team_id")
                payload=[dict(r) for r in store.db.execute("SELECT m.id,m.created_at,m.scope,m.body,COALESCE(d.nickname,u.username,'Dyrekcja') AS author FROM race_messages m LEFT JOIN drivers d ON d.id=m.author_id LEFT JOIN users u ON u.id=m.author_id WHERE m.scope='team' AND m.team_id=? ORDER BY m.created_at DESC LIMIT 100",(team_id,))]
            elif path=="/api/team/messages" and method=="POST":
                require(user,{"admin","race_control","captain"}); team_id=body.get("team_id") or user.get("team_id"); text=str(body.get("body","")).strip()
                if user["role"]=="captain" and team_id!=user.get("team_id"): raise ApiError(403,"Kapitan może pisać tylko do swojego zespołu")
                if not team_id or not text or len(text)>300: raise ApiError(400,"Wymagany zespół i treść do 300 znaków")
                mid=str(uuid.uuid4()); store.db.execute("INSERT INTO race_messages VALUES(?,?,?,?,?,?,?)",(mid,time.time(),user["id"],"team",team_id,None,text)); store.audit(user["id"],"team.message","message",mid,{"team_id":team_id}); status,payload="201 Created",{"id":mid}
            elif path=="/api/incidents" and method=="GET":
                require(user,{"admin","race_control","steward"})
                payload=[dict(r) for r in store.db.execute("SELECT i.*,d.nickname,d.team_id,c.status AS clip_status FROM incident_reports i JOIN drivers d ON d.id=i.driver_id LEFT JOIN replay_clips c ON c.incident_id=i.id ORDER BY i.created_at DESC LIMIT 300")]
                for row in payload: row["telemetry"]=json.loads(row.pop("telemetry_json"))
                for row in payload: row["clip_url"]=f"/api/replay/{row['id']}/video" if row.get("clip_status")=="SAVED" else None
            elif path=="/api/replay/pending" and method=="GET":
                require(user,{"admin","race_control","steward"}); payload=store.pending_replays()
            elif re.fullmatch(r"/api/replay/[0-9a-f-]{36}/claim",path) and method=="POST":
                require(user,{"admin","race_control","steward"}); iid=path.split("/")[3]
                if not store.claim_replay(iid,user["id"]): raise ApiError(409,"Klip został już przejęty lub nie istnieje")
                store.audit(user["id"],"replay.claim","incident",iid,{}); payload={"incident_id":iid,"status":"CLAIMED"}
            elif re.fullmatch(r"/api/replay/[0-9a-f-]{36}/miss",path) and method=="POST":
                require(user,{"admin","race_control","steward"}); iid=path.split("/")[3]
                cur=store.db.execute("UPDATE replay_clips SET status='MISSED',updated_at=? WHERE incident_id=? AND status='CLAIMED' AND claimed_by=?",(time.time(),iid,user["id"]))
                if not cur.rowcount: raise ApiError(409,"Zadanie nie należy do tego operatora")
                store.audit(user["id"],"replay.missed","incident",iid,{"reason":str(body.get("reason",""))[:200]}); payload={"incident_id":iid,"status":"MISSED"}
            elif re.fullmatch(r"/api/replay/[0-9a-f-]{36}/video",path) and method=="GET":
                require(user,{"admin","race_control","steward"}); iid=path.split("/")[3]
                row=store.db.execute("SELECT relative_path,mime_type,file_size FROM replay_clips WHERE incident_id=? AND status='SAVED'",(iid,)).fetchone()
                if not row: raise ApiError(404,"Nie znaleziono klipu")
                from pathlib import Path
                video=(Path.cwd()/row[0]).resolve(); root=Path(__import__("os").getenv("ACEC_REPLAY_DIR","var/replays")).resolve()
                if root not in video.parents or not video.is_file(): raise ApiError(404,"Plik klipu jest niedostępny")
                size=video.stat().st_size;start=0;end=size-1;code="200 OK";rng=env.get("HTTP_RANGE","")
                if rng:
                    m=re.fullmatch(r"bytes=(\d+)-(\d*)",rng)
                    if not m: raise ApiError(416,"Nieobsługiwany zakres klipu")
                    start=int(m.group(1));end=min(int(m.group(2)) if m.group(2) else end,end)
                    if start>end or start>=size: raise ApiError(416,"Zakres klipu poza rozmiarem pliku")
                    code="206 Partial Content"
                length=end-start+1
                def chunks():
                    with video.open("rb") as f:
                        f.seek(start);left=length
                        while left:
                            part=f.read(min(1024*1024,left))
                            if not part: break
                            left-=len(part);yield part
                headers=[("Content-Type",row[1] or "video/mp4"),("Content-Length",str(length)),("Accept-Ranges","bytes"),("Cache-Control","private, no-store"),("X-Content-Type-Options","nosniff")]
                if code.startswith("206"): headers.append(("Content-Range",f"bytes {start}-{end}/{size}"))
                start_response(code,headers);return chunks()
            elif re.fullmatch(r"/api/incidents/[0-9a-f-]+",path) and method=="PATCH":
                require(user,{"admin","race_control","steward"}); iid=path.rsplit("/",1)[1]; decision=body.get("status")
                if decision not in DECISIONS: raise ApiError(400,"Nieznana decyzja")
                cur=store.db.execute("UPDATE incident_reports SET status=? WHERE id=?",(decision,iid))
                if not cur.rowcount: raise ApiError(404,"Nie znaleziono incydentu")
                store.audit(user["id"],"incident.decision","incident",iid,{"status":decision,"comment":str(body.get("comment",""))[:500]}); payload={"id":iid,"status":decision}
            elif path=="/api/penalties" and method=="GET":
                require(user,{"admin","race_control","steward"}); payload=[dict(r) for r in store.db.execute("SELECT * FROM penalties ORDER BY created_at DESC LIMIT 300")]
            elif path=="/api/penalties" and method=="POST":
                require(user,{"admin","race_control","steward"}); kind=body.get("kind"); reason=str(body.get("reason","")).strip(); did=body.get("driver_id") or None
                if kind not in PENALTIES or not reason: raise ApiError(400,"Rodzaj kary i powód są wymagane")
                if did and not store.db.execute("SELECT 1 FROM drivers WHERE id=?",(did,)).fetchone(): raise ApiError(400,"Nie znaleziono kierowcy")
                pid=str(uuid.uuid4()); store.db.execute("INSERT INTO penalties VALUES(?,?,?,?,?,?,?,?,?,?,?)",(pid,time.time(),user["id"],did,body.get("team_id"),body.get("car_number"),kind,reason,str(body.get("evidence",""))[:1000],"ACTIVE",time.time()))
                store.audit(user["id"],"penalty.create","penalty",pid,{"kind":kind,"reason":reason}); status,payload="201 Created",{"id":pid,"status":"ACTIVE"}
            elif re.fullmatch(r"/api/penalties/[0-9a-f-]+",path) and method=="PATCH":
                require(user,{"admin","race_control","steward"}); pid=path.rsplit("/",1)[1]; state=body.get("status")
                if state not in {"ACTIVE","SERVED","CANCELLED","MODIFIED"}: raise ApiError(400,"Nieprawidłowy status kary")
                cur=store.db.execute("UPDATE penalties SET status=?,reason=COALESCE(?,reason),updated_at=? WHERE id=?",(state,body.get("reason"),time.time(),pid))
                if not cur.rowcount: raise ApiError(404,"Nie znaleziono kary")
                store.audit(user["id"],"penalty.update","penalty",pid,{"status":state,"reason":body.get("reason")}); payload={"id":pid,"status":state}
            elif path=="/api/pit-stops" and method=="GET":
                require(user,{"admin","race_control","steward","captain"})
                if user["role"]=="captain": payload=[dict(r) for r in store.db.execute("SELECT * FROM pit_stops WHERE team_id=? ORDER BY entered_at DESC LIMIT 100",(user.get("team_id"),))]
                else: payload=[dict(r) for r in store.db.execute("SELECT * FROM pit_stops ORDER BY entered_at DESC LIMIT 300")]
                for stop in payload: stop["verified"]=stop["source"]!="client_unverified"
            elif path=="/api/swaps" and method=="POST":
                require(user,{"admin","race_control","captain"}); team_id=body.get("team_id"); to_id=body.get("to_driver_id"); from_id=body.get("from_driver_id") or None
                if user["role"]=="captain" and user.get("team_id")!=team_id: raise ApiError(403,"Kapitan może planować zmiany wyłącznie dla swojego zespołu")
                if not store.db.execute("SELECT 1 FROM drivers WHERE id=? AND team_id=?",(to_id,team_id)).fetchone(): raise ApiError(400,"Kierowca docelowy nie należy do zespołu")
                if from_id and not store.db.execute("SELECT 1 FROM drivers WHERE id=? AND team_id=?",(from_id,team_id)).fetchone(): raise ApiError(400,"Kierowca bieżący nie należy do zespołu")
                when=float(body.get("scheduled_at",time.time())); sid=str(uuid.uuid4())
                store.db.execute("INSERT INTO driver_swaps VALUES(?,?,?,?,?,?,?,?)",(sid,team_id,from_id,to_id,when,user["id"],"PLANNED",str(body.get("note",""))[:300]))
                store.audit(user["id"],"swap.plan","driver_swap",sid,{"team_id":team_id,"to_driver_id":to_id,"scheduled_at":when,"warning":"Harmonogram nie przełącza auta w grze"}); status,payload="201 Created",{"id":sid,"status":"PLANNED","game_swap_executed":False}
            else: raise ApiError(404,"Nie znaleziono zasobu")
        except ApiError as e: status,payload=f"{e.status} {http_reason(e.status)}",{"error":str(e)}
        except (ValueError,TypeError,json.JSONDecodeError) as e: status,payload="400 Bad Request",{"error":str(e)}
        except Exception as e:
            if "UNIQUE" in str(e): status,payload="409 Conflict",{"error":"Rekord o takiej wartości już istnieje"}
            else: status,payload="500 Internal Server Error",{"error":"Błąd wewnętrzny"}
        data=json.dumps(payload,ensure_ascii=False,default=str).encode()
        start_response(status,[("Content-Type","application/json; charset=utf-8"),("Content-Length",str(len(data))),("Cache-Control","no-store"),("X-Content-Type-Options","nosniff")])
        return [data]
    return app

class ApiError(Exception):
    def __init__(self,status:int,message:str): self.status=status; super().__init__(message)

def require(user,roles):
    if not user: raise ApiError(401,"Wymagane logowanie")
    if user["role"] not in roles: raise ApiError(403,"Brak uprawnień")

def http_reason(status): return {400:"Bad Request",401:"Unauthorized",403:"Forbidden",404:"Not Found",413:"Payload Too Large",503:"Service Unavailable"}.get(status,"Error")

def serve(store: Store,host:str,port:int):
    with make_server(host,port,application(store)) as server: server.serve_forever()
