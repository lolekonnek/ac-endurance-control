import struct, tempfile, unittest
from unittest.mock import patch
from pathlib import Path
from ac_endurance.protocol import parse_packet
from ac_endurance.store import Store

class StoreTests(unittest.TestCase):
    def test_raw_and_lap_are_persisted_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(str(Path(tmp)/"db.sqlite3"))
            packet=bytes([73,1])+struct.pack("<I",90000)+bytes([0,0])+struct.pack("<f",.98)
            event=parse_packet(packet)
            self.assertTrue(store.ingest(packet,event,"127.0.0.1:1"))
            self.assertFalse(store.ingest(packet,event,"127.0.0.1:1"))
            self.assertEqual(store.status()["raw_events"],1)
            self.assertEqual(store.status()["laps"],1)
            store.db.close()

    def test_result_import_hashes_driver_guid_and_is_idempotent(self):
        from ac_endurance.results import import_result
        import json
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ",{"ACEC_GUID_PEPPER":"pepper"}):
            store=Store(str(Path(tmp)/"db.sqlite3")); gh=__import__('hashlib').sha256(b"pepperguid-x").hexdigest()
            import time
            store.db.execute("INSERT INTO drivers VALUES(?,?,?,?,?)",("d","Driver",gh,None,time.time()))
            f=Path(tmp)/"race.json"; f.write_text(json.dumps({"TrackName":"spa","Type":2,"Result":[{"CarId":1,"DriverGuid":"GUID-X","DriverName":"Driver","BestLap":123000,"TotalTime":123000,"NumLaps":1}]}))
            self.assertTrue(import_result(store,f)); self.assertFalse(import_result(store,f))
            saved=store.db.execute("SELECT raw_json FROM result_sessions").fetchone()[0]
            self.assertNotIn("GUID-X",saved); self.assertEqual(store.db.execute("SELECT driver_id FROM result_entries").fetchone()[0],"d")
            store.db.close()

    def test_guid_is_redacted_and_udp_collision_creates_review_candidate(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ",{"ACEC_GUID_PEPPER":"pepper"}):
            store=Store(str(Path(tmp)/"db.sqlite3"))
            import hashlib, time
            digest=hashlib.sha256(b"peppersteam-guid").hexdigest()
            store.db.execute("INSERT INTO teams VALUES(?,?,?,?,?,?,?)",("team","Team",None,7,None,None,time.time()))
            store.db.execute("INSERT INTO drivers VALUES(?,?,?,?,?)",("driver","Driver",digest,"team",time.time()))
            conn={"packet_id":51,"type":"new_connection","driver_name":"Driver","driver_guid":"Steam-GUID","car_id":4,"car_model":"car","car_skin":"skin"}
            store.ingest(b"private-guid-packet",conn,"127.0.0.1:1")
            raw=store.db.execute("SELECT payload,parsed_json FROM raw_events").fetchone()
            self.assertNotIn(b"private-guid-packet",raw[0]); self.assertNotIn("Steam-GUID",raw[1])
            collision={"packet_id":130,"type":"client_event","event_type":11,"car_id":4,"speed":3.0,"world_position":[0,0,0],"relative_position":[1,0,0]}
            store.ingest(b"collision",collision,"127.0.0.1:1")
            self.assertEqual(store.db.execute("SELECT status FROM incident_reports").fetchone()[0],"NEW")
            store.db.close()

if __name__ == "__main__": unittest.main()
