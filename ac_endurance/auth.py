from __future__ import annotations
import hashlib, hmac, secrets, time, uuid
from .store import Store

ROLES={"admin","race_control","steward","captain","driver","viewer"}

def password_hash(password: str, salt: bytes | None=None) -> tuple[bytes,bytes]:
    salt=salt or secrets.token_bytes(16)
    return salt,hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1,dklen=32)

def verify_password(password: str, salt: bytes, digest: bytes) -> bool:
    return hmac.compare_digest(password_hash(password,salt)[1],digest)

def create_user(store: Store, username: str, password: str, role: str, driver_id: str | None=None):
    if role not in ROLES: raise ValueError("nieznana rola")
    if len(password)<12: raise ValueError("hasło musi mieć co najmniej 12 znaków")
    salt,digest=password_hash(password)
    uid=str(uuid.uuid4())
    store.db.execute("INSERT INTO users(id,username,password_salt,password_hash,role,driver_id,created_at) VALUES(?,?,?,?,?,?,?)",(uid,username,salt,digest,role,driver_id,time.time()))
    store.audit("bootstrap","user.create","user",uid,{"username":username,"role":role})
    return uid

def login(store: Store, username: str, password: str) -> str | None:
    row=store.db.execute("SELECT id,password_salt,password_hash FROM users WHERE username=? AND disabled=0",(username,)).fetchone()
    # Perform a hash even for unknown usernames, reducing account enumeration timing differences.
    if not row:
        password_hash(password,b"\x00"*16)
        return None
    if not verify_password(password,row[1],row[2]): return None
    token=secrets.token_urlsafe(32); now=time.time()
    store.db.execute("INSERT INTO user_sessions VALUES(?,?,?, ?,NULL)",(hashlib.sha256(token.encode()).hexdigest(),row[0],now,now+12*3600))
    store.audit(row[0],"auth.login","user",row[0],{})
    return token
