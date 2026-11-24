from __future__ import annotations
import asyncio, logging, os, threading
from .adapter import run_udp
from .websocket import serve as serve_ws
from .store import Store
from .web import serve
from .results import monitor as monitor_results

def main():
    logging.basicConfig(level=os.getenv("ACEC_LOG_LEVEL","INFO"), format="%(asctime)s %(levelname)s %(message)s")
    store = Store(os.getenv("ACEC_DB","var/endurance.sqlite3"))
    def network():
        async def run():
            await asyncio.gather(
                run_udp(store,os.getenv("ACEC_UDP_HOST","0.0.0.0"),int(os.getenv("ACEC_UDP_PORT","12001"))),
                serve_ws(store,os.getenv("ACEC_WS_HOST","127.0.0.1"),int(os.getenv("ACEC_WS_PORT","8089"))),
                monitor_results(store))
        asyncio.run(run())
    thread = threading.Thread(target=network,name="ac-network",daemon=True); thread.start()
    serve(store,os.getenv("ACEC_HTTP_HOST","127.0.0.1"),int(os.getenv("ACEC_HTTP_PORT","8088")))

if __name__ == "__main__": main()
