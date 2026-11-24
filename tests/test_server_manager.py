import tempfile, unittest
from pathlib import Path
from ac_endurance.server_manager import ServerManager

class ServerManagerTests(unittest.TestCase):
    def test_detect_catalog_and_config_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"server"; (root/"cfg").mkdir(parents=True); (root/"content/cars/car_a").mkdir(parents=True); (root/"content/tracks/track_a").mkdir(parents=True)
            (root/"acServer").write_text(""); (root/"cfg/server_cfg.ini").write_text("[SERVER]\nNAME=Test\nTRACK=track_a\nUDP_PLUGIN_LOCAL_PORT=0\n")
            mgr=ServerManager(str(root),str(Path(tmp)/"lgsm"),str(Path(tmp)/"backups")); info=mgr.config()
            self.assertTrue(info["detected"]);self.assertEqual(info["cars"],["car_a"]);self.assertFalse(info["udp_plugin_enabled"])
            archive=Path(mgr.backup());self.assertTrue(archive.exists())

if __name__=="__main__":unittest.main()
