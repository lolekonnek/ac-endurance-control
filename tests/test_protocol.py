import struct, unittest
from ac_endurance.protocol import parse_packet, PacketError

class ProtocolTests(unittest.TestCase):
    def test_car_update(self):
        packet = bytes([53,2]) + struct.pack("<6f",1,2,3,4,5,6) + bytes([3]) + struct.pack("<Hf",7000,.5)
        parsed = parse_packet(packet)
        self.assertEqual(parsed["type"],"car_update"); self.assertEqual(parsed["car_id"],2); self.assertEqual(parsed["rpm"],7000)
    def test_lap_and_truncation(self):
        packet = bytes([73,1])+struct.pack("<I",90000)+bytes([0,0])+struct.pack("<f",.98)
        self.assertEqual(parse_packet(packet)["lap_ms"],90000)
        with self.assertRaises(PacketError): parse_packet(bytes([53,0]))
    def test_reject_nan(self):
        packet = bytes([53,0])+struct.pack("<6f",float("nan"),0,0,0,0,0)+bytes([0])+struct.pack("<Hf",0,.5)
        with self.assertRaises(PacketError): parse_packet(packet)

if __name__ == "__main__": unittest.main()
