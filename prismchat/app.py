import html
import os
import time
import zlib

import streamlit as st

from chat_core import ChatServer, TCPGateway

st.set_page_config(page_title="PrismChat", page_icon="🌈", layout="wide")

THEMES = {
    "Neon": {"me": "#00e5ff", "them": "#b44cff", "sys": "#39ff14", "whisper": "#ff2d95"},
    "Sunset": {"me": "#ffb347", "them": "#ff5e62", "sys": "#ffe66d", "whisper": "#ff9ff3"},
    "Ocean": {"me": "#4facfe", "them": "#00c9a7", "sys": "#a8ff78", "whisper": "#f093fb"},
}

CSS = """
<style>
.stApp{background:
  radial-gradient(1100px 600px at 8% -10%, rgba(180,76,255,.28), transparent 60%),
  radial-gradient(900px 500px at 100% 0%, rgba(0,229,255,.18), transparent 60%),
  #0b0720;}
header[data-testid="stHeader"]{background:transparent;}
.prism-title{font-size:clamp(2rem,6vw,3.3rem);font-weight:800;text-align:center;margin:0;
  background:linear-gradient(90deg,#00e5ff,#b44cff,#ff2d95,#39ff14,#00e5ff);background-size:300% 100%;
  -webkit-background-clip:text;background-clip:text;color:transparent;animation:flow 8s linear infinite;}
@keyframes flow{to{background-position:300% 0;}}
.tagline{text-align:center;opacity:.7;margin:0 0 1rem 0;}
.feed{display:flex;flex-direction:column-reverse;gap:.55rem;height:62vh;overflow-y:auto;padding:1rem;
  border-radius:18px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);}
.row{display:flex;gap:.6rem;align-items:flex-end;}
.row.me{justify-content:flex-end;}
.row.sys{justify-content:center;}
.av{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-weight:700;
  font-size:.8rem;color:#0b0720;flex:none;}
.bub{max-width:min(78%,560px);padding:.5rem .85rem;border-radius:16px;line-height:1.35;
  overflow-wrap:anywhere;color:#f4f1ff;}
.bub .meta{font-size:.7rem;opacity:.9;margin-bottom:.15rem;font-weight:600;}
.bub.me{background:color-mix(in srgb,var(--me) 16%,transparent);border:1px solid var(--me);
  box-shadow:0 0 14px color-mix(in srgb,var(--me) 35%,transparent);border-bottom-right-radius:4px;}
.bub.me .meta{color:var(--me);}
.bub.them{background:color-mix(in srgb,var(--them) 18%,transparent);border:1px solid var(--them);
  box-shadow:0 0 14px color-mix(in srgb,var(--them) 30%,transparent);border-bottom-left-radius:4px;}
.bub.whisper{background:color-mix(in srgb,var(--whisper) 16%,transparent);border:1px dashed var(--whisper);
  box-shadow:0 0 14px color-mix(in srgb,var(--whisper) 35%,transparent);}
.bub.whisper .meta{color:var(--whisper);}
.row.sys span{color:var(--sys);font-size:.82rem;padding:.2rem .75rem;border-radius:999px;
  background:color-mix(in srgb,var(--sys) 10%,transparent);
  border:1px solid color-mix(in srgb,var(--sys) 35%,transparent);}
.panel{padding:1rem;border-radius:18px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);}
.panel h4{margin:0 0 .5rem 0;}
.user{display:flex;align-items:center;gap:.5rem;padding:.3rem 0;}
.dot{width:9px;height:9px;border-radius:50%;background:var(--sys);box-shadow:0 0 8px var(--sys);
  animation:pulse 1.6s infinite;}
@keyframes pulse{50%{opacity:.3;}}
div[data-testid="stFormSubmitButton"] button, div[data-testid="stSidebar"] button{
  width:100%;border:0;color:#0b0720;font-weight:700;
  background:linear-gradient(90deg,#00e5ff,#b44cff,#ff2d95);}
</style>
"""


@st.cache_resource
def get_chat():
    chat = ChatServer()
    if os.getenv("PRISM_TCP") == "1":  # optional raw-socket door (local / VPS)
        TCPGateway(chat, port=int(os.getenv("PRISM_TCP_PORT", "5050"))).start()
    return chat


chat = get_chat()
ss = st.session_state
ss.setdefault("name", None)
ss.setdefault("theme", "Neon")


def esc(s):
    return html.escape(s).replace("$", "&#36;").replace("\n", "<br>")


def hue(name):
    return zlib.crc32(name.lower().encode()) % 360


def render(m, me):
    t = time.strftime("%H:%M", time.localtime(m.ts))
    if m.kind == "system":
        return f'<div class="row sys"><span>✦ {esc(m.text)}</span></div>'
    if m.kind == "action":
        return f'<div class="row sys"><span>✶ {esc(m.sender)} {esc(m.text)}</span></div>'
    mine = m.sender.lower() == me.lower()
    if m.kind == "whisper":
        label = f"🤫 you → {esc(m.to)}" if mine else f"🤫 {esc(m.sender)} → you"
        side = "me" if mine else ""
        return (f'<div class="row {side}"><div class="bub whisper">'
                f'<div class="meta">{label} · {t}</div>{esc(m.text)}</div></div>')
    if mine:
        return (f'<div class="row me"><div class="bub me">'
                f'<div class="meta">You · {t}</div>{esc(m.text)}</div></div>')
    h = hue(m.sender)
    return (f'<div class="row"><div class="av" style="background:hsl({h},85%,62%)">'
            f'{esc(m.sender[:1].upper())}</div><div class="bub them">'
            f'<div class="meta" style="color:hsl({h},90%,72%)">{esc(m.sender)} · {t}</div>'
            f'{esc(m.text)}</div></div>')


# ---------------- sidebar ----------------
with st.sidebar:
    st.markdown("### 🎨 Vibe")
    st.radio("Theme", list(THEMES), key="theme", label_visibility="collapsed")
    if ss.name:
        st.markdown(f"Signed in as **{ss.name}**")
        if st.button("Leave room"):
            chat.leave(ss.name)
            ss.name = None
            st.rerun()
        st.caption("Commands: `/w user msg` · `/me action` · `/users` · `/help`")
    if os.getenv("PRISM_TCP") == "1":
        st.caption(f"Terminal clients: `python tcp_client.py <host> {os.getenv('PRISM_TCP_PORT', '5050')}`")

c = THEMES[ss.theme]
st.markdown(
    f"<style>:root{{--me:{c['me']};--them:{c['them']};--sys:{c['sys']};--whisper:{c['whisper']};}}</style>" + CSS,
    unsafe_allow_html=True,
)
st.markdown('<h1 class="prism-title">🌈 PrismChat</h1>', unsafe_allow_html=True)
st.markdown('<p class="tagline">A colour-coded, real-time client-server chatroom</p>', unsafe_allow_html=True)

# ---------------- login ----------------
if not ss.name:
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if ss.pop("kicked", False):
            st.warning("You were disconnected for being idle. Rejoin below.")
        with st.form("join"):
            nick = st.text_input("Pick a unique nickname", max_chars=16, placeholder="e.g. NeonFox")
            go = st.form_submit_button("Enter the Prism ✨")
        if go:
            ok, res = chat.join(nick)
            if ok:
                ss.name = res
                st.rerun()
            else:
                st.error(res)
        st.caption(f"🟢 {len(chat.users())} online right now")
    st.stop()


# ---------------- chat room ----------------
@st.fragment(run_every=1.5)
def live_room(me):
    msgs = chat.fetch(me)[-120:]
    if not chat.is_member(me):
        ss.name = None
        ss.kicked = True
        st.rerun()
    left, right = st.columns([4, 1.4])
    with left:
        feed = "".join(render(m, me) for m in reversed(msgs))  # newest first -> column-reverse
        st.markdown(f'<div class="feed">{feed}</div>', unsafe_allow_html=True)
    with right:
        users = chat.users()
        rows = "".join(
            f'<div class="user"><span class="dot"></span>'
            f'<span style="color:hsl({hue(u)},90%,72%)">{esc(u)}</span>'
            f'{" <small>(you)</small>" if u.lower() == me.lower() else ""}</div>'
            for u in users
        )
        st.markdown(f'<div class="panel"><h4>🟢 Online · {len(users)}</h4>{rows}</div>',
                    unsafe_allow_html=True)


prompt = st.chat_input("Message everyone… or /w name secret")
if prompt:
    chat.post(ss.name, prompt)
live_room(ss.name)
