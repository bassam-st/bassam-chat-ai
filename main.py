# main.py — Chat-Like مع تدوير مفاتيح Google/Gemini/OpenAI ثم بحث مجاني (DuckDuckGo)
import os, re, json, time, sqlite3
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from duckduckgo_search import DDGS

# ---------- إعداد المتغيرات من البيئة ----------
# ضع المفاتيح مفصولة بفاصلة (no spaces) أو اتركها فارغة
GOOGLE_KEYS_CSV = os.getenv("GOOGLE_KEYS", "").strip()
GEMINI_KEYS_CSV = os.getenv("GEMINI_KEYS", "").strip()
OPENAI_KEYS_CSV  = os.getenv("OPENAI_KEYS", "").strip()

GOOGLE_KEYS = [k for k in GOOGLE_KEYS_CSV.split(",") if k]
GEMINI_KEYS = [k for k in GEMINI_KEYS_CSV.split(",") if k]
OPENAI_KEYS = [k for k in OPENAI_KEYS_CSV.split(",") if k]

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
BASE = os.path.dirname(os.path.abspath(__file__))

# ---------- مسارات وتهيئة ----------
DATA = os.path.join(BASE, "data"); os.makedirs(DATA, exist_ok=True)
DB   = os.path.join(DATA, "threads.db")
KEY_STATE = os.path.join(DATA, "key_state.json")
STATIC_DIR = os.path.join(BASE, "static"); os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="Bassam — Chat with key rotation")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---------- DB خيوط ورسائل ----------
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

# ---------- حالة مفاتيح التدوير ----------
def load_key_state():
    if os.path.exists(KEY_STATE):
        try:
            with open(KEY_STATE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # بنية افتراضية
    s = {"google_idx":0, "gemini_idx":0, "openai_idx":0}
    save_key_state(s); return s

def save_key_state(s):
    try:
        with open(KEY_STATE, "w", encoding="utf-8") as f:
            json.dump(s, f)
    except Exception:
        pass

key_state = load_key_state()

def rotate_index(list_len:int, idx:int)->int:
    if list_len<=0: return 0
    return (idx+1) % list_len

# ---------- أدوات بحث مجاني (DuckDuckGo) ----------
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
    out, seen = [], set()
    for p in parts:
        p = re.sub(r"\s+"," ", p).strip(" -•،,")
        if len(p.split())>=4:
            key = p[:90]
            if key not in seen:
                seen.add(key); out.append(p)
        if len(out)>=m: break
    return out

# ---------- استدعاءات LLM مع التدوير ----------
# ملاحظة: ندعم طريقتين: Google (generative ai / Gemini) و OpenAI (openai python client).
# نحاول كل مفتاح بالتسلسل. إذا نجح أحدهم نستخدمه.

def try_gemini_with_key(key:str, prompt:str)->Optional[str]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        # استخدم نموذج افتراضي؛ يمكن تغييره إذا أردت
        model_name = "gemini-1.5-mini"  # قابل للتعديل
        # طريقة أبسط: generate_text (الأسماء API قد تختلف حسب نسخة حزمة)
        resp = genai.generate_text(model=model_name, prompt=prompt, max_output_tokens=512, temperature=0.4)
        text = ""
        if isinstance(resp, dict):
            # بعض إصدارات المكتبة ترجع dict
            text = resp.get("candidates", [{}])[0].get("content", "").strip()
        else:
            # كائن مخصص
            text = getattr(resp, "text", "") or getattr(resp, "content", "")
        return (text or "").strip()
    except Exception:
        return None

def try_openai_with_key(key:str, prompt:str)->Optional[str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        r = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role":"system","content":"أنت مساعد عربي. أجب بالعربية دائمًا وبإيجاز ووضوح."},
                {"role":"user","content":prompt}
            ],
            temperature=0.4,
            max_tokens=600
        )
        return (r.choices[0].message.content or "").strip()
    except Exception:
        return None

def llm_via_rotation(prompt:str)->Optional[str]:
    """
    تحاول استخدام مفاتيح Google (Gemini) أولاً، بالتدوير على GOOGLE_KEYS ثم GEMINI_KEYS،
    ثم OpenAI keys بالتدوير. تعيد النص أو None.
    """
    global key_state
    # 1) مفاتيح GOOGLE_KEYS (نعتبرها جاهزة لاستدعاء gemini أيضاً إن كانت تدعم)
    if GOOGLE_KEYS:
        idx = key_state.get("google_idx", 0) % len(GOOGLE_KEYS)
        for _ in range(len(GOOGLE_KEYS)):
            key = GOOGLE_KEYS[idx]
            out = try_gemini_with_key(key, prompt)
            if out:
                key_state["google_idx"] = rotate_index(len(GOOGLE_KEYS), idx)
                save_key_state(key_state)
                return out
            idx = rotate_index(len(GOOGLE_KEYS), idx)

    # 2) مفاتيح GEMINI_KEYS
    if GEMINI_KEYS:
        idx = key_state.get("gemini_idx", 0) % len(GEMINI_KEYS)
        for _ in range(len(GEMINI_KEYS)):
            key = GEMINI_KEYS[idx]
            out = try_gemini_with_key(key, prompt)
            if out:
                key_state["gemini_idx"] = rotate_index(len(GEMINI_KEYS), idx)
                save_key_state(key_state)
                return out
            idx = rotate_index(len(GEMINI_KEYS), idx)

    # 3) مفاتيح OPENAI_KEYS
    if OPENAI_KEYS:
        idx = key_state.get("openai_idx", 0) % len(OPENAI_KEYS)
        for _ in range(len(OPENAI_KEYS)):
            key = OPENAI_KEYS[idx]
            out = try_openai_with_key(key, prompt)
            if out:
                key_state["openai_idx"] = rotate_index(len(OPENAI_KEYS), idx)
                save_key_state(key_state)
                return out
            idx = rotate_index(len(OPENAI_KEYS), idx)

    return None

# ---------- واجهة HTML بسيطة ----------
HTML_PAGE = """
<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>بسام — Chat</title>
<style>body{background:#0b0f19;color:#e5e7eb;font-family:system-ui,Arial} .wrap{max-width:900px;margin:12px auto;padding:12px}
.card{background:#121826;border-radius:12px;padding:12px;margin-bottom:10px} .msg{white-space:pre-wrap;padding:10px;border-radius:10px;margin:8px 0}
.user{background:#0f1421} .assistant{background:#0f1220;border:1px solid #2a2f45} input{width:100%;padding:12px;border-radius:10px;border:1px solid #1f2937;background:#0f1421;color:#fff}
button{padding:10px 14px;border-radius:10px;background:#7c3aed;color:#fff;border:none;font-weight:700}
.ts{opacity:.75;font-size:12px;display:block;margin-bottom:6px}
</style></head><body>
<div class="wrap">
  <h2>بسام — دردشة (تدوير مفاتيح / بحث مجاني)</h2>
  <div id="chat" class="card"></div>
  <form class="card" onsubmit="return sendMsg()">
    <input id="q" placeholder="اكتب سؤالك..." required />
    <div style="height:8px"></div>
    <button type="submit">إرسال</button>
  </form>
  <div style="margin-top:8px;color:#98a2b3">وضع المفاتيح: GOOGLE_KEYS({{g}}) • GEMINI_KEYS({{gm}}) • OPENAI_KEYS({{oa}})</div>
</div>
<script>
const chat = document.getElementById('chat');
function addMsg(txt, who){
  const d=document.createElement('div'); d.className='msg '+who;
  const ts=document.createElement('div'); ts.className='ts'; ts.textContent=new Date().toISOString();
  d.appendChild(ts); d.appendChild(document.createTextNode("\\n"+txt)); chat.appendChild(d); chat.scrollTop=chat.scrollHeight;
}
addMsg("مرحبًا! اسألني. سأحاول استخدام مفاتيحك ذات الترتيب ثم البحث المجاني.", "assistant");
async function sendMsg(){
  const q = document.getElementById('q'); const v=q.value.trim(); if(!v) return false;
  addMsg(v, "user"); q.value='';
  const es = new EventSource('/api/ask_sse?q='+encodeURIComponent(v));
  let buf="";
  const holder=document.createElement('div'); holder.className='msg assistant';
  const ts=document.createElement('div'); ts.className='ts'; ts.textContent=new Date().toISOString();
  holder.appendChild(ts); const tn=document.createTextNode('...'); holder.appendChild(tn); chat.appendChild(holder);
  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if(d.chunk){ buf += d.chunk; holder.childNodes[1].nodeValue = "\\n"+buf; chat.scrollTop=chat.scrollHeight; }
      if(d.done) { es.close(); }
    } catch(err){}
  };
  es.onerror = ()=>{ es.close(); };
  return false;
}
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    ensure_thread()
    # نعرض أرقام المفاتيح المتاحة للعلم (لا نعرض المفاتيح الحقيقية)
    g = len(GOOGLE_KEYS); gm = len(GEMINI_KEYS); oa = len(OPENAI_KEYS)
    page = HTML_PAGE.replace("{{g}}", str(g)).replace("{{gm}}", str(gm)).replace("{{oa}}", str(oa))
    return page

@app.get("/status")
def status():
    mode = "Free Search"
    if GOOGLE_KEYS or GEMINI_KEYS: mode = "Gemini/Google keys available"
    if OPENAI_KEYS: mode = "OpenAI keys available"
    return {"mode":mode}

# ---------- SSE endpoint: محاولة LLM ثم بحث مجاني ----------
@app.get("/api/ask_sse")
def ask_sse(q: str, request: Request):
    q = (q or "").strip()
    tid = ensure_thread()
    add_msg(tid, "user", q)

    def stream():
        # 1) حاول LLM عبر تدوير المفاتيح
        prompt = f"أجب بالعربية: {q}\nأعطِ إجابة موجزة واضحة. إن احتجت بيانات، استند إلى مقتطفات الوب التالية."
        llm_resp = llm_via_rotation(prompt)
        if llm_resp:
            add_msg(tid, "assistant", llm_resp)
            for part in llm_resp.split("\n"):
                yield "data: "+json.dumps({"chunk":part+"\n"})+"\n\n"; time.sleep(0.01)
            yield "data: "+json.dumps({"done":True})+"\n\n"
            return

        # 2) fallback: بحث مجاني + تلخيص عربي
        try:
            results = ddg_search(q, 8)
        except Exception:
            results = []
        bullets = bullets_from_snips([r.get("snippet","") for r in results], 8)
        if not bullets and not results:
            msg = "لم أجد نتائج كافية الآن. جرّب إعادة صياغة السؤال."
            add_msg(tid, "assistant", msg)
            yield "data: "+json.dumps({"chunk":msg,"done":True})+"\n\n"
            return

        header = "هذا ملخص عربي موجز:\n"
        yield "data: "+json.dumps({"chunk":header})+"\n\n"; time.sleep(0.02)
        for b in bullets[:6]:
            yield "data: "+json.dumps({"chunk":"• "+b+"\n"})+"\n\n"; time.sleep(0.02)
        if results:
            yield "data: "+json.dumps({"chunk":"\nأهم الروابط:\n"})+"\n\n"
            for r in results[:5]:
                yield "data: "+json.dumps({"chunk":f"- {r['title']}: {r['link']}\n"})+"\n\n"; time.sleep(0.01)
        closing = "\nلمتابعة نقطة محددة، اكتب: (عن النقطة ...)."
        yield "data: "+json.dumps({"chunk":closing,"done":True})+"\n\n"
        full = header + "".join("• "+b+"\n" for b in bullets[:6])
        if results:
            full += "\nأهم الروابط:\n" + "\n".join(f"- {r['title']}: {r['link']}" for r in results[:5])
        full += closing
        add_msg(tid, "assistant", full)

    return StreamingResponse(stream(), media_type="text/event-stream")

# ---------- ملفات PWA خفيفة ----------
@app.get("/sw.js")
def sw_js():
    return HTMLResponse("self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>self.clients.claim());",
                        media_type="application/javascript")

@app.get("/static/pwa/manifest.json")
def manifest():
    return JSONResponse({
        "name":"Bassam Chat",
        "short_name":"Bassam",
        "start_url":"/",
        "display":"standalone",
        "background_color":"#0b0f19",
        "theme_color":"#7c3aed",
    })

@app.get("/healthz")
def health(): return {"ok": True}
