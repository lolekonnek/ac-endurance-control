#!/usr/bin/env python3
"""Create a single-driver bearer credential; display it once for the client install."""
import argparse, hashlib, secrets, sqlite3, time

def main():
    p=argparse.ArgumentParser(); p.add_argument("database"); p.add_argument("driver_id"); a=p.parse_args()
    token=secrets.token_urlsafe(32)
    db=sqlite3.connect(a.database)
    if not db.execute("SELECT 1 FROM drivers WHERE id=?",(a.driver_id,)).fetchone(): p.error("driver_id nie istnieje")
    db.execute("INSERT INTO client_tokens(token_hash,driver_id,created_at) VALUES(?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),a.driver_id,time.time()))
    db.commit(); db.close()
    print("Skopiuj token teraz; baza przechowuje wyłącznie jego SHA-256:")
    print(token)

if __name__=="__main__": main()
