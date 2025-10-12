# main.py — تشات بسام: صفحة واحدة، وعي متابعة، SSE، بحث مجاني + مفاتيح اختيارية
import os, sqlite3, re, json, time, asyncio
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import httpx
from duckduckgo_search import DDGS

# ===================== إعدادات ومجلدات =====================
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data"); os.makedirs(DATA, exist_ok=True)
DB_PATH = os.path.join(DATA, "chat.db")

STATIC_DIR = os.path.join(BASE, "static"); os.makedirs(STATIC_DIR, exist_ok=True)
ICONS_DIR = os.path.join(STATIC_DIR, "icons"); os.makedirs(ICONS_DIR, exist_ok=True)

# مفاتيح اختيارية:
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()        # Google via Serper (اختياري)
BRAVE_API_KEY  = os.getenv("BRAVE_API_KEY", "").strip()         # Brave Search API (اختياري)

app = FastAPI(title="Bassam Chat — Single Page, Aware")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ===================== قاعدة البيانات: خيوط ومحادثات =====================
def db():
    con = sqlite3.connect(DB_PATH); con.row_factory = sqlite3.Row
    return con

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")+"Z"

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS threads(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, created_at TEXT NOT NULL
        );""")
        con.execute("""CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL, ts TEXT NOT NULL,
            role TEXT NOT NULL, text TEXT NOT NULL,
            FOREIGN KEY(thread_id) REFERENCES threads(id)
        );""")
init_db()

def new_thread(title="محادثة جديدة")->int:
    with db() as con:
        cur = con.execute("INSERT INTO threads(title,created_at) VALUES(?,?)",(title,now_iso()))
        return cur.lastrowid

def list_threads()->List[Dict]:
    with db() as con:
        rows = con.execute("SELECT id,title,created_at FROM threads ORDER BY id DESC LIMIT 100").fetchall()
    return [dict(r) for r in rows]

def get_messages(tid:int)->List[Dict]:
    with db() as con:
        rows = con.execute("SELECT role,text,ts FROM messages WHERE thread_id=? ORDER BY id ASC",(tid,)).fetchall()
    return [dict(r) for r in rows]

def add_msg(tid:int, role:str, text:str):
    with db() as con:
        con.execute("INSERT INTO messages(thread_id,ts,role,text) VALUES(?,?,?,?)",(tid,now_iso(),role,text))

# ===================== وعي المتابعة (نصّيات) =====================
AR_VARIANTS = str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه"})
def normalize_ar(s:str)->str: return (s or "").strip().lower().translate(AR_VARIANTS)

FOLLOWUP_HINTS = ["النقطه","النقطة","وضح","توضيح","المقصود","هذا","تلك","سابق","الاول","الأول","تابع","بالنسبه","بالنسبة"]
def is_followup(q:str)->bool:
    nq = normalize_ar(q); return any(h in nq for h in FOLLOWUP_HINTS)

TOKEN_SPLIT = re.compile(r"[^\w\u0600-\u06FF]+")
def tokenize_ar(s:str): return [t for t in TOKEN_SPLIT.split(normalize_ar(s)) if t and len(t)>=2]

def extract_keywords(texts:List[str], top:int=12)->List[str]:
    freq={}
    for t in texts:
        for tok in tokenize_ar(t):
            if tok in {"هذا","هذه","ذلك","الى","على","من","في","عن","او","ثم","مع","كان","انا","انت","هو","هي","هم"}:
                continue
            freq[tok]=freq.get(tok,0)+1
    return [k for k,_ in sorted(freq.items(), key=lambda x:(x[1],len(x[0])), reverse=True)[:top]]

def last_texts(tid:int, n:int=8)->List[str]:
    msgs = get_messages(tid)
    return [f"{m['role']}:{m['text']}" for m in msgs[-n:]]

def condense_context(tid:int, n:int=8)->str:
    lines = last_texts(tid, n)
    if not lines: return ""
    keys = extract_keywords(lines, top=14)
    lastQ = next((m['text'] for m in get_messages(tid)[::-1] if m['role']=='user'), "")
    return f"سياق قصير: ({'؛ '.join(keys[:10])}). اخر سؤال: {lastQ[:160]}"

def contextualize_query(tid:int, q:str)->str:
    return f"{q} — [متابعة: {condense_context(tid)}]" if is_followup(q) else q

# ===================== محركات البحث (مجانية + اختيارية) =====================
def url_domain(u:str)->str:
    m=re.search(r"https?://([^/]+)/?", u or ""); return (m.group(1) if m else u or "").lower()

def merge_results(a:List[Dict], b:List[Dict], limit:int=10)->List[Dict]:
    seen=set(); out=[]
    for lst in (a,b):
        for r in lst:
            sig=(url_domain(r.get("link","")), (r.get("title","") or "")[:50])
            if sig in seen: continue
            seen.add(sig); out.append(r)
            if len(out)>=limit: break
    return out

def _clean(s:str)->str: return re.sub(r"[^\w\s\u0600-\u06FF]", " ", (s or "").strip())
def bullets_from_snips(snips:List[str], m:int=8)->List[str]:
    txt = " ".join(_clean(s) for s in snips if s).strip()
    parts = re.split(r"[.!؟\n]", txt); seen=set(); out=[]
    for p in parts:
        p = re.sub(r"\s+"," ", p).strip(" -•،,")
        if len(p.split())>=4:
            key=p[:90]
            if key not in seen: seen.add(key); out.append(p)
        if len(out)>=m: break
    return out

def ddg_text(q: str, k: int = 8) -> List[Dict]:
    """DuckDuckGo (نصي) — مجاني."""
    out=[]
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(q, region="xa-ar", safesearch="moderate", max_results=k):
                out.append({"title":r.get("title",""),"link":r.get("href") or r.get("url") or "","snippet":r.get("body","")})
                if len(out)>=k: break
    except Exception:
        pass
    # محاولة مناطق أخرى لو صفر
    if not out:
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(q, region="us-en", safesearch="moderate", max_results=k):
                    out.append({"title":r.get("title",""),"link":r.get("href") or r.get("url") or "","snippet":r.get("body","")})
                    if len(out)>=k: break
        except Exception:
            pass
    return out

async def ddg_instant(q:str, k:int=6)->List[Dict]:
    """DuckDuckGo Instant Answer — مجاني."""
    url=f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            r = await cl.get(url); data = r.json()
    except Exception:
        return []
    out=[]
    abs_txt = (data.get("AbstractText") or "").strip()
    if abs_txt:
        out.append({"title": data.get("Heading") or "ملخص","link": data.get("AbstractURL") or "","snippet": abs_txt})
    for t in (data.get("RelatedTopics") or []):
        if isinstance(t, dict):
            txt = (t.get("Text") or "").strip()
            href = (t.get("FirstURL") or "").strip()
            if txt:
                out.append({"title": txt[:60], "link": href, "snippet": txt})
                if len(out)>=k: break
    return out

async def serper_google(q:str, k:int=8)->List[Dict]:
    """Google via Serper — يتطلب SERPER_API_KEY (اختياري)."""
    if not SERPER_API_KEY: return []
    url="https://google.serper.dev/search"
    headers={"X-API-KEY":SERPER_API_KEY,"Content-Type":"application/json"}
    payload={"q":q,"num":k,"hl":"ar"}
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            r=await cl.post(url, headers=headers, json=payload)
            data=r.json()
    except Exception:
        return []
    out=[]
    for it in (data.get("organic",[]) or [])[:k]:
        out.append({"title": it.get("title",""), "link": it.get("link",""), "snippet": it.get("snippet","")})
    return out

async def brave_search(q:str, k:int=8)->List[Dict]:
    """Brave Search — يتطلب BRAVE_API_KEY (اختياري)."""
    if not BRAVE_API_KEY: return []
    url=f"https://api.search.brave.com/res/v1/web/search?q={q}&count={k}&source=web"
    headers={"Accept":"application/json","X-Subscription-Token":BRAVE_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            r=await cl.get(url, headers=headers)
            data=r.json()
    except Exception:
        return []
    out=[]
    for it in (data.get("web",{}).get("results",[]) or [])[:k]:
        out.append({"title": it.get("title",""), "link": it.get("url",""), "snippet": it.get("description","")})
    return out

def rough_en(q: str) -> str:
    """ترجمة بدائية لكلمات شائعة كخطة (C) عند فشل العربي."""
    rep = {
        "اين":"where","أين":"where","تقع":"is","ماهو":"what is","ما هو":"what is",
        "اليمن":"Yemen","السعوديه":"Saudi Arabia","السعودية":"Saudi Arabia"
    }
    s=q
    for ar,en in rep.items(): s=s.replace(ar,en)
    return s

async def smart_search(q:str, k:int=10)->Dict:
    """تجميع نتائج من عدّة مصادر (مجاني + مفاتيح اختيارية)."""
    resA = ddg_text(q, k)
    resB = await ddg_instant(q, k)
    resC = await serper_google(q, k) if SERPER_API_KEY else []
    resD = await brave_search(q, k) if BRAVE_API_KEY else []

    merged = merge_results(resA, resB, k)
    merged = merge_results(merged, resC, k)
    merged = merge_results(merged, resD, k)

    bullets = bullets_from_snips([r.get("snippet") for r in merged], 8)

    # لو النتائج ضعيفة جدًا: أعد المحاولة بالإنجليزية
    if not merged or len(bullets) < 2:
        qq = rough_en(q)
        extra = ddg_text(qq, k) + (await ddg_instant(qq, k))
        merged = merge_results(merged, extra, k)
        bullets = bullets_from_snips([r.get("snippet") for r in merged], 8)

    return {"results": merged, "bullets": bullets}

# ===================== هوية/خصوصية (حسب طلبك) =====================
def id_or_privacy_reply(nq:str)->Optional[str]:
    if ("من هو بسام" in nq) or ("من هو بسام الذكي" in nq) or ("من هو بسام الشتيمي" in nq) \
       or ("من صنع التطبيق" in nq) or ("من المطور" in nq) or ("من هو صاحب التطبيق" in nq):
        return "بسام الشتيمي هو منصوريّ الأصل، وهو صانع هذا التطبيق."
    if ("اسم ام بسام" in nq) or ("اسم ام بسام الشتيمي" in nq) or ("اسم زوجة بسام" in nq) or ("مرت بسام" in nq):
        return "حرصًا على الخصوصية، لا يقدّم بسام معلومات شخصية مثل أسماء أفراد العائلة. رجاءً تجنّب مشاركة بيانات حساسة."
    return None

# ===================== صفحة واحدة (HTML + JS) =====================
HTML_PAGE = """<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>بسام — محادثة بوعي متابعة</title>
<link rel="manifest" href="/static/pwa/manifest.json"/><meta name="theme-color" content="#7c3aed"/>
<style>
:root{--bg:#0b0f19;--card:#121826;--muted:#98a2b3;--pri:#7c3aed}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#e5e7eb;font-family:system-ui,Segoe UI,Roboto,"Noto Naskh Arabic UI","Noto Kufi Arabic",Tahoma,Arial,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:14px}.header{display:flex;gap:10px;align-items:center;justify-content:space-between}
h1{margin:8px 0;font-size:18px}.layout{display:grid;grid-template-columns:260px 1fr;gap:12px}
@media (max-width:900px){.layout{grid-template-columns:1fr}}
.card{background:var(--card);border-radius:14px;padding:12px;border:1px solid #1f2937}
input[type=text]{width:100%;padding:12px;border-radius:12px;border:1px solid #1f2937;background:#0f1421;color:#fff}
.msg{white-space:pre-wrap;line-height:1.7;margin:8px 0;padding:10px;border-radius:10px}
.user{background:#0f1421}.assistant{background:#0f1220;border:1px solid #2a2f45}
.ts{opacity:.75;font-size:12px;display:block;margin-bottom:4px}
ul{list-style:none;margin:0;padding:0}.thread{padding:8px;border-radius:10px;cursor:pointer;border:1px solid #1f2937;margin-bottom:8px;display:block;color:#e5e7eb;text-decoration:none}
.thread.active{border-color:#7c3aed;background:#151b2b}
.install{position:fixed;right:12px;bottom:12px;background:#7c3aed;border:none;color:#fff;border-radius:12px;padding:10px 14px;font-weight:700}
.footer{color:var(--muted);text-align:center;margin-top:18px}
.hint{color:#c4b5fd;font-size:13px}
</style></head><body>
<div class="wrap">
  <div class="header">
    <h1>بسام — محادثة بوعي متابعة</h1>
    <form action="/thread/new" method="post" style="margin:0"><!-- لا أزرار إضافية --></form>
  </div>
  <div class="layout">
    <div class="card">
      <h3>المحادثات</h3>
      <ul id="threads"></ul>
      <div class="hint">لبدء محادثة جديدة اكتب: <b>محادثة جديدة</b></div>
    </div>
    <div class="card">
      <div id="chat"></div>
      <input id="q" type="text" placeholder="اكتب سؤالك ثم Enter…" autocomplete="off"/>
    </div>
  </div>
  <div class="footer">© Bassam 2025 — بحث متعدد المصادر + وعي متابعة • يدعم التثبيت PWA</div>
</div>
<script>
// PWA: زر التثبيت يظهر تلقائيًا
let deferredPrompt=null;window.addEventListener("beforeinstallprompt",(e)=>{e.preventDefault();deferredPrompt=e;
  const b=document.createElement("button");b.className="install";b.textContent="📱 تثبيت بسام";
  b.onclick=async()=>{b.style.display="none";deferredPrompt.prompt();await deferredPrompt.userChoice;deferredPrompt=null;};
  document.body.appendChild(b);
});
if("serviceWorker" in navigator){navigator.serviceWorker.register("/sw.js").catch(()=>{});}

const chat = document.getElementById('chat');
const q    = document.getElementById('q');
const tl   = document.getElementById('threads');
let tid = 0;

function addMsg(txt,who){
  const d=document.createElement('div'); d.className='msg '+who;
  const ts=document.createElement('span'); ts.className='ts'; ts.textContent=new Date().toISOString();
  d.appendChild(ts); d.appendChild(document.createTextNode("\\n"+txt));
  chat.appendChild(d); chat.scrollTop=chat.scrollHeight;
}

async function loadThreads(){
  const r=await fetch('/threads'); const j=await r.json();
  tl.innerHTML=''; j.threads.forEach(t=>{
    const a=document.createElement('a'); a.href='/?t='+t.id; a.className='thread'+(t.id===j.cur?' active':'');
    a.textContent='#'+t.id+' — '+(t.title||'بدون عنوان');
    const sub=document.createElement('div'); sub.className='ts'; sub.textContent=t.created_at; a.appendChild(sub);
    const li=document.createElement('li'); li.appendChild(a); tl.appendChild(li);
  });
  tid=j.cur;
}
async function loadPage(){
  await loadThreads();
  const r=await fetch('/messages?t='+tid); const j=await r.json();
  chat.innerHTML=''; j.msgs.forEach(m=>{ const d=document.createElement('div'); d.className='msg '+m.role;
    const ts=document.createElement('span'); ts.className='ts'; ts.textContent=m.ts;
    d.appendChild(ts); d.appendChild(document.createTextNode("\\n"+m.text)); chat.appendChild(d); });
  if(j.msgs.length===0){ addMsg("مرحبًا! أنا بسام — اسألني أي شيء، وسأبحث من أجلك وألخّص لك أهم النقاط مع روابط.", "assistant"); }
}
q.addEventListener('keydown', (e)=>{
  if(e.key==='Enter'){
    const text=q.value.trim(); if(!text) return;
    if(text==='محادثة جديدة'){ fetch('/thread/new',{method:'POST'}).then(()=>location.href='/'); return; }
    addMsg(text,'user'); q.value='';
    ask(text);
  }
});
async function ask(text){
  try{
    // أولاً نحاول SSE
    const url=`/api/ask_sse?q=${encodeURIComponent(text)}&tid=${tid}`;
    const es=new EventSource(url);
    let buf=''; const holder=document.createElement('div'); holder.className='msg assistant';
    const ts=document.createElement('span'); ts.className='ts'; ts.textContent=new Date().toISOString();
    holder.appendChild(ts); const tn=document.createTextNode('...'); holder.appendChild(tn); chat.appendChild(holder);
    es.onmessage=(e)=>{const d=JSON.parse(e.data); if(d.chunk){buf+=d.chunk; holder.childNodes[1].nodeValue="\\n"+buf; chat.scrollTop=chat.scrollHeight;} if(d.done){es.close();}};
    es.onerror=()=>{es.close(); fallback(text);};
  }catch(_){ fallback(text); }
}
async function fallback(text){
  try{
    const r = await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:text, tid:tid})});
    const j = await r.json(); addMsg(j.answer || 'تعذر الحصول على نتيجة الآن.', 'assistant');
  }catch(_){ addMsg('تعذر الاتصال بالخادم الآن.', 'assistant'); }
}
loadPage();
</script>
</body></html>
"""

# ===================== صفحات / API مساعدة للواجهة =====================
@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE

@app.get("/threads")
def threads_json():
    threads = list_threads()
    cur = threads[0]["id"] if threads else new_thread()
    return {"threads": threads, "cur": cur}

@app.get("/messages")
def messages_json(t: Optional[int] = None):
    threads = list_threads()
    if t is None: t = threads[0]["id"] if threads else new_thread()
    msgs = get_messages(t)
    return {"msgs": msgs, "cur": t}

@app.post("/thread/new")
def create_thread(title: str = Form("محادثة جديدة")):
    tid = new_thread(title.strip() or "محادثة جديدة")
    return RedirectResponse(url=f"/?t={tid}", status_code=303)

# ===================== SSE مع Heartbeat + احتياطي غير متدفق =====================
def intro_or_privacy(nq:str) -> Optional[str]:
    # هويّة وخصوصية كما طلبت
    rep = id_or_privacy_reply(nq)
    if rep: return rep
    # تعريف بسيط عند سؤال "من أنت"
    if "من انت" in nq or "من انت؟" in nq:
        return "أنا بسام — مساعدك الذكي. أسألني، وسأبحث وألخّص لك أهم النقاط مع روابط."
    return None

@app.get("/api/ask_sse")
async def ask_sse(request: Request, q: str, tid: int):
    q = (q or "").strip()
    if not q:
        async def gen_err():
            yield "data: " + json.dumps({"chunk":"⚠️ الرجاء كتابة سؤالك أولًا."}) + "\n\n"
        return StreamingResponse(gen_err(), media_type="text/event-stream")

    nq = normalize_ar(q)
    add_msg(tid,"user",f"[{now_iso()}] {q}")

    async def streamer():
        last_ping = time.time()

        quick = intro_or_privacy(nq)
        if quick:
            add_msg(tid,"assistant",f"[{now_iso()}] {quick}")
            yield "data: " + json.dumps({"chunk":quick,"done":True}) + "\n\n"
            return

        contextual_q = contextualize_query(tid, q)
        data = await smart_search(contextual_q, 10)
        results, bullets = data["results"], data["bullets"]

        opening = f"[{now_iso()}] تمام! هذا ملخص حسب سياق محادثتنا:\n"
        yield "data: " + json.dumps({"chunk":opening}) + "\n\n"
        await asyncio.sleep(0.02)

        if bullets:
            for b in bullets:
                yield "data: " + json.dumps({"chunk":"• "+b+"\n"}) + "\n\n"
                await asyncio.sleep(0.01)
        else:
            yield "data: " + json.dumps({"chunk":"لم أجد نقاطًا كافية؛ إليك روابط مفيدة.\n"}) + "\n\n"

        if results:
            yield "data: " + json.dumps({"chunk":"\nأهم الروابط:\n"}) + "\n\n"
            for r in results[:6]:
                yield "data: " + json.dumps({"chunk":f"- {r.get('title','')}: {r.get('link','')}\n"}) + "\n\n"
                await asyncio.sleep(0.008)

        closing = f"\n[{now_iso()}] لمتابعة نقطة محددة من هذا الموضوع، اكتب جملة تتضمن الكلمة المفتاحية (مثال: وضّح النقطة الأولى). لبدء موضوع جديد اكتب: محادثة جديدة."
        full = opening + "".join("• "+b+"\n" for b in bullets) + \
               ("\nأهم الروابط:\n" + "\n".join(f"- {r.get('title','')}: {r.get('link','')}" for r in results[:6]) if results else "") + closing
        add_msg(tid,"assistant",full)

        yield "data: " + json.dumps({"chunk":closing,"done":True}) + "\n\n"

        # نبضات للتثبيت الشبكي
        while not await request.is_disconnected():
            if time.time() - last_ping > 15:
                yield ": ping\n\n"; last_ping = time.time()
            await asyncio.sleep(5)

    return StreamingResponse(streamer(), media_type="text/event-stream")

@app.post("/api/ask")
async def ask_json(request: Request):
    data = await request.json()
    q = (data.get("q") or "").strip()
    tid = int(data.get("tid") or 0) or new_thread()
    nq = normalize_ar(q)
    add_msg(tid,"user",f"[{now_iso()}] {q}")

    quick = intro_or_privacy(nq)
    if quick:
        add_msg(tid,"assistant",f"[{now_iso()}] {quick}")
        return {"ok": True, "answer": quick}

    contextual_q = contextualize_query(tid, q)
    dd = await smart_search(contextual_q, 10)
    bullets, results = dd["bullets"], dd["results"]

    if not bullets and not results:
        ans = "حاولت أبحث لكن الظاهر الخدمة رجّعت نتائج قليلة الآن. أعد الصياغة أو اسألني نقطة أدق وسأحاول مرة أخرى."
    else:
        ans = "تمام! هذا ملخص سريع:\n" + "".join("• "+b+"\n" for b in bullets[:6])
        if results:
            ans += "\nأهم الروابط:\n" + "\n".join(f"- {r.get('title','')}: {r.get('link','')}" for r in results[:6])

    add_msg(tid,"assistant",ans)
    return {"ok": True, "answer": ans}

# ===================== PWA =====================
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
        "name":"بسام — محادثة بوعي متابعة",
        "short_name":"Bassam Chat",
        "start_url":"/",
        "display":"standalone",
        "background_color":"#0b0f19",
        "theme_color":"#7c3aed",
        "icons":[
            {"src":"/static/icons/icon-192.png","sizes":"192x192","type":"image/png"},
            {"src":"/static/icons/icon-512.png","sizes":"512x512","type":"image/png"}
        ]
    })

@app.get("/healthz")
def health(): return {"ok": True}
