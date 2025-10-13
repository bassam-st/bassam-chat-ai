# main.py — Chat-Like (Gemini/OpenAI fallback) + Free Web Search + SSE + Arabic replies
import os, re, json, time, sqlite3
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from duckduckgo_search import DDGS

# ---------- مفاتيح البيئة (اختياري) ----------
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "").strip()
LLM_MODEL        = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()  # لو استُخدم OpenAI
PORT             = int(os.getenv("PORT", "10000"))

# ---------- إعدادات أساسية ----------
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data"); os.makedirs(DATA, exist_ok=True)
DB   = os.path.join(DATA, "threads.db")

STATIC_DIR = os.path.join(BASE, "static"); os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="Bassam — Chat-Like (Smart Fallback)")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---------- قاعدة بيانات خيوط/رسائل بسيطة ----------
def db():
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; return con

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")+"Z"

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS threads(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL
        );""")
        con.execute("""CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL
        );""")
init_db()

def ensure_thread()->int:
    with db() as con:
        r = con.execute("SELECT id FROM threads ORDER BY id DESC LIMIT 1").fetchone()
        if r: return r["id"]
        cur = con.execute("INSERT INTO threads(created_at) VALUES(?)", (now_iso(),))
        return cur.lastrowid

def add_msg(tid:int, role:str, text:str):
    with db() as con:
        con.execute("INSERT INTO messages(thread_id,ts,role,text) VALUES(?,?,?,?)",
                    (tid, now_iso(), role, text))

def last_msgs(tid:int, n:int=8)->List[Dict]:
    with db() as con:
        rows = con.execute("""SELECT role, text, ts FROM messages
                              WHERE thread_id=? ORDER BY id DESC LIMIT ?""", (tid,n)).fetchall()
    return [dict(r) for r in rows][::-1]

# ---------- أدوات بحث مجاني ----------
def ddg_search(q:str, k:int=8)->List[Dict]:
    out=[]
    with DDGS() as d:
        for r in d.text(q, region="xa-ar", safesearch="moderate", max_results=k):
            out.append({"title": r.get("title",""),
                        "link": r.get("href") or r.get("url") or "",
                        "snippet": r.get("body","")})
            if len(out)>=k: break
    return out

def _clean(s:str)->str:
    return re.sub(r"[^\w\s\u0600-\u06FF]", " ", (s or "").strip())

def bullets_from_snips(snips:List[str], m:int=8)->List[str]:
    txt = " ".join(_clean(x) for x in snips if x).strip()
    parts = re.split(r"[.!؟\n]", txt)
    out, seen=set(), []
    for p in parts:
        p = re.sub(r"\s+"," ", p).strip(" -•،,")
        if len(p.split())>=4:
            key = p[:90]
            if key not in out:
                out.add(key)
                seen.append(p)
        if len(seen)>=m: break
    return seen

# ---------- نماذج LLM (اختياري) ----------
_use_gemini = False
_use_openai = False
_gem_model  = None
_oa_client  = None

if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _gem_model = genai.GenerativeModel("gemini-1.5-flash")
        _use_gemini = True
    except Exception:
        _use_gemini = False

if (not _use_gemini) and OPENAI_API_KEY:
    try:
        from openai import OpenAI
        _oa_client = OpenAI(api_key=OPENAI_API_KEY)
        _use_openai = True
    except Exception:
        _use_openai = False

AR_SYS_PROMPT = (
    "أنت مساعد عربي ودود وعملي. ردّ بإيجاز واضح وبالعربية دائمًا. "
    "إن احتجت مصادر فاذكر أهم رابطين. إن لم تكن واثقًا قل: لا أعلم."
)

async def llm_answer(question:str, web_context:str="")->str:
    """يرد عبر Gemini أو OpenAI أو يرجع نصًا فارغًا لو لا يوجد مفاتيح."""
    if _use_gemini:
        try:
            prompt = f"{AR_SYS_PROMPT}\n\nسؤال المستخدم:\n{question}\n\nمقتطفات لل参考:\n{web_context}\n\nأعطني جوابًا عربيًا موجزًا ثم نقاطًا مختصرة."
            r = _gem_model.generate_content(prompt)
            return (r.text or "").strip()
        except Exception:
            return ""
    if _use_openai:
        try:
            r = _oa_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role":"system","content":AR_SYS_PROMPT},
                    {"role":"user","content":f"سؤال:\n{question}\n\nمقتطفات:\n{web_context}\n\nاكتب جوابًا عربيًا موجزًا ثم نقاطًا."}
                ],
                temperature=0.4,
                max_tokens=600
            )
            return (r.choices[0].message.content or "").strip()
        except Exception:
            return ""
    return ""  # لا مفاتيح

# ---------- صفحة HTML بسيطة (تشبه Chat) ----------
HTML_PAGE = """
<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>بسام — Chat-Like</title>
<meta name="theme-color" content="#7c3aed"/>
<style>
:root{--bg:#0b0f19;--card:#121826;--pri:#7c3aed;--muted:#98a2b3}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:#e5e7eb;
font-family:system-ui,Segoe UI,Roboto,"Noto Naskh Arabic UI","Noto Kufi Arabic",Tahoma,Arial,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:12px}
.card{background:#121826;border:1px solid #1f2937;border-radius:16px;padding:12px}
.msg{white-space:pre-wrap;line-height:1.7;margin:10px 0;padding:12px;border-radius:12px}
.user{background:#0f1421} .assistant{background:#0f1220;border:1px solid #2a2f45}
.row{display:flex;gap:8px;flex-wrap:wrap} input[type=text]{flex:1;min-width:200px;padding:12px;border-radius:12px;border:1px solid #1f2937;background:#0f1421;color:#fff}
button{padding:12px 16px;border:none;border-radius:12px;background:var(--pri);color:#fff;font-weight:700;cursor:pointer}
.ts{opacity:.75;font-size:12px;display:block;margin-bottom:4px}
.note{color:var(--muted);font-size:13px;margin-top:6px}
</style></head><body>
<div class="wrap">
  <h2>بسام — دردشة عربية تشبه ChatGPT (بحث مجاني + مفاتيح اختيارية)</h2>
  <div id="chat" class="card"></div>
  <form class="card row" onsubmit="return sendMsg()">
    <input id="q" type="text" placeholder="اكتب سؤالك هنا..." required />
    <button type="submit">إرسال</button>
  </form>
  <div class="note">المود: <span id="mode">Free Search</span> • إذا أضفت مفاتيح <b>GEMINI_API_KEY</b> أو <b>OPENAI_API_KEY</b> سيكتب مثل ChatGPT.</div>
</div>
<script>
const mode = document.getElementById('mode');
fetch('/status').then(r=>r.json()).then(j=>{mode.textContent=j.mode;}).catch(()=>{});
const chat = document.getElementById('chat');
function addMsg(txt, who){
  const d=document.createElement('div'); d.className='msg '+who;
  const ts=document.createElement('span'); ts.className='ts'; ts.textContent=new Date().toISOString();
  d.appendChild(ts); d.appendChild(document.createTextNode("\\n"+txt)); chat.appendChild(d); chat.scrollTop=chat.scrollHeight;
}
addMsg("👋 أهلاً! اكتب سؤالك وسأجيبك فورًا — إذا وُجد مفتاح OpenAI أو Gemini أعمل مثل ChatGPT، وإلا ألخّص من الويب بالعربية.", "assistant");
async function sendMsg(){
  const inp=document.getElementById('q'); const t=inp.value.trim(); if(!t) return false;
  addMsg(t,"user"); inp.value="";
  const es=new EventSource('/api/ask_sse?q='+encodeURIComponent(t));
  let buf=""; const holder=document.createElement('div'); holder.className='msg assistant';
  const ts=document.createElement('span'); ts.className='ts'; ts.textContent=new Date().toISOString();
  holder.appendChild(ts); const tn=document.createTextNode('...'); holder.appendChild(tn); chat.appendChild(holder);
  es.onmessage=(e)=>{const d=JSON.parse(e.data); if(d.chunk){buf+=d.chunk; holder.childNodes[1].nodeValue="\\n"+buf; chat.scrollTop=chat.scrollHeight;} if(d.done){es.close();}};
  es.onerror=()=>{es.close();};
  return false;
}
</script>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    ensure_thread()
    return HTML_PAGE

@app.get("/status")
def status():
    if _use_gemini: m = "Gemini"
    elif _use_openai: m = f"OpenAI ({LLM_MODEL})"
    else: m = "Free Search"
    return {"mode": m}

# ---------- SSE: منطق الإجابة ----------
@app.get("/api/ask_sse")
def ask_sse(q: str, request: Request):
    q = (q or "").strip()
    tid = ensure_thread()
    add_msg(tid, "user", q)

    def stream():
        # لو معنا LLM → نحاول الرد مباشرة (مع بحث خفيف عند الحاجة)
        factual = any(k in q for k in ["ما هو", "من هو", "أين", "متى", "كم", "خبر", "سعر", "تعريف", "نتيجة"])
        web_summary = ""
        if (_use_gemini or _use_openai) and factual:
            try:
                res = ddg_search(q, 6)
                bullets = bullets_from_snips([r["snippet"] for r in res], 6)
                web_summary = " • ".join(bullets[:4])
            except Exception:
                web_summary = ""

        if _use_gemini or _use_openai:
            ans = ""
            try:
                import asyncio
                ans = asyncio.run(llm_answer(q, web_summary))
            except Exception:
                ans = ""
            if ans:
                add_msg(tid, "assistant", ans)
                for part in ans.split("\n"):
                    yield "data: "+json.dumps({"chunk":part+"\n"})+"\n\n"; time.sleep(0.01)
                yield "data: "+json.dumps({"done":True})+"\n\n"; return

        # ---- وضع البحث المجاني (بدون مفاتيح) ----
        try:
            res = ddg_search(q, 8)
        except Exception:
            res = []
        bullets = bullets_from_snips([r.get("snippet","") for r in res], 8)
        if not bullets and not res:
            fallback = "لم أعثر على نتائج كافية الآن. جرّب صياغة أخرى أو سؤالًا أوضح."
            add_msg(tid, "assistant", fallback)
            yield "data: "+json.dumps({"chunk":fallback, "done":True})+"\n\n"; return

        header = f"هذا ملخص عربي موجز:\n"
        yield "data: "+json.dumps({"chunk":header})+"\n\n"; time.sleep(0.02)
        for b in bullets[:6]:
            yield "data: "+json.dumps({"chunk":"• "+b+"\n"})+"\n\n"; time.sleep(0.02)
        if res:
            yield "data: "+json.dumps({"chunk":"\nأهم الروابط:\n"})+"\n\n"
            for r in res[:5]:
                line = f"- {r['title']}: {r['link']}\n"
                yield "data: "+json.dumps({"chunk":line})+"\n\n"; time.sleep(0.01)
        closing = "\nلمتابعة نقطة محددة، اكتب: (عن النقطة …) أو اقتبس سطرًا."
        yield "data: "+json.dumps({"chunk":closing, "done":True})+"\n\n"
        full = header + "".join("• "+b+"\n" for b in bullets[:6]) + \
               ("\nأهم الروابط:\n" + "\n".join(f"- {r['title']}: {r['link']}" for r in res[:5]) if res else "") + closing
        add_msg(tid, "assistant", full)

    return StreamingResponse(stream(), media_type="text/event-stream")

# ---------- PWA بسيط (اختياري خفيف) ----------
@app.get("/sw.js")
def sw_js():
    return HTMLResponse(
        "self.addEventListener('install',e=>self.skipWaiting());"
        "self.addEventListener('activate',e=>self.clients.claim());"
        "self.addEventListener('fetch',()=>{});",
        media_type="application/javascript"
    )

@app.get("/static/pwa/manifest.json")
def manifest():
    return JSONResponse({
        "name":"Bassam Chat-Like",
        "short_name":"Bassam",
        "start_url":"/",
        "display":"standalone",
        "background_color":"#0b0f19",
        "theme_color":"#7c3aed",
        "icons":[
            {"src":"/static/icon-192.png","sizes":"192x192","type":"image/png"},
            {"src":"/static/icon-512.png","sizes":"512x512","type":"image/png"}
        ]
    })

@app.get("/healthz")
def health(): return {"ok": True}
