"""Local application accounts. Not an OS security boundary."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROLES = ("Administrator", "Engineer", "Operator", "Viewer")
MATRIX = {
    "Open data files": (1,1,1,1),
    "View trends & statistics": (1,1,1,1),
    "Advanced diagnostics": (1,1,1,0),
    "Modify analysis settings": (1,1,0,0),
    "Export data & reports": (1,1,0,0),
    "Manage users": (1,0,0,0),
    "View audit history": (1,1,0,0),
}
@dataclass(frozen=True)
class Session:
    username: str
    role: str
    demo: bool = False

    def allows(self, key):
        if self.demo:
            return key in ("View trends & statistics","Advanced diagnostics","Modify analysis settings","Export data & reports")
        return self.role in ROLES and bool(MATRIX.get(key,(0,0,0,0))[ROLES.index(self.role)])

def derive(password, salt):
    if not isinstance(password,str) or len(password)>256:
        raise ValueError("Password must contain at most 256 characters")
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**15,r=8,p=1,maxmem=64*1024*1024,dklen=32)

class AccessStore:
    def __init__(self,path):
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS users (name TEXT PRIMARY KEY COLLATE NOCASE, role TEXT NOT NULL, enabled INTEGER NOT NULL, salt BLOB NOT NULL, digest BLOB NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, utc TEXT NOT NULL, username TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS attempts (name TEXT PRIMARY KEY COLLATE NOCASE, failures INTEGER NOT NULL, until REAL NOT NULL)")
        self.db.commit()

    def empty(self):
        return self.db.execute("SELECT COUNT(*) FROM users").fetchone()[0]==0

    def audit(self,who,action,detail=""):
        with self.db:
            self.db.execute("INSERT INTO audit(utc,username,action,detail) VALUES(?,?,?,?)",(datetime.now(timezone.utc).isoformat(),str(who)[:40],str(action)[:100],str(detail)[:300]))
            self.db.execute("DELETE FROM audit WHERE id NOT IN (SELECT id FROM audit ORDER BY id DESC LIMIT 10000)")

    @staticmethod
    def validate(name,password,role):
        if not re.fullmatch(r"[A-Za-z0-9._-]{3,40}",name):
            raise ValueError("Use 3–40 letters, digits, dots, hyphens or underscores.")
        if not 12<=len(password)<=256:
            raise ValueError("Use a password with 12–256 characters.")
        if role not in ROLES: raise ValueError("Invalid role")

    def _insert(self,name,password,role):
        self.validate(name,password,role)
        salt=secrets.token_bytes(16)
        try:
            self.db.execute("INSERT INTO users VALUES(?,?,?,?,?)",(name,role,1,salt,derive(password,salt)))
        except sqlite3.IntegrityError as exc:
            raise ValueError("Username already exists") from exc

    def setup(self,name,password):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not self.empty(): raise PermissionError("Initial setup already completed")
            self._insert(name,password,"Administrator")
        self.audit(name,"Initial setup")
        return Session(name,"Administrator")

    def login(self,name,password):
        name=name.strip()[:40]; now=time.time()
        a=self.db.execute("SELECT failures,until FROM attempts WHERE name=?",(name,)).fetchone()
        if a and a[1]>now: raise ValueError("Too many failed attempts. Try again later.")
        row=self.db.execute("SELECT name,role,enabled,salt,digest FROM users WHERE name=?",(name,)).fetchone()
        salt=row[3] if row else bytes(16)
        digest=derive(password,salt)
        if not row or not hmac.compare_digest(digest,row[4]) or not row[2]:
            failures=(a[0] if a else 0)+1
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO attempts VALUES(?,?,?)",(name,failures,now+60 if failures>=5 else 0))
            self.audit(name,"Failed sign in")
            raise ValueError("Invalid username or password.")
        with self.db:
            self.db.execute("DELETE FROM attempts WHERE name=?",(name,))
        self.audit(row[0],"Sign in")
        return Session(row[0],row[1])

    def require(self,session,key):
        if session.demo or not session.allows(key): raise PermissionError("Access denied")
        row=self.db.execute("SELECT role,enabled FROM users WHERE name=?",(session.username,)).fetchone()
        if not row or not row[1] or row[0]!=session.role: raise PermissionError("Session is no longer authorized")

    def create(self,session,name,password,role):
        self.require(session,"Manage users")
        with self.db: self._insert(name,password,role)
        self.audit(session.username,"User created",name)

    def users(self,session):
        if session.demo: return []
        if session.allows("Manage users"):
            self.require(session,"Manage users")
            return self.db.execute("SELECT name,role,enabled FROM users ORDER BY name").fetchall()
        return self.db.execute("SELECT name,role,enabled FROM users WHERE name=?",(session.username,)).fetchall()

    def toggle(self,session,name):
        self.require(session,"Manage users")
        if name.casefold()==session.username.casefold(): raise ValueError("Cannot disable your own account")
        with self.db: self.db.execute("UPDATE users SET enabled=1-enabled WHERE name=?",(name,))
        self.audit(session.username,"User status changed",name)

    def change(self,session,current,new):
        if session.demo: raise PermissionError("Demo account has no password")
        self.login(session.username,current)
        self.validate(session.username,new,session.role)
        salt=secrets.token_bytes(16)
        with self.db: self.db.execute("UPDATE users SET salt=?,digest=? WHERE name=?",(salt,derive(new,salt),session.username))
        self.audit(session.username,"Password changed")

    def history(self,session):
        self.require(session,"View audit history")
        return self.db.execute("SELECT utc,username,action,detail FROM audit ORDER BY id DESC LIMIT 300").fetchall()

    def close(self):
        self.db.close()
