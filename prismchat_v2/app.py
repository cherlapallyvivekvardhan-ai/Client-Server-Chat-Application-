import html
import time
import zlib

import streamlit as st

from chat_core import Hub

st.set_page_config(page_title="PrismChat", page_icon="🌈", layout="wide")

THEMES = {
    "Neon": dict(me="#00e5ff", them="#b44cff", sys="#39ff14", whisper="#ff2d95", a1="#7a2cff", a2="#00c2ff"),
    "Sunset": dict(me="#ffb347", them="#ff5e62", sys="#ffe66d", whisper="#ff9ff3", a1="#ff5e62", a2="#ffb347"),
    "Ocean": dict(me="#4facfe", them="#00c9a7", sys="#a8ff78", whisper="#f093fb", a1="#0072ff", a2="#00c9a7"),
    "Candy": dict(me="#ff6bd6", them="#6c8cff", sys="#7dffb2", whisper="#ffd166", a1="#ff6bd6", a2="#6c8cff"),
}
IMG = {"image/png", "image/jpeg", "image/gif", "image/webp"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
html,body,.stApp,button,input,textarea{font-family:'Space Grotesk',system-ui,sans-serif !important;}
.stApp{background:#07041a;}
.stApp::before{content:"";position:fixed;inset:-25%;z-index:0;pointer-events:none;filter:blur(35px);
  background:
   radial-gradient(40% 40% at 20% 30%,color-mix(in srgb,var(--a1) 55%,transparent),transparent 70%),
   radial-gradient(35% 35% at 82% 18%,color-mix(in srgb,var(--a2) 45%,transparent),transparent 70%),
   radial-gradient(45% 45% at 60% 92%,color-mix(in srgb,var(--them) 40%,transparent),transparent 70%);
  animation:drift 20s ease-in-out infinite alternate;}
@keyframes drift{to{transform:translate3d(4%,-3%,0) rotate(7deg) scale(1.1);}}
[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:transparent !important;}
[data-testid="stAppViewContainer"],[data-testid="stSidebar"]{position:relative;z-index:1;}
[data-testid="stSidebar"]{background:rgba(10,6,34,.72);backdrop-filter:blur(16px);}
.glass,[data-testid="stForm"]{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.13);
  border-radius:22px;backdrop-filter:blur(14px);box-shadow:0 10px 40px rgba(0,0,0,.35);}
[data-testid="stForm"]{padding:1.2rem;}
.hero{text-align:center;padding:1.2rem 0 .4rem;}
.logo{font-size:clamp(2.4rem,7vw,4.2rem);font-weight:700;letter-spacing:.12em;margin:0;
  background:linear-gradient(90deg,var(--me),var(--them),var(--whisper),var(--sys),var(--me));background-size:300% 100%;
  -webkit-background-clip:text;background-clip:text;color:transparent;animation:flow 9s linear infinite;
  filter:drop-shadow(0 0 22px color-mix(in srgb,var(--them) 55%,transparent));}
@keyframes flow{to{background-position:300% 0;}}
.tag{opacity:.75;margin:.2rem 0 .9rem;}
.pills{display:flex;gap:.5rem;justify-content:center;flex-wrap:wrap;margin-bottom:1rem;}
.pill{padding:.3rem .8rem;border-radius:999px;font-size:.82rem;border:1px solid rgba(255,255,255,.18);
  background:rgba(255,255,255,.06);}
button[data-baseweb="tab"]{font-weight:600;}
.stTextInput input{background:rgba(255,255,255,.07) !important;border:1px solid rgba(255,255,255,.18) !important;border-radius:12px !important;}
div[data-testid="stFormSubmitButton"] button,[data-testid="stSidebar"] button{width:100%;border:0;color:#0b0720;font-weight:700;
  border-radius:12px;background:linear-gradient(90deg,var(--me),var(--them),var(--whisper));}
.head{display:flex;justify-content:space-between;align-items:center;padding:.8rem 1.1rem;margin-bottom:.7rem;gap:.8rem;flex-wrap:wrap;}
.srv{font-size:1.35rem;font-weight:700;}
.sub{opacity:.75;font-size:.85rem;}
.chip{font-family:ui-monospace,monospace;letter-spacing:.18em;padding:.3rem .9rem;border-radius:999px;color:var(--me);
  border:1px solid var(--me);box-shadow:0 0 14px color-mix(in srgb,var(--me) 40%,transparent);}
.feed{display:flex;flex-direction:column-reverse;gap:.55rem;height:56vh;overflow-y:auto;padding:1rem;border-radius:22px;
  background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);}
.row{display:flex;gap:.6rem;align-items:flex-end;}
.row.me{justify-content:flex-end;}
.row.sys{justify-content:center;}
.av{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:.8rem;color:#0b0720;flex:none;}
.bub{max-width:min(78%,560px);padding:.5rem .85rem;border-radius:16px;line-height:1.35;overflow-wrap:anywhere;color:#f4f1ff;}
.bub .meta{font-size:.7rem;margin-bottom:.15rem;font-weight:600;}
.bub.me{background:color-mix(in srgb,var(--me) 16%,transparent);border:1px solid var(--me);border-bottom-right-radius:4px;
  box-shadow:0 0 14px color-mix(in srgb,var(--me) 32%,transparent);}
.bub.me .meta{color:var(--me);}
.bub.them{background:color-mix(in srgb,var(--them) 18%,transparent);border:1px solid var(--them);border-bottom-left-radius:4px;
  box-shadow:0 0 14px color-mix(in srgb,var(--them) 28%,transparent);}
.bub.whisper{background:color-mix(in srgb,var(--whisper) 16%,transparent);border:1px dashed var(--whisper);
  box-shadow:0 0 14px color-mix(in srgb,var(--whisper) 32%,transparent);}
.bub.whisper .meta{color:var(--whisper);}
.bub.file{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.28);}
.row.sys span{color:var(--sys);font-size:.82rem;padding:.2rem .75rem;border-radius:999px;
  background:color-mix(in srgb,var(--sys) 10%,transparent);border:1px solid color-mix(in srgb,var(--sys) 35%,transparent);}
.user{display:flex;align-items:center;gap:.5rem;padding:.3rem 0;}
.dot{width:9px;height:9px;border-radius:50%;background:var(--sys);box-shadow:0 0 8px var(--sys);animation:pulse 1.6s infinite;}
@keyframes pulse{50%{opacity:.3;}}
.vfile{padding:.4rem 0 .2rem;}
.room{padding:.7rem 1rem;margin:.4rem 0;}
</style>
"""


@st.cache_resource
def get_hub():
    return Hub()


hub = get_hub()
ss = st.session_state
ss.setdefault("sess", None)
ss.setdefault("theme", "Neon")
ss.setdefault("notice", "")


def esc(s):
    return html.escape(str(s)).replace("$", "&#36;").replace("\n", "<br>")


def hue(n):
    return zlib.crc32(n.lower().encode()) % 360


def human(n):
    for u in ("B", "KB", "MB"):
        if n < 1024 or u == "MB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def render(m, me):
    t = time.strftime("%H:%M", time.localtime(m.ts))
    if m.kind == "system":
        return f'<div class="row sys"><span>✦ {esc(m.text)}</span></div>'
    if m.kind == "action":
        return f'<div class="row sys"><span>✶ {esc(m.sender)} {esc(m.text)}</span></div>'
    mine = m.sender.lower() == me.lower()
    side = "me" if mine else ""
    if m.kind == "whisper":
        label = f"🤫 you → {esc(m.to)}" if mine else f"🤫 {esc(m.sender)} → you"
        return f'<div class="row {side}"><div class="bub whisper"><div class="meta">{label} · {t}</div>{esc(m.text)}</div></div>'
    if m.kind == "file":
        who = "You" if mine else esc(m.sender)
        return (f'<div class="row {side}"><div class="bub file"><div class="meta">{who} · {t}</div>'
                f'📎 <b>{esc(m.text)}</b><br><small>saved in the Vault →</small></div></div>')
    if mine:
        return f'<div class="row me"><div class="bub me"><div class="meta">You · {t}</div>{esc(m.text)}</div></div>'
    h = hue(m.sender)
    return (f'<div class="row"><div class="av" style="background:hsl({h},85%,62%)">{esc(m.sender[:1].upper())}</div>'
            f'<div class="bub them"><div class="meta" style="color:hsl({h},90%,72%)">{esc(m.sender)} · {t}</div>{esc(m.text)}</div></div>')


# ---------- sidebar ----------
with st.sidebar:
    st.markdown("### 🎨 Vibe")
    st.radio("Theme", list(THEMES), key="theme", label_visibility="collapsed")
    if ss.sess:
        info = hub.info(ss.sess)
        if info:
            st.markdown("### 🔗 Invite")
            st.code(info["code"], language=None)
            st.caption("Share the code (or server name) and the password.")
        if st.button("Leave server"):
            hub.leave(ss.sess)
            ss.sess = None
            st.rerun()
        if info and info["is_owner"]:
            if st.checkbox("I want to close this server for everyone"):
                if st.button("Close server"):
                    hub.close(ss.sess)
                    ss.sess, ss.notice = None, "Your server was closed."
                    st.rerun()
        st.caption("`/w user msg` · `/me action` · `/users` · `/kick user` (owner)")

c = THEMES[ss.theme]
vars_css = "".join(f"--{k}:{v};" for k, v in c.items())
st.markdown(f"<style>:root{{{vars_css}}}</style>" + CSS, unsafe_allow_html=True)

# ---------- landing ----------
if not ss.sess:
    st.markdown(
        '<div class="hero"><h1 class="logo">PRISMCHAT</h1>'
        '<p class="tag">Private, password-locked servers · live chat · a shared file vault</p>'
        '<div class="pills"><span class="pill">🔐 Hashed passwords</span><span class="pill">🛰️ Unlimited servers</span>'
        '<span class="pill">📎 Share any file</span><span class="pill">🤫 Private whispers</span>'
        '<span class="pill">🎨 Live themes</span></div></div>',
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 2.2, 1])
    with mid:
        if ss.notice:
            st.warning(ss.notice)
            ss.notice = ""
        t_join, t_new, t_disc = st.tabs(["🔑 Join a server", "✨ Create a server", "🧭 Discover"])
        with t_join:
            with st.form("join"):
                key = st.text_input("Server code or name", value=st.query_params.get("s", ""), placeholder="K7Q2-9XMB or Night Owls")
                pw = st.text_input("Password", type="password")
                nick = st.text_input("Your nickname", max_chars=16, placeholder="NeonFox")
                if st.form_submit_button("Enter the Prism ✨"):
                    ok, res = hub.join(key, pw, nick)
                    if ok:
                        ss.sess = res
                        st.rerun()
                    st.error(res)
        with t_new:
            with st.form("create"):
                sname = st.text_input("Server name", max_chars=24, placeholder="Night Owls")
                spw = st.text_input("Set a password (4+ characters)", type="password")
                onick = st.text_input("Your nickname", max_chars=16, placeholder="Captain")
                listed = st.checkbox("Show this server in Discover (password still required)")
                if st.form_submit_button("Launch my server 🚀"):
                    ok, res = hub.create(sname, spw, onick, listed)
                    if ok:
                        ss.sess = res
                        st.rerun()
                    st.error(res)
        with t_disc:
            rooms = hub.listed()
            if not rooms:
                st.caption("No public servers yet - create one and tick 'Show in Discover'.")
            for name, n in rooms:
                st.markdown(f'<div class="glass room"><b>{esc(name)}</b> &nbsp;·&nbsp; 🟢 {n} online</div>', unsafe_allow_html=True)
            if rooms:
                st.caption("Type the server name in the Join tab and enter its password.")
    st.stop()


# ---------- room ----------
@st.fragment(run_every=2)
def live_room(sess):
    msgs = hub.fetch(sess)
    info = hub.info(sess)
    if msgs is None or info is None:
        ss.sess, ss.notice = None, "You were disconnected, kicked, or the server was closed."
        st.rerun()
    me = sess.nick
    st.markdown(
        f'<div class="glass head"><div><div class="srv">🌐 {esc(info["name"])}</div>'
        f'<div class="sub">👑 {esc(info["owner"])} · 🟢 {len(info["crew"])} online · you are <b>{esc(me)}</b></div></div>'
        f'<div class="chip">{esc(info["code"])}</div></div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns([3.4, 1.6])
    with left:
        feed = "".join(render(m, me) for m in reversed(msgs[-120:]))  # newest first (column-reverse)
        st.markdown(f'<div class="feed">{feed}</div>', unsafe_allow_html=True)
    with right:
        crew_tab, vault_tab = st.tabs(["👥 Crew", "📎 Vault"])
        with crew_tab:
            rows = "".join(
                f'<div class="user"><span class="dot"></span><span style="color:hsl({hue(n)},90%,72%)">{esc(n)}</span>'
                f'{" 👑" if own else ""}{" <small>(you)</small>" if n.lower() == me.lower() else ""}</div>'
                for n, own in info["crew"]
            )
            st.markdown(f'<div class="glass" style="padding:.8rem 1rem">{rows}</div>', unsafe_allow_html=True)
        with vault_tab:
            files = hub.files(sess)
            if not files:
                st.caption("Use the + in the message bar to share files (max 10 MB each).")
            for f in files[:12]:
                st.markdown(f'<div class="vfile"><b>{esc(f.name)}</b><br><small>{human(f.size)} · by {esc(f.uploader)}</small></div>',
                            unsafe_allow_html=True)
                if f.mime in IMG and f.size < 3_000_000:
                    st.image(f.data, width=210)
                st.download_button("⬇ Download", f.data, file_name=f.name, mime=f.mime, key=f"dl_{f.id}")


prompt = st.chat_input("Message, attach files with +, or /w name secret", accept_file="multiple")
if prompt:
    for f in prompt["files"] or []:
        ok, err = hub.send_file(ss.sess, f.name, f.getvalue(), f.type or "")
        if not ok:
            st.toast(f"{f.name}: {err}", icon="⚠️")
    if (prompt["text"] or "").strip():
        hub.post(ss.sess, prompt["text"])
live_room(ss.sess)
