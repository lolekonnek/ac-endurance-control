#!/usr/bin/env python3
import argparse, getpass, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ac_endurance.auth import create_user
from ac_endurance.store import Store

def main():
    p=argparse.ArgumentParser(); p.add_argument("database"); p.add_argument("username"); p.add_argument("role",choices=["admin","race_control","steward","captain","driver","viewer"]); p.add_argument("--driver-id"); a=p.parse_args()
    first=getpass.getpass("Hasło (min. 12 znaków): "); second=getpass.getpass("Powtórz hasło: ")
    if first!=second: p.error("hasła się różnią")
    store=Store(a.database)
    try: print("Utworzono użytkownika:",create_user(store,a.username,first,a.role,a.driver_id))
    finally: store.db.close()

if __name__=="__main__": main()
