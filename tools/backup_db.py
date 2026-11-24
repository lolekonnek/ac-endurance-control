#!/usr/bin/env python3
import argparse, sqlite3, time
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument("database");p.add_argument("destination");p.add_argument("--keep",type=int,default=14);a=p.parse_args()
    src=Path(a.database); dst=Path(a.destination); dst.mkdir(parents=True,exist_ok=True)
    out=dst/("endurance-"+time.strftime("%Y%m%d-%H%M%S",time.gmtime())+".sqlite3")
    source=sqlite3.connect(src); target=sqlite3.connect(out)
    try: source.backup(target)
    finally: target.close();source.close()
    backups=sorted(dst.glob("endurance-*.sqlite3"),key=lambda x:x.stat().st_mtime,reverse=True)
    for stale in backups[a.keep:]: stale.unlink()
    print(out)

if __name__=="__main__": main()
