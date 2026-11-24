import io, json, tempfile, unittest
from pathlib import Path
from ac_endurance.auth import create_user
from ac_endurance.store import Store
from ac_endurance.web import application

def call(app,path,method="GET",body=None,token=""):
    raw=json.dumps(body or {}).encode(); env={"PATH_INFO":path,"REQUEST_METHOD":method,"CONTENT_LENGTH":str(len(raw)),"wsgi.input":io.BytesIO(raw),"HTTP_AUTHORIZATION":("Bearer "+token if token else "")}
    result={}
    def start(status,headers): result["status"]=status
    data=b"".join(app(env,start)); result["body"]=json.loads(data) if data else None
    return result

class ApiTests(unittest.TestCase):
    def test_login_rbac_and_audited_race_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(str(Path(tmp)/"db.sqlite3")); create_user(store,"ops","a-long-password-value","admin")
            app=application(store)
            self.assertTrue(call(app,"/api/teams","POST",{"name":"Denied"})["status"].startswith("401"))
            login=call(app,"/api/auth/login","POST",{"username":"ops","password":"a-long-password-value"})
            self.assertTrue(login["status"].startswith("200")); token=login["body"]["access_token"]
            event=call(app,"/api/events","POST",{"name":"24h","track":"sx_lemans","duration_seconds":86400},token)
            self.assertTrue(event["status"].startswith("201")); eid=event["body"]["id"]
            self.assertEqual(call(app,f"/api/events/{eid}/transition","POST",{"status":"STAGING"},token)["body"]["status"],"STAGING")
            self.assertEqual(call(app,f"/api/events/{eid}/transition","POST",{"status":"LIVE"},token)["body"]["status"],"LIVE")
            state=call(app,"/api/control/state","POST",{"flag":"VSC","message":"Limit 80 km/h"},token)
            self.assertEqual(state["body"]["flag"],"VSC")
            self.assertEqual(call(app,"/api/live")["body"]["status"],"live")
            self.assertEqual(store.db.execute("SELECT count(*) FROM audit WHERE action='race.state'").fetchone()[0],1)
            store.db.close()

if __name__=="__main__": unittest.main()
