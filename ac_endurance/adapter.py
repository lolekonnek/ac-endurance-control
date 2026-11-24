from __future__ import annotations
import asyncio, json, logging, time
from .protocol import parse_packet, PacketError
from .store import Store

log = logging.getLogger(__name__)

class ACProtocol(asyncio.DatagramProtocol):
    def __init__(self, store: Store): self.store, self.transport, self.last_packet, self.bad_packets = store, None, None, 0
    def connection_made(self, transport): self.transport = transport
    def datagram_received(self, data: bytes, addr):
        try:
            parsed = parse_packet(data)
            self.store.ingest(data, parsed, f"{addr[0]}:{addr[1]}")
            self.last_packet = time.time()
            log.info("UDP %s from %s", parsed["type"], addr[0])
        except (PacketError, ValueError, IndexError) as exc:
            self.bad_packets += 1
            log.warning("Odrzucono niepoprawny pakiet UDP od %s: %s", addr[0], exc)
    def error_received(self, exc): log.error("Błąd transportu UDP: %s", exc)

async def run_udp(store: Store, host: str, port: int):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(lambda: ACProtocol(store), local_addr=(host, port))
    try: await asyncio.Future()
    finally: transport.close()
