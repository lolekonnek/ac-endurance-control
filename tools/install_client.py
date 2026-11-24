#!/usr/bin/env python3
"""Install the CSP Lua app into an Assetto Corsa root directory."""
import argparse, pathlib, shutil
import re
from urllib.parse import urlparse

def main():
    p=argparse.ArgumentParser(); p.add_argument("assetto_root",help="katalog główny Assetto Corsa"); p.add_argument("--url",required=True,help="wss://host/ws/client"); p.add_argument("--token",required=True,help="token pojedynczego kierowcy")
    a=p.parse_args()
    parsed=urlparse(a.url)
    if parsed.scheme!="wss" or not parsed.netloc or parsed.path!="/ws/client" or any(c in a.url for c in "'\"\r\n"):
        p.error("wymagany bezpieczny adres wss://host/ws/client")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,200}",a.token): p.error("token musi być tokenem URL-safe (użyj mint_client_token.py)")
    src=pathlib.Path(__file__).resolve().parents[1]/"client"/"csp"/"ac_endurance_client"
    dst=pathlib.Path(a.assetto_root)/"apps"/"lua"/"ac_endurance_client"
    dst.mkdir(parents=True,exist_ok=True)
    for name in ("manifest.ini","ac_endurance_client.lua"):
        shutil.copy2(src/name,dst/name)
    app=dst/"ac_endurance_client.lua"
    text=app.read_text(encoding="utf-8").replace("wss://race.example.org/ws/client",a.url).replace("SET_DRIVER_TOKEN",a.token)
    app.write_text(text,encoding="utf-8")
    print(f"Zainstalowano CSP Lua App w: {dst}")
    print("W Content Manager włącz Lua Apps, CSP 0.2.0 lub nowszy i aktywuj Endurance Control w sesji.")

if __name__=="__main__": main()
