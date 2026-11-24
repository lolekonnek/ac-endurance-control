"""Small RFC 6455 endpoint for authenticated CSP client sessions (JSON text frames only)."""
from __future__ import annotations
import asyncio, base64, hashlib, json, logging, time
from urllib.parse import urlsplit
from .store import Store

log=logging.getLogger(__name__)
GUID="258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

def frame(payload: bytes, opcode: int=1) -> bytes:
    n=len(payload); head=bytes([0x80|opcode])
    if n<126: head+=bytes([n])
    elif n<65536: head+=bytes([126])+n.to_bytes(2,"big")
    else: head+=bytes([127])+n.to_bytes(8,"big")
    return head+payload

async def read_frame(reader: asyncio.StreamReader):
    first=await reader.readexactly(2); opcode=first[0]&15; masked=bool(first[1]&128); n=first[1]&127
    if n==126: n=int.from_bytes(await reader.readexactly(2),"big")
    elif n==127: n=int.from_bytes(await reader.readexactly(8),"big")
    if n>65536: raise ValueError("frame too large")
    if not masked: raise ValueError("client frame must be masked")
    mask=await reader.readexactly(4); data=await reader.readexactly(n)
    return opcode,bytes(v^mask[i%4] for i,v in enumerate(data))

async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, store: Store):
    try:
        request=await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"),5)
        if len(request)>8192: raise ValueError("headers too large")
        lines=request.decode("latin1").split("\r\n"); headers={}
        for line in lines[1:]:
            if ":" in line:
                k,v=line.split(":",1); headers[k.lower().strip()]=v.strip()
        path=urlsplit(lines[0].split(" ")[1]).path
        auth=headers.get("authorization","")
        if path!="/ws/client" or not auth.startswith("Bearer "):
            writer.write(b"HTTP/1.1 401 Unauthorized\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"); await writer.drain(); return
        token_hash=hashlib.sha256(auth[7:].encode()).hexdigest(); context=store.client_context(token_hash)
        key=headers.get("sec-websocket-key")
        if not context or not key or headers.get("upgrade","").lower()!="websocket":
            writer.write(b"HTTP/1.1 401 Unauthorized\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"); await writer.drain(); return
        accept=base64.b64encode(hashlib.sha1((key+GUID).encode()).digest()).decode()
        writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "+accept+"\r\n\r\n").encode()); await writer.drain()
        next_state=0.0
        while not writer.is_closing():
            now=time.monotonic()
            if now>=next_state:
                packet={"type":"sync","server_time":time.time(),"driver":context,"race":store.live_state(),
                        "messages":store.client_messages(context["driver_id"],context.get("team_id")),
                        "penalties":store.client_penalties(context["driver_id"]),
                        "next_swap":store.client_next_swap(context.get("team_id")),
                        "stint":store.client_stint(context["driver_id"])}
                writer.write(frame(json.dumps(packet,separators=(",",":"),ensure_ascii=False).encode())); await writer.drain(); next_state=now+1
            try: opcode,payload=await asyncio.wait_for(read_frame(reader),.15)
            except asyncio.TimeoutError: continue
            if opcode==8: break
            if opcode==9: writer.write(frame(payload,10)); await writer.drain(); continue
            if opcode!=1: continue
            try: msg=json.loads(payload)
            except (ValueError,UnicodeDecodeError): continue
            if msg.get("type")=="incident_report":
                category=str(msg.get("category","driver_report"))[:40]
                telemetry=msg.get("telemetry") if isinstance(msg.get("telemetry"),dict) else {}
                incident_id=store.report_incident(context["driver_id"],category,str(msg.get("note","")),telemetry)
                writer.write(frame(json.dumps({"type":"incident_ack","id":incident_id}).encode())); await writer.drain()
            elif msg.get("type")=="pit_transition":
                pid=store.record_pit_transition(context["driver_id"],context.get("team_id"),context.get("car_number"),bool(msg.get("entering")),"zgłoszenie z klienta CSP (niezweryfikowane)")
                writer.write(frame(json.dumps({"type":"pit_ack","id":pid,"verified":False}).encode())); await writer.drain()
            elif msg.get("type")=="team_message" and context.get("team_id"):
                body=str(msg.get("body","")).strip()
                if body and len(body)<=300:
                    mid=__import__("uuid").uuid4().hex
                    store.db.execute("INSERT INTO race_messages VALUES(?,?,?,?,?,?,?)",(mid,time.time(),context["driver_id"],"team",context["team_id"],None,body))
                    store.audit(context["driver_id"],"team.message","message",mid,{"team_id":context["team_id"]})
                    writer.write(frame(json.dumps({"type":"team_message_ack","id":mid}).encode())); await writer.drain()
            # All other client messages are intentionally ignored: the client cannot mutate race state.
    except (asyncio.IncompleteReadError, ConnectionError, asyncio.TimeoutError, ValueError) as exc:
        log.debug("Klient WS rozłączony/odrzucony: %s",exc)
    finally:
        writer.close()
        try: await writer.wait_closed()
        except ConnectionError: pass

async def serve(store: Store, host: str="127.0.0.1", port: int=8089):
    server=await asyncio.start_server(lambda r,w:handle(r,w,store),host,port,limit=8192)
    async with server: await server.serve_forever()
