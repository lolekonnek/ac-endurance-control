import io, json, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
from ac_endurance.auth import create_user
from ac_endurance.store import Store
from ac_endurance.web import application

def call(app,path,method="GET",body=None,token="",raw=None,headers=None):
    data=raw if raw is not None else json.dumps(body or {}).encode(); env={"PATH_INFO":path,"REQUEST_METHOD":method,"CONTENT_LENGTH":str(len(data)),"wsgi.input":io.BytesIO(data),"HTTP_AUTHORIZATION":("Bearer "+token if token else "")}
    for key,value in (headers or {}).items(): env[key]=value
    result={}
    def start(status,response_headers): result["status"]=status;result["headers"]=dict(response_headers)
    result["body"]=b"".join(application_store(env,start)); return result

class ReplayTests(unittest.TestCase):
    def test_claim_upload_range_and_retention(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ",{"ACEC_REPLAY_DIR":str(Path(tmp)/"clips")}):
            store=Store(str(Path(tmp)/"db.sqlite3"));create_user(store,"steward","a-long-password-value","steward")
            store.db.execute("INSERT INTO drivers VALUES(?,?,?,?,?)",("d","Driver",None,None,time.time()))
            incident=store.report_incident("d","manual","review",{})
            global application_store;application_store=application(store)
            token=json.loads(call(application_store,"/api/auth/login","POST",{"username":"steward","password":"a-long-password-value"})["body"])["access_token"]
            self.assertEqual(json.loads(call(application_store,f"/api/replay/{incident}/claim","POST",{},token)["body"])["status"],"CLAIMED")
            clip=b"0123456789"
            up=call(application_store,f"/api/replay/{incident}/upload","POST",token=token,raw=clip,headers={"HTTP_X_FILENAME":"race.mp4"})
            self.assertTrue(up["status"].startswith("201"))
            response=call(application_store,f"/api/replay/{incident}/video",token=token,headers={"HTTP_RANGE":"bytes=2-5"})
            self.assertEqual(response["status"],"206 Partial Content");self.assertEqual(response["body"],b"2345")
            store.db.execute("UPDATE replay_clips SET created_at=? WHERE incident_id=?",(time.time()-100*86400,incident))
            self.assertEqual(store.cleanup_replays(60),1)
            self.assertEqual(store.db.execute("SELECT status FROM replay_clips WHERE incident_id=?",(incident,)).fetchone()[0],"EXPIRED")
            store.db.close()

    def test_stale_claim_is_recoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(str(Path(tmp)/"db.sqlite3"));store.db.execute("INSERT INTO drivers VALUES(?,?,?,?,?)",("d","D",None,None,time.time()))
            iid=store.report_incident("d","manual","x",{});store.claim_replay(iid,"worker-a")
            store.db.execute("UPDATE replay_clips SET claimed_at=? WHERE incident_id=?",(time.time()-700,iid))
            self.assertTrue(store.claim_replay(iid,"worker-b"));self.assertEqual(store.db.execute("SELECT claimed_by FROM replay_clips WHERE incident_id=?",(iid,)).fetchone()[0],"worker-b")
            store.db.close()

    def test_manual_clip_upload_claims_pending_case(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ",{"ACEC_REPLAY_DIR":str(Path(tmp)/"clips")}):
            store=Store(str(Path(tmp)/"db.sqlite3"));create_user(store,"steward","a-long-password-value","steward")
            store.db.execute("INSERT INTO drivers VALUES(?,?,?,?,?)",("d","Driver",None,None,time.time()))
            incident=store.report_incident("d","manual","review",{});global application_store;application_store=application(store)
            token=json.loads(call(application_store,"/api/auth/login","POST",{"username":"steward","password":"a-long-password-value"})["body"])["access_token"]
            result=call(application_store,f"/api/replay/{incident}/manual-upload","POST",token=token,raw=b"video",headers={"HTTP_X_FILENAME":"manual.webm"})
            self.assertTrue(result["status"].startswith("201"));self.assertEqual(store.db.execute("SELECT status FROM replay_clips WHERE incident_id=?",(incident,)).fetchone()[0],"SAVED")
            store.db.close()

if __name__=="__main__": unittest.main()
