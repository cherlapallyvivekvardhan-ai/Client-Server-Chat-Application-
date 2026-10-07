"""PrismChat server core.

* ChatServer  - thread-safe room: unique usernames, broadcast, whispers,
                /me actions, system notifications, presence timeouts.
* TCPGateway  - optional raw-socket front door (one thread per client) so
                terminal clients can chat in the SAME room as browser users.
"""
import itertools
import re
import socket
import threading
import time
from dataclasses import dataclass

NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{2,16}$")


@dataclass(frozen=True)
class Message:
    id: int
    ts: float
    kind: str  # chat | action | whisper | system
    sender: str
    text: str
    to: str = ""  # whisper target, or private-system-notice target


class ChatServer:
    def __init__(self, timeout=30, history=400):
        self._lock = threading.RLock()
        self._msgs = []
        self._users = {}  # lowercase name -> [display name, last_seen]
        self._ids = itertools.count(1)
        self.timeout = timeout
        self.history = history

    # ---------- internals ----------
    def _add(self, kind, sender, text, to=""):
        with self._lock:
            m = Message(next(self._ids), time.time(), kind, sender, text, to)
            self._msgs.append(m)
            del self._msgs[:-self.history]
            return m

    def _touch(self, name):
        with self._lock:
            u = self._users.get((name or "").lower())
            if u:
                u[1] = time.time()

    def _prune(self):
        now = time.time()
        with self._lock:
            for key, (disp, seen) in list(self._users.items()):
                if now - seen > self.timeout:
                    del self._users[key]
                    self._add("system", "", f"{disp} dropped off (timed out)")

    @staticmethod
    def _visible(m, name):
        n = name.lower()
        if m.kind == "whisper":
            return n in (m.sender.lower(), m.to.lower())
        if m.kind == "system" and m.to:
            return m.to.lower() == n
        return True

    # ---------- public API ----------
    def join(self, name):
        name = (name or "").strip()
        if not NAME_RE.match(name):
            return False, "Use 2-16 characters: letters, numbers, _ or -"
        with self._lock:
            self._prune()
            if name.lower() in self._users:
                return False, f"'{name}' is already taken - pick another"
            self._users[name.lower()] = [name, time.time()]
            self._add("system", "", f"{name} joined the room")
            self._add("system", "", "Welcome! Try /help for commands", to=name)
            return True, name

    def leave(self, name):
        with self._lock:
            u = self._users.pop((name or "").lower(), None)
            if u:
                self._add("system", "", f"{u[0]} left the room")

    def is_member(self, name):
        with self._lock:
            return (name or "").lower() in self._users

    def users(self):
        with self._lock:
            self._prune()
            return sorted((u[0] for u in self._users.values()), key=str.lower)

    def latest_id(self):
        with self._lock:
            return self._msgs[-1].id if self._msgs else 0

    def fetch(self, name, after=0):
        """Messages visible to `name` with id > after. Also acts as a heartbeat."""
        with self._lock:
            self._touch(name)
            self._prune()
            return [m for m in self._msgs if m.id > after and self._visible(m, name)]

    def post(self, name, raw):
        text = (raw or "").strip()[:500]
        if not text:
            return
        with self._lock:
            me = self._users.get((name or "").lower())
            if not me:
                return
            me[1] = time.time()
            who = me[0]
            if not text.startswith("/"):
                self._add("chat", who, text)
                return
            cmd, _, rest = text.partition(" ")
            cmd, rest = cmd.lower(), rest.strip()
            if cmd in ("/w", "/whisper"):
                target, _, body = rest.partition(" ")
                body = body.strip()
                t = self._users.get(target.lower())
                if not target or not body:
                    self._add("system", "", "Usage: /w <user> <message>", to=who)
                elif not t:
                    self._add("system", "", f"No user named '{target}' is online", to=who)
                elif t[0].lower() == who.lower():
                    self._add("system", "", "You can't whisper to yourself", to=who)
                else:
                    self._add("whisper", who, body, to=t[0])
            elif cmd == "/me" and rest:
                self._add("action", who, rest)
            elif cmd == "/users":
                self._add("system", "", "Online: " + ", ".join(self.users()), to=who)
            elif cmd == "/help":
                self._add(
                    "system", "",
                    "Commands: /w <user> <msg> (private) | /me <action> | /users | /help",
                    to=who,
                )
            else:
                self._add("system", "", "Unknown command - try /help", to=who)


def format_ansi(m, me):
    """Colour-coded line for terminal clients."""
    if m.kind == "system":
        return f"\033[92m* {m.text}\033[0m"
    if m.kind == "action":
        return f"\033[92m* {m.sender} {m.text}\033[0m"
    if m.kind == "whisper":
        return f"\033[95m[whisper] {m.sender} -> {m.to}: {m.text}\033[0m"
    colour = "96" if m.sender.lower() == me.lower() else "35"  # cyan / purple
    return f"\033[{colour}m{m.sender}: {m.text}\033[0m"


class TCPGateway(threading.Thread):
    """Plain TCP server, one thread per connected client."""

    def __init__(self, chat, host="0.0.0.0", port=5050):
        super().__init__(daemon=True)
        self.chat, self.host, self.port = chat, host, port
        self.ready = threading.Event()

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(50)
        self.ready.set()
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn):
        rf = conn.makefile("r", encoding="utf-8", errors="replace", newline="\n")
        wf = conn.makefile("w", encoding="utf-8", newline="\n")
        name = None
        stop = threading.Event()
        try:
            while not name:
                wf.write("Choose a username: ")
                wf.flush()
                line = rf.readline()
                if not line:
                    return
                ok, res = self.chat.join(line.strip())
                if ok:
                    name = res
                else:
                    wf.write(res + "\n")
            last = 0

            def pump():
                nonlocal last
                try:
                    while not stop.is_set():
                        for m in self.chat.fetch(name, last):
                            last = m.id
                            wf.write(format_ansi(m, name) + "\n")
                        wf.flush()
                        time.sleep(0.3)
                except (OSError, ValueError):
                    stop.set()

            threading.Thread(target=pump, daemon=True).start()
            for line in rf:  # ends when the client disconnects
                self.chat.post(name, line)
        except (OSError, ValueError):
            pass
        finally:
            stop.set()
            if name:
                self.chat.leave(name)
            try:
                conn.close()
            except OSError:
                pass
