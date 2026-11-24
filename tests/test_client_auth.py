import hashlib, tempfile, time, unittest
from pathlib import Path
from ac_endurance.store import Store
from ac_endurance.websocket import frame

class ClientAuthTests(unittest.TestCase):
    def test_token_maps_to_server_owned_driver_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(str(Path(tmp)/"db.sqlite3"))
            s.db.execute("INSERT INTO teams VALUES(?,?,?,?,?,?,?)",("t","Team", "car",7,"#fff",None,time.time()))
            s.db.execute("INSERT INTO drivers VALUES(?,?,?,?,?)",("d","Driver","guid-hash","t",time.time()))
            token="one-driver-secret"; digest=hashlib.sha256(token.encode()).hexdigest()
            s.db.execute("INSERT INTO client_tokens VALUES(?,?,?,NULL)",(digest,"d",time.time()))
            self.assertEqual(s.client_context(digest)["team"],"Team")
            self.assertIsNone(s.client_context(hashlib.sha256(b"wrong").hexdigest()))
            s.db.close()
    def test_websocket_server_frame(self):
        self.assertEqual(frame(b"hi"),bytes([0x81,2])+b"hi")

if __name__=="__main__": unittest.main()
