#!/usr/bin/env python3
"""Set the public, read-only race snapshot served to authenticated game clients."""
import argparse, json, sqlite3, time

def main():
    p=argparse.ArgumentParser(); p.add_argument("database"); p.add_argument("--name",default="AC Endurance"); p.add_argument("--status",default="live"); p.add_argument("--flag",choices=["GREEN","YELLOW","DOUBLE_YELLOW","BLUE","RED","WHITE","BLACK_WHITE","BLACK","CHEQUERED","SC","VSC","FCY"],default="GREEN"); p.add_argument("--message",default=""); a=p.parse_args()
    state={"name":a.name,"status":a.status,"flag":a.flag,"message":a.message,"updated_at":time.time()}
    db=sqlite3.connect(a.database); db.execute("INSERT INTO app_state(key,value_json,updated_at) VALUES('race_state',?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",(json.dumps(state,ensure_ascii=False),time.time())); db.commit(); db.close()

if __name__=="__main__": main()
