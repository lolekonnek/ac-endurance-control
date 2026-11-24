#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ac_endurance.server_manager import ServerManager

def main():
    p=argparse.ArgumentParser(description="Bezpieczna integracja z instalacją AC/LinuxGSM"); p.add_argument("action",choices=["status","backup","restart"]); p.add_argument("--confirm",action="store_true"); a=p.parse_args(); manager=ServerManager()
    if a.action=="status": print(json.dumps(manager.config(),ensure_ascii=False,indent=2))
    elif a.action=="backup": print(manager.backup())
    else:
        if not a.confirm: p.error("restart wymaga jawnego --confirm")
        print(json.dumps(manager.restart(),ensure_ascii=False,indent=2))

if __name__=="__main__": main()
