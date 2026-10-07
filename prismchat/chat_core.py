"""PrismChat v2 server core: many independent, password-locked servers (rooms).

Security model
* Passwords are never stored - only a salted PBKDF2-HMAC-SHA256 hash.
* Compared in constant time; 5 wrong tries lock a server for 60 s.
* Join errors are generic, so nobody can probe which servers exist.
* Every action needs a per-member secret token (no impersonation).
* Files are kept in memory only, size-capped, and deleted with the server.
"""
import hashlib
import hmac
import itertools
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass

NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{2,16}$")
ROOM_RE = re.compile(r"^[A-Za-z0-9 _\-]{3,24}$")
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_FILE = 10 * 1024 * 1024          # per file
MAX_ROOM_BYTES = 80 * 1024 * 1024    # per server
MAX_MEMBERS = 50
MAX_ROOMS = 200
GENERIC_FAIL = "Wrong server or password"


@dataclass(frozen=True)
class Session:
    code: str
    nick: str
    token: str


@dataclass(frozen=True)
class Message:
    id: int
    ts: float
    kind: str  # chat | action | whisper | system | file
    sender: str
    text: str
    to: str = ""
    file_id: str = ""


@dataclass(frozen=True)
class FileItem:
    id: str
    name: str
    mime: str
    data: bytes
    uploader: str
    ts: float

    @property
    def size(self):
        return len(self.data)


def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 120_000)


def _clean_filename(name):
    name = os.path.basename((name or "file").replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "", name).strip(". ")
    return (name or "file")[:80]


class Room:
    def __init__(self, code, name, owner_nick, owner_token, password, listed):
        self.code, self.name, self.listed = code, name, listed
        self.owner_nick, self.owner_token = owner_nick, owner_token
        self.salt = os.urandom(16)
        self.pw_hash = _hash(password, self.salt)
        self.members = {}  # lower nick -> {"nick","token","seen"}
        self.msgs, self.files, self.bytes = [], {}, 0
        self.ids = itertools.count(1)
        self.fails, self.locked_until = [], 0.0
        self.last_active = time.time()

    def add(self, kind, sender, text, to="", file_id=""):
        m = Message(next(self.ids), time.time(), kind, sender, text, to, file_id)
        self.msgs.append(m)
        del self.msgs[:-500]
        self.last_active = m.ts
        return m


def _visible(m, nick):
    n = nick.lower()
    if m.kind == "whisper":
        return n in (m.sender.lower(), m.to.lower())
    if m.kind == "system" and m.to:
        return m.to.lower() == n
    return True


class Hub:
    def __init__(self, timeout=45):
        self._lock = threading.RLock()
        self._rooms = {}
        self.timeout = timeout

    # ----- helpers -----
    def _gc(self):
        now = time.time()
        for code, r in list(self._rooms.items()):
            if not r.members and now - r.last_active > 6 * 3600:
                del self._rooms[code]

    def _prune(self, r):
        now = time.time()
        for k, m in list(r.members.items()):
            if now - m["seen"] > self.timeout:
                del r.members[k]
                r.add("system", "", f"{m['nick']} dropped off")

    def _auth(self, s):
        r = self._rooms.get(s.code) if s else None
        m = r.members.get(s.nick.lower()) if r else None
        if m and hmac.compare_digest(m["token"], s.token):
            m["seen"] = time.time()
            return r, m
        return None, None

    def _is_owner(self, r, s):
        return hmac.compare_digest(r.owner_token, s.token)

    def _find(self, key):
        key = (key or "").strip()
        if key.upper() in self._rooms:
            return self._rooms[key.upper()]
        for r in self._rooms.values():
            if r.name.lower() == key.lower():
                return r
        return None

    def _enter(self, r, nick, token=None):
        token = token or secrets.token_urlsafe(24)
        r.members[nick.lower()] = {"nick": nick, "token": token, "seen": time.time()}
        r.add("system", "", f"{nick} joined the server")
        r.add("system", "", "Welcome! Type /help for commands", to=nick)
        return Session(r.code, nick, token)

    # ----- create / join / leave -----
    def create(self, room_name, password, nick, listed=False):
        room_name, nick = (room_name or "").strip(), (nick or "").strip()
        if not ROOM_RE.match(room_name):
            return False, "Server name: 3-24 letters, numbers, spaces, _ or -"
        if not 4 <= len(password or "") <= 64:
            return False, "Password must be 4-64 characters"
        if not NAME_RE.match(nick):
            return False, "Nickname: 2-16 letters, numbers, _ or -"
        with self._lock:
            self._gc()
            if len(self._rooms) >= MAX_ROOMS:
                return False, "Server limit reached, try later"
            if any(r.name.lower() == room_name.lower() for r in self._rooms.values()):
                return False, "That server name is taken"
            while True:
                code = "".join(secrets.choice(ALPHABET) for _ in range(8))
                code = code[:4] + "-" + code[4:]
                if code not in self._rooms:
                    break
            token = secrets.token_urlsafe(24)
            r = Room(code, room_name, nick, token, password, bool(listed))
            self._rooms[code] = r
            return True, self._enter(r, nick, token)

    def join(self, key, password, nick):
        nick = (nick or "").strip()
        if not NAME_RE.match(nick):
            return False, "Nickname: 2-16 letters, numbers, _ or -"
        with self._lock:
            r = self._find(key)
            if r is None:
                return False, GENERIC_FAIL
            now = time.time()
            if now < r.locked_until:
                return False, f"Too many attempts - try again in {int(r.locked_until - now) + 1}s"
            if not hmac.compare_digest(_hash(password or "", r.salt), r.pw_hash):
                r.fails = [t for t in r.fails if now - t < 60] + [now]
                if len(r.fails) >= 5:
                    r.locked_until, r.fails = now + 60, []
                return False, GENERIC_FAIL
            r.fails = []
            self._prune(r)
            if nick.lower() in r.members:
                return False, f"'{nick}' is already online in this server"
            if len(r.members) >= MAX_MEMBERS:
                return False, "Server is full"
            return True, self._enter(r, nick)

    def leave(self, s):
        with self._lock:
            r, m = self._auth(s)
            if r:
                del r.members[m["nick"].lower()]
                r.add("system", "", f"{m['nick']} left")

    def close(self, s):
        with self._lock:
            r, _ = self._auth(s)
            if r and self._is_owner(r, s):
                del self._rooms[r.code]
                return True
            return False

    def listed(self):
        with self._lock:
            return [(r.name, len(r.members)) for r in self._rooms.values() if r.listed]

    # ----- in-room API (None means: not authorised / server gone) -----
    def fetch(self, s, after=0):
        with self._lock:
            r, m = self._auth(s)
            if not r:
                return None
            self._prune(r)
            return [x for x in r.msgs if x.id > after and _visible(x, m["nick"])]

    def info(self, s):
        with self._lock:
            r, _ = self._auth(s)
            if not r:
                return None
            self._prune(r)
            crew = sorted(((m["nick"], hmac.compare_digest(m["token"], r.owner_token))
                           for m in r.members.values()), key=lambda x: (not x[1], x[0].lower()))
            return {"name": r.name, "code": r.code, "crew": crew,
                    "is_owner": self._is_owner(r, s), "owner": r.owner_nick}

    def files(self, s):
        with self._lock:
            r, _ = self._auth(s)
            return sorted(r.files.values(), key=lambda f: -f.ts) if r else []

    def send_file(self, s, filename, data, mime=""):
        with self._lock:
            r, m = self._auth(s)
            if not r:
                return False, "Not connected"
            if not data:
                return False, "Empty file"
            if len(data) > MAX_FILE:
                return False, f"Max file size is {MAX_FILE // 1048576} MB"
            if r.bytes + len(data) > MAX_ROOM_BYTES:
                return False, "This server's file vault is full"
            f = FileItem(secrets.token_hex(6), _clean_filename(filename), mime or "application/octet-stream",
                         data, m["nick"], time.time())
            r.files[f.id] = f
            r.bytes += len(data)
            r.add("file", m["nick"], f.name, file_id=f.id)
            return True, f.id

    def post(self, s, raw):
        text = (raw or "").strip()[:500]
        if not text:
            return
        with self._lock:
            r, m = self._auth(s)
            if not r:
                return
            who = m["nick"]
            if not text.startswith("/"):
                r.add("chat", who, text)
                return
            cmd, _, rest = text.partition(" ")
            cmd, rest = cmd.lower(), rest.strip()
            say = lambda t: r.add("system", "", t, to=who)  # private notice
            if cmd in ("/w", "/whisper"):
                target, _, body = rest.partition(" ")
                t = r.members.get(target.lower())
                if not target or not body.strip():
                    say("Usage: /w <user> <message>")
                elif not t:
                    say(f"No user named '{target}' is online")
                elif t["nick"].lower() == who.lower():
                    say("You can't whisper to yourself")
                else:
                    r.add("whisper", who, body.strip(), to=t["nick"])
            elif cmd == "/me" and rest:
                r.add("action", who, rest)
            elif cmd == "/users":
                say("Online: " + ", ".join(sorted((x["nick"] for x in r.members.values()), key=str.lower)))
            elif cmd == "/kick":
                t = r.members.get(rest.lower())
                if not self._is_owner(r, s):
                    say("Only the server owner can kick")
                elif not t or t["nick"].lower() == who.lower():
                    say("Pick another member to kick")
                else:
                    del r.members[rest.lower()]
                    r.add("system", "", f"{t['nick']} was kicked by {who}")
            elif cmd == "/help":
                say("/w user msg (private) | /me action | /users | /kick user (owner) | attach files with the + button")
            else:
                say("Unknown command - try /help")
