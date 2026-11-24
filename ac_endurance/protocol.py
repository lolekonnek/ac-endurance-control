"""Minimal parser for the community-documented AC dedicated server UDP protocol."""
from __future__ import annotations
import math
import struct
from typing import Any

PACKETS = {50: "new_session", 51: "new_connection", 52: "connection_closed", 53: "car_update",
           54: "car_info", 55: "end_session", 56: "version", 57: "chat", 58: "client_loaded",
           59: "session_info", 60: "error", 73: "lap_completed", 130: "client_event"}

class PacketError(ValueError):
    pass

class Reader:
    def __init__(self, data: bytes): self.data, self.i = data, 0
    def take(self, n: int) -> bytes:
        if n < 0 or self.i + n > len(self.data): raise PacketError("ucięty pakiet")
        out = self.data[self.i:self.i+n]; self.i += n; return out
    def u8(self) -> int: return self.take(1)[0]
    def u16(self) -> int: return struct.unpack("<H", self.take(2))[0]
    def i16(self) -> int: return struct.unpack("<h", self.take(2))[0]
    def u32(self) -> int: return struct.unpack("<I", self.take(4))[0]
    def i32(self) -> int: return struct.unpack("<i", self.take(4))[0]
    def f32(self) -> float:
        v = struct.unpack("<f", self.take(4))[0]
        if not math.isfinite(v): raise PacketError("niepoprawna liczba")
        return v
    def string(self) -> str: return self.take(self.u8()).decode("utf-8", "replace")
    def wide(self) -> str: return self.take(self.u8() * 4).decode("utf-16le", "replace").replace("\0", "")
    def vec3(self) -> list[float]: return [self.f32(), self.f32(), self.f32()]

def parse_packet(data: bytes) -> dict[str, Any]:
    if not data: raise PacketError("pusty pakiet")
    r = Reader(data); packet_id = r.u8(); name = PACKETS.get(packet_id, "unknown")
    d: dict[str, Any] = {"packet_id": packet_id, "type": name}
    if packet_id in (50, 59):
        d.update(version=r.u8(), session_index=r.u8(), current_session_index=r.u8(), session_count=r.u8(),
                 server_name=r.wide(), track=r.string(), track_config=r.string(), name=r.string(),
                 session_type=r.u8(), time=r.u16(), laps=r.u16(), wait_time=r.u16(), ambient_temp=r.u8(),
                 road_temp=r.u8(), weather=r.string(), elapsed_ms=r.i32())
    elif packet_id in (51, 52):
        d.update(driver_name=r.wide(), driver_guid=r.wide(), car_id=r.u8(), car_model=r.string(), car_skin=r.string())
    elif packet_id == 53:
        d.update(car_id=r.u8(), position=r.vec3(), velocity=r.vec3(), gear=r.u8(), rpm=r.u16(), spline=r.f32())
        if not 0 <= d["spline"] <= 1.1: raise PacketError("pozycja spline poza zakresem")
    elif packet_id == 54:
        d.update(car_id=r.u8(), connected=bool(r.u8()), car_model=r.wide(), car_skin=r.wide(),
                 driver_name=r.wide(), driver_team=r.wide(), driver_guid=r.wide())
    elif packet_id == 55: d["filename"] = r.wide()
    elif packet_id in (56, 58): d["value"] = r.u8()
    elif packet_id == 57: d.update(car_id=r.u8(), message=r.wide())
    elif packet_id == 60: d["message"] = r.wide()
    elif packet_id == 73:
        d.update(car_id=r.u8(), lap_ms=r.u32(), cuts=r.u8(), cars_count=r.u8())
        if d["cars_count"] > 100: raise PacketError("niewiarygodna liczba aut")
        d["leaderboard"] = [{"car_id": r.u8(), "lap_ms": r.u32(), "laps": r.u8()} for _ in range(d["cars_count"])]
        d["grip"] = r.f32()
    elif packet_id == 130:
        d.update(event_type=r.u8(), car_id=r.u8())
        if d["event_type"] == 10: d["other_car_id"] = r.u8()
        d.update(speed=r.f32(), world_position=r.vec3(), relative_position=r.vec3())
    # Do not silently accept malformed known messages or discard undocumented trailing fields.
    if packet_id in PACKETS and r.i != len(data): raise PacketError(f"nadmiarowe bajty: {len(data)-r.i}")
    return d
