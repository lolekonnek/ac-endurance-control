from __future__ import annotations
import hashlib, json, sqlite3, time, uuid
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS raw_events(id TEXT PRIMARY KEY, received_at REAL NOT NULL, source TEXT NOT NULL, packet_id INTEGER, payload BLOB NOT NULL, parsed_json TEXT, dedupe_key TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS teams(id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, car_model TEXT, car_number INTEGER, color TEXT, captain_driver_id TEXT, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS drivers(id TEXT PRIMARY KEY, nickname TEXT NOT NULL, guid_hash TEXT UNIQUE, team_id TEXT REFERENCES teams(id), created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS laps(id TEXT PRIMARY KEY, event_key TEXT NOT NULL UNIQUE, car_id INTEGER NOT NULL, lap_ms INTEGER NOT NULL, cuts INTEGER NOT NULL, received_at REAL NOT NULL, payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY, created_at REAL NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT, details_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS app_state(key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS client_tokens(token_hash TEXT PRIMARY KEY, driver_id TEXT NOT NULL REFERENCES drivers(id), created_at REAL NOT NULL, revoked_at REAL);
CREATE TABLE IF NOT EXISTS incident_reports(id TEXT PRIMARY KEY, driver_id TEXT NOT NULL REFERENCES drivers(id), created_at REAL NOT NULL, category TEXT NOT NULL, note TEXT NOT NULL, telemetry_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'NEW');
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_salt BLOB NOT NULL, password_hash BLOB NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','race_control','steward','captain','driver','viewer')), driver_id TEXT REFERENCES drivers(id), created_at REAL NOT NULL, disabled INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS user_sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), created_at REAL NOT NULL, expires_at REAL NOT NULL, revoked_at REAL);
CREATE TABLE IF NOT EXISTS race_messages(id TEXT PRIMARY KEY, created_at REAL NOT NULL, author_id TEXT NOT NULL, scope TEXT NOT NULL, team_id TEXT, driver_id TEXT, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS penalties(id TEXT PRIMARY KEY, created_at REAL NOT NULL, author_id TEXT NOT NULL, driver_id TEXT, team_id TEXT, car_number INTEGER, kind TEXT NOT NULL, reason TEXT NOT NULL, evidence TEXT, status TEXT NOT NULL DEFAULT 'ACTIVE', updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS driver_swaps(id TEXT PRIMARY KEY, team_id TEXT NOT NULL REFERENCES teams(id), from_driver_id TEXT REFERENCES drivers(id), to_driver_id TEXT NOT NULL REFERENCES drivers(id), scheduled_at REAL NOT NULL, created_by TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PLANNED', note TEXT NOT NULL DEFAULT '', updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS pit_stops(id TEXT PRIMARY KEY, team_id TEXT, driver_id TEXT, car_number INTEGER, entered_at REAL NOT NULL, exited_at REAL, source TEXT NOT NULL, note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS server_cars(car_id INTEGER PRIMARY KEY, driver_id TEXT REFERENCES drivers(id), guid_hash TEXT, connected INTEGER NOT NULL DEFAULT 1, observed_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS result_sessions(id TEXT PRIMARY KEY, source_file TEXT NOT NULL, file_hash TEXT NOT NULL UNIQUE, imported_at REAL NOT NULL, track TEXT, session_type TEXT, race_date TEXT, raw_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS result_entries(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES result_sessions(id), driver_id TEXT REFERENCES drivers(id), team_id TEXT REFERENCES teams(id), car_id INTEGER, car_model TEXT, driver_name TEXT, position INTEGER, total_time INTEGER, best_lap INTEGER, laps INTEGER, penalty_time INTEGER, lap_penalty INTEGER, disqualified INTEGER NOT NULL DEFAULT 0, UNIQUE(session_id,car_id,driver_name));
CREATE TABLE IF NOT EXISTS live_standings(car_id INTEGER PRIMARY KEY, position INTEGER NOT NULL, laps INTEGER NOT NULL DEFAULT 0, last_lap_ms INTEGER, best_lap_ms INTEGER, cuts INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS seasons(id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, starts_at REAL, ends_at REAL, created_by TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, season_id TEXT REFERENCES seasons(id), name TEXT NOT NULL, track TEXT NOT NULL, track_config TEXT, duration_seconds INTEGER NOT NULL, rules_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'DRAFT', created_by TEXT NOT NULL, created_at REAL NOT NULL, started_at REAL, ended_at REAL);
CREATE TABLE IF NOT EXISTS driver_stints(id TEXT PRIMARY KEY, driver_id TEXT NOT NULL REFERENCES drivers(id), team_id TEXT REFERENCES teams(id), car_id INTEGER NOT NULL, started_at REAL NOT NULL, ended_at REAL, start_lap INTEGER NOT NULL DEFAULT 0, end_lap INTEGER, source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS replay_clips(incident_id TEXT PRIMARY KEY REFERENCES incident_reports(id), status TEXT NOT NULL DEFAULT 'PENDING', claimed_by TEXT, claimed_at REAL, relative_path TEXT, file_size INTEGER, mime_type TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
"""

class Store:
    def __init__(self, filename: str):
        self.path = Path(filename); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row; self.db.executescript(SCHEMA)
    def ingest(self, raw: bytes, parsed: dict[str, Any], source: str) -> bool:
        now = time.time(); key = None
        safe=dict(parsed)
        guid=safe.pop("driver_guid",None)
        guid_hash=None
        if guid:
            import os
            pepper=os.getenv("ACEC_GUID_PEPPER","").encode()
            if pepper: guid_hash=hashlib.sha256(pepper+guid.strip().casefold().encode()).hexdigest()
            safe["driver_guid_redacted"]=True
            safe["guid_hash"] = guid_hash[:12] if guid_hash else None
        if parsed["type"] == "lap_completed":
            current=self.db.execute("SELECT value_json FROM app_state WHERE key='ac_session_id'").fetchone()
            session_id=current[0] if current else "unscoped"
            lap_seq=next((x["laps"] for x in parsed.get("leaderboard",[]) if x["car_id"]==parsed["car_id"]),None)
            identity=f"{session_id}:{parsed['car_id']}:{lap_seq}" if lap_seq is not None else f"{session_id}:{parsed['car_id']}:{hashlib.sha256(raw).hexdigest()}:{int(now//5)}"
            key=hashlib.sha256(identity.encode()).hexdigest()
        elif parsed["type"] in ("new_session", "end_session"):
            key = hashlib.sha256(raw + str(int(now // 2)).encode()).hexdigest()
        eid = str(uuid.uuid4())
        # AC connection packets contain Steam GUID in clear text. Keep a packet digest instead of the credential-bearing datagram.
        stored_raw=(b"REDACTED:"+hashlib.sha256(raw).hexdigest().encode()) if guid else raw
        try:
            self.db.execute("INSERT INTO raw_events VALUES(?,?,?,?,?,?,?)", (eid,now,source,parsed["packet_id"],stored_raw,json.dumps(safe,ensure_ascii=False),key))
        except sqlite3.IntegrityError:
            return False
        if parsed["type"] == "lap_completed":
            self.db.execute("INSERT OR IGNORE INTO laps VALUES(?,?,?,?,?,?,?)", (str(uuid.uuid4()),key,parsed["car_id"],parsed["lap_ms"],parsed["cuts"],now,json.dumps(parsed,ensure_ascii=False)))
            leaderboard=parsed.get("leaderboard",[])
            for position,entry in enumerate(leaderboard,1):
                car_id=entry["car_id"]
                old=self.db.execute("SELECT best_lap_ms FROM live_standings WHERE car_id=?",(car_id,)).fetchone()
                best=min([x for x in ((old[0] if old else None),(parsed["lap_ms"] if car_id==parsed["car_id"] else None)) if x and x>0],default=None)
                lap_time=parsed["lap_ms"] if car_id==parsed["car_id"] else None
                cuts=parsed["cuts"] if car_id==parsed["car_id"] else 0
                self.db.execute("INSERT INTO live_standings VALUES(?,?,?,?,?,?,?) ON CONFLICT(car_id) DO UPDATE SET position=excluded.position,laps=MAX(live_standings.laps,excluded.laps),last_lap_ms=CASE WHEN excluded.car_id=? THEN excluded.last_lap_ms ELSE live_standings.last_lap_ms END,best_lap_ms=CASE WHEN live_standings.best_lap_ms IS NULL OR excluded.best_lap_ms<live_standings.best_lap_ms THEN excluded.best_lap_ms ELSE live_standings.best_lap_ms END,cuts=live_standings.cuts+excluded.cuts,updated_at=excluded.updated_at",(car_id,position,entry["laps"],lap_time,best,cuts,now,parsed["car_id"]))
        elif parsed["type"] in ("new_connection","car_info") and guid:
            match=self.db.execute("SELECT id FROM drivers WHERE guid_hash=?",(guid_hash,)).fetchone() if guid_hash else None
            self.db.execute("INSERT INTO server_cars(car_id,driver_id,guid_hash,connected,observed_at) VALUES(?,?,?,?,?) ON CONFLICT(car_id) DO UPDATE SET driver_id=excluded.driver_id,guid_hash=excluded.guid_hash,connected=1,observed_at=excluded.observed_at",(parsed["car_id"],match[0] if match else None,guid_hash,1,now))
            if parsed["type"]=="new_connection" and match:
                active=self.db.execute("SELECT id,driver_id FROM driver_stints WHERE car_id=? AND ended_at IS NULL",(parsed["car_id"],)).fetchone()
                if not active or active["driver_id"]!=match[0]:
                    self.db.execute("UPDATE driver_stints SET ended_at=?,end_lap=COALESCE((SELECT laps FROM live_standings WHERE car_id=?),start_lap) WHERE car_id=? AND ended_at IS NULL",(now,parsed["car_id"],parsed["car_id"]))
                    team=self.db.execute("SELECT team_id FROM drivers WHERE id=?",(match[0],)).fetchone()
                    lap=self.db.execute("SELECT laps FROM live_standings WHERE car_id=?",(parsed["car_id"],)).fetchone()
                    self.db.execute("INSERT INTO driver_stints VALUES(?,?,?,?,?,NULL,?,NULL,'udp_connection')",(str(uuid.uuid4()),match[0],team[0] if team else None,parsed["car_id"],now,lap[0] if lap else 0))
        elif parsed["type"] == "connection_closed":
            self.db.execute("UPDATE server_cars SET connected=0,observed_at=? WHERE car_id=?",(now,parsed["car_id"]))
            self.db.execute("UPDATE driver_stints SET ended_at=?,end_lap=COALESCE((SELECT laps FROM live_standings WHERE car_id=?),start_lap) WHERE car_id=? AND ended_at IS NULL",(now,parsed["car_id"],parsed["car_id"]))
        elif parsed["type"] == "new_session":
            self.db.execute("DELETE FROM server_cars")
            self.db.execute("DELETE FROM live_standings")
            self.db.execute("UPDATE driver_stints SET ended_at=?,end_lap=COALESCE(end_lap,start_lap) WHERE ended_at IS NULL",(now,))
            self.db.execute("INSERT INTO app_state VALUES('ac_session_id',?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",(str(uuid.uuid4()),now))
        elif parsed["type"] == "client_event" and parsed.get("event_type") in (10,11):
            car_ids={parsed["car_id"]}
            if parsed.get("event_type")==10: car_ids.add(parsed.get("other_car_id"))
            for car_id in car_ids:
                row=self.db.execute("SELECT driver_id FROM server_cars WHERE car_id=?",(car_id,)).fetchone()
                if row and row[0]:
                    self.report_incident(row[0],"collision_signal","Automatyczny sygnał kolizji z UDP; wymaga oceny sędziego",{"car_id":car_id,"other_car_id":parsed.get("other_car_id"),"speed":parsed.get("speed"),"world_position":parsed.get("world_position"),"relative_position":parsed.get("relative_position"),"source":"ac_udp"})
        return True
    def status(self) -> dict[str, Any]:
        return {"database": "ok", "raw_events": self.db.execute("SELECT count(*) FROM raw_events").fetchone()[0],
                "laps": self.db.execute("SELECT count(*) FROM laps").fetchone()[0]}
    def audit(self, actor: str, action: str, obj: str, obj_id: str | None, details: dict[str, Any]):
        self.db.execute("INSERT INTO audit VALUES(?,?,?,?,?,?,?)", (str(uuid.uuid4()),time.time(),actor,action,obj,obj_id,json.dumps(details,ensure_ascii=False)))
    def client_context(self, token_hash: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT d.id AS driver_id,d.nickname,d.team_id,t.name AS team,t.car_number,t.car_model,t.color FROM client_tokens c JOIN drivers d ON d.id=c.driver_id LEFT JOIN teams t ON t.id=d.team_id WHERE c.token_hash=? AND c.revoked_at IS NULL", (token_hash,)).fetchone()
        return dict(row) if row else None
    def user_for_token(self, token: str) -> dict[str, Any] | None:
        digest=hashlib.sha256(token.encode()).hexdigest()
        row=self.db.execute("SELECT u.id,u.username,u.role,u.driver_id,d.team_id,s.expires_at FROM user_sessions s JOIN users u ON u.id=s.user_id LEFT JOIN drivers d ON d.id=u.driver_id WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>? AND u.disabled=0",(digest,time.time())).fetchone()
        return dict(row) if row else None
    def client_messages(self, driver_id: str, team_id: str | None) -> list[dict[str, Any]]:
        rows=self.db.execute("SELECT m.id,m.created_at,m.scope,m.body,COALESCE(d.nickname,u.username,'Dyrekcja') AS author FROM race_messages m LEFT JOIN drivers d ON d.id=m.author_id LEFT JOIN users u ON u.id=m.author_id WHERE m.scope='global' OR m.driver_id=? OR (m.scope='team' AND m.team_id=?) ORDER BY m.created_at DESC LIMIT 10",(driver_id,team_id)).fetchall()
        return [dict(r) for r in rows]
    def client_penalties(self, driver_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT id,kind,reason,status,created_at FROM penalties WHERE driver_id=? AND status='ACTIVE' ORDER BY created_at DESC LIMIT 5",(driver_id,)).fetchall()]
    def client_next_swap(self, team_id: str | None) -> dict[str, Any] | None:
        if not team_id: return None
        row=self.db.execute("SELECT s.scheduled_at,d.nickname FROM driver_swaps s JOIN drivers d ON d.id=s.to_driver_id WHERE s.team_id=? AND s.status='PLANNED' AND s.scheduled_at>? ORDER BY s.scheduled_at LIMIT 1",(team_id,time.time())).fetchone()
        return dict(row) if row else None
    def client_stint(self, driver_id: str) -> dict[str, Any] | None:
        row=self.db.execute("SELECT started_at,car_id FROM driver_stints WHERE driver_id=? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",(driver_id,)).fetchone()
        return dict(row) if row else None
    def live_timing(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT l.car_id,l.position,l.laps,l.last_lap_ms,l.best_lap_ms,l.cuts,s.driver_id,d.nickname,d.team_id,t.name AS team,t.car_number,t.car_model FROM live_standings l LEFT JOIN server_cars s ON s.car_id=l.car_id LEFT JOIN drivers d ON d.id=s.driver_id LEFT JOIN teams t ON t.id=d.team_id ORDER BY l.position")]
    def recent_laps(self,limit:int=20) -> list[dict[str,Any]]:
        return [dict(r) for r in self.db.execute("SELECT l.car_id,l.lap_ms,l.cuts,l.received_at,s.driver_id,d.nickname,t.name AS team FROM laps l LEFT JOIN server_cars s ON s.car_id=l.car_id LEFT JOIN drivers d ON d.id=s.driver_id LEFT JOIN teams t ON t.id=d.team_id ORDER BY l.received_at DESC LIMIT ?",(limit,))]
    def record_pit_transition(self, driver_id: str, team_id: str | None, car_number: int | None, entering: bool, note: str=""):
        now=time.time()
        if entering:
            existing=self.db.execute("SELECT id FROM pit_stops WHERE driver_id=? AND exited_at IS NULL ORDER BY entered_at DESC LIMIT 1",(driver_id,)).fetchone()
            if existing: return existing[0]
            pid=str(uuid.uuid4()); self.db.execute("INSERT INTO pit_stops VALUES(?,?,?,?,?,?,?,?)",(pid,team_id,driver_id,car_number,now,None,"client_unverified",note[:200])); return pid
        row=self.db.execute("SELECT id FROM pit_stops WHERE driver_id=? AND exited_at IS NULL ORDER BY entered_at DESC LIMIT 1",(driver_id,)).fetchone()
        if not row: return None
        self.db.execute("UPDATE pit_stops SET exited_at=?,note=CASE WHEN ?='' THEN note ELSE ? END WHERE id=?",(now,note,note[:200],row[0])); return row[0]
    def live_state(self) -> dict[str, Any]:
        row = self.db.execute("SELECT value_json FROM app_state WHERE key='race_state'").fetchone()
        return json.loads(row[0]) if row else {"status":"offline","flag":"GREEN","message":"Brak aktywnego wydarzenia"}
    def report_incident(self, driver_id: str, category: str, note: str, telemetry: dict[str, Any]) -> str:
        incident_id=str(uuid.uuid4())
        now=time.time()
        self.db.execute("INSERT INTO incident_reports(id,driver_id,created_at,category,note,telemetry_json) VALUES(?,?,?,?,?,?)", (incident_id,driver_id,now,category[:40],note[:500],json.dumps(telemetry,ensure_ascii=False)))
        self.db.execute("INSERT INTO replay_clips(incident_id,status,created_at,updated_at) VALUES(?,'PENDING',?,?)",(incident_id,now,now))
        self.audit(driver_id,"incident.report","incident",incident_id,{"category":category[:40]})
        return incident_id
    def pending_replays(self,limit:int=30,lease_seconds:int=600) -> list[dict[str,Any]]:
        cutoff=time.time()-lease_seconds
        return [dict(r) for r in self.db.execute("SELECT i.id,i.created_at,i.category,i.note FROM incident_reports i JOIN replay_clips c ON c.incident_id=i.id WHERE c.status='PENDING' OR (c.status='CLAIMED' AND c.claimed_at<?) ORDER BY i.created_at LIMIT ?",(cutoff,limit))]
    def claim_replay(self,incident_id:str,worker:str,lease_seconds:int=600)->bool:
        now=time.time()
        cur=self.db.execute("UPDATE replay_clips SET status='CLAIMED',claimed_by=?,claimed_at=?,updated_at=? WHERE incident_id=? AND (status='PENDING' OR (status='CLAIMED' AND claimed_at<?))",(worker,now,now,incident_id,now-lease_seconds))
        return cur.rowcount==1
    def claim_manual_replay(self,incident_id:str,worker:str)->bool:
        now=time.time()
        cur=self.db.execute("UPDATE replay_clips SET status='CLAIMED',claimed_by=?,claimed_at=?,updated_at=? WHERE incident_id=? AND status IN ('PENDING','MISSED')",(worker,now,now,incident_id))
        return cur.rowcount==1
    def cleanup_replays(self,retention_days:int=60)->int:
        from pathlib import Path
        cutoff=time.time()-max(1,retention_days)*86400
        rows=self.db.execute("SELECT incident_id,relative_path FROM replay_clips WHERE status='SAVED' AND created_at<?",(cutoff,)).fetchall()
        root=Path(__import__("os").getenv("ACEC_REPLAY_DIR","var/replays")).resolve()
        for row in rows:
            if row[1]:
                path=(Path.cwd()/row[1]).resolve()
                if root in path.parents: path.unlink(missing_ok=True)
            self.db.execute("UPDATE replay_clips SET status='EXPIRED',relative_path=NULL,updated_at=? WHERE incident_id=?",(time.time(),row[0]))
        return len(rows)
