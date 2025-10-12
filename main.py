# main.py — خيوط محادثة + رد فوري (SSE) + بحث مزدوج موثوق + Heartbeat + Fallback + PWA
import os, sqlite3, re, json, time, asyncio
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import httpx
from duckduckgo_search import DDGS

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data"); os.makedirs(DATA, exist_ok=True)
DB_PATH = os.path.join(DATA, "chat.db")

STATIC_DIR = os.path.join(BASE, "static"); os.makedirs(STATIC_DIR, exist_ok=True)
TEMPLATES_DIR = os.path.join(BASE, "templates"); os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(title="Bassam Chat — Context Threads")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ===================== DB =====================
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

# ===================== نصيات سياقية =====================
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

# ===================== بحث ويب موثوق =====================
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

def ddg_search_text(q:str, k:int=8)->List[Dict]:
    out=[]
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(q, region="xa-ar", safesearch="moderate", max_results=k):
                out.append({"title":r.get("title",""),"link":r.get("href") or r.get("url") or "","snippet":r.get("body","")})
                if len(out)>=k: break
    except Exception:
        pass
    return out

async def ddg_instant_answer(q:str, k:int=6)->List[Dict]:
    """API بسيطة بدون مفتاح — تأتي بجواب فوري + روابط ذات صلة عند توفرها"""
    url=f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            r = await cl.get(url)
            data = r.json()
    except Exception:
        return []

    out=[]
    # Abstract / heading
    abs_txt = (data.get("AbstractText") or "").strip()
    if abs_txt:
        out.append({"title": data.get("Heading") or "ملخص",
                    "link": data.get("AbstractURL") or "",
                    "snippet": abs_txt})
    # RelatedTopics
    for t in (data.get("RelatedTopics") or []):
        if isinstance(t, dict):
            txt = (t.get("Text") or "").strip()
            href = (t.get("FirstURL") or "").strip()
            if txt:
                out.append({"title": txt[:60], "link": href, "snippet": txt})
                if len(out)>=k: break
    return out

async def smart_search(q:str, k:int=10)->Dict:
    # نجمع نتائج DDGS + Instant Answer
    resA = ddg_search_text(q, k)
    resB = await ddg_instant_answer(q, k)
    merged = merge_results(resA, resB, k)
    bullets = bullets_from_snips([r.get("snippet") for r in merged], 8)
    return {"results": merged, "bullets": bullets}

# ===================== ردود خاصة بالهوية/الخصوصية =====================
def id_or_privacy_reply(nq:str)->Optional[str]:
    if ("من هو بسام" in nq) or ("من هو بسام الذكي" in nq) or ("من هو بسام الشتيمي" in nq) \
       or ("من صنع التطبيق" in nq) or ("من المطور" in nq) or ("من هو صاحب التطبيق" in nq):
        return "بسام الشتيمي هو منصوريّ الأصل، وهو صانع هذا التطبيق."
    if ("اسم ام بسام" in nq) or ("اسم ام بسام الشتيمي" in nq) or ("اسم زوجة بسام" in nq) or ("مرت بسام" in nq):
        return "حرصًا على الخصوصية، لا يقدّم بسام معلومات شخصية مثل أسماء أفراد العائلة. رجاءً تجنّب مشاركة بيانات حساسة."
    return None

# ===================== لو القالب ناقص نولده =====================
INDEX = os.path.join(TEMPLATES_DIR, "index.html")
if not os.path.exists(INDEX):
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write("""<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>بسام — محادثات بخيوط + وعي متابعة</title>
<link rel="manifest" href="/static/pwa/manifest.json"/><meta name="theme-color" content="#7c3aed"/>
<style>
:root{--bg:#0b0f19;--card:#121826;--muted:#98a2b3;--pri:#7c3aed}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#e5e7eb;font-family:system-ui,Segoe UI,Roboto,"Noto Naskh Arabic UI","Noto Kufi Arabic",Tahoma,Arial,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:14px}.header{display:flex;gap:10px;align-items:center;justify-content:space-between}
h1{margin:8px 0;font-size:18px}.layout{display:grid;grid-template-columns:260px 1fr;gap:12px}
@media (max-width:900px){.layout{grid-template-columns:1fr}}
.card{background:var(--card);border-radius:14px;padding:12px;border:1px solid #1f2937}
.btn{background:var(--pri);border:none;color:#fff;border-radius:12px;padding:10px 12px;font-weight:700;cursor:pointer}
input[type=text]{width:100%;padding:10px;border-radius:10px;border:1px solid #1f2937;background:#0f1421;color:#fff}
ul{list-style:none;margin:0;padding:0}.thread{padding:8px;border-radius:10px;cursor:pointer;border:1px solid #1f2937;margin-bottom:8px;display:block;color:#e5e7eb;text-decoration:none}
.thread.active{border-color:#7c3aed;background:#151b2b}
.msg{white-space:pre-wrap;line-height:1.7;margin:8px 0;padding:10px;border-radius:10px}.user{background:#0f1421}
.assistant{background:#0f1220;border:1px solid #2a2f45}.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.footer{color:var(--muted);text-align:center;margin-top:18px}.install{position:fixed;right:12px;bottom:12px;background:#7c3aed;border:none;color:#fff;border-radius:12px;padding:10px 14px;font-weight:700}
.ts{opacity:.75;font-size:12px;display:block;margin-bottom:4px}
</style></head><body>
<div class="wrap">
  <div class="header">
    <h1>بسام — محادثات بخيوط + وعي متابعة</h1>
    <form action="/thread/new" method="post"><button class="btn" type="submit">➕ محادثة جديدة</button></form>
  </div>
  <div class="layout">
    <div class="card"><h3>المحادثات</h3><ul>
      {% for th in threads %}
      <li><a class="thread {% if th.id==cur %}active{% endif %}" href="/?t={{ th.id }}">#{{ th.id }} — {{ th.title or "بدون عنوان" }}
      <div class="ts">{{ th.created_at }}</div></a></li>{% endfor %}
    </ul><hr style="border-color:#1f2937;margin:10px 0">
      <form action="/thread/rename" method="post" class="row">
        <input type="hidden" name="tid" value="{{ cur }}"/><input type="text" name="title" placeholder="اسم الخيط…">
        <button class="btn" type="submit">حفظ الاسم</button>
      </form>
    </div>
    <div class="card"><div id="chat">
      {% for m in msgs %}<div class="msg {{ m.role }}"><span class="ts">{{ m.ts }}</span>{{ m.text }}</div>{% endfor %}
    </div>
      <form class="row" onsubmit="return sendMsg()"><input id="q" type="text" placeholder="اكتب سؤالك هنا…" required>
      <button class="btn" type="submit">اسأل</button></form></div>
  </div><div class="footer">© Bassam 2025 — وعي متابعة + بحث مجاني.</div></div>
<script>
let deferredPrompt=null;window.addEventListener("beforeinstallprompt",(e)=>{e.preventDefault();deferredPrompt=e;
  const b=document.createElement("button");b.className="install";b.textContent="📱 تثبيت";b.onclick=async()=>{b.style.display="none";deferredPrompt.prompt();await deferredPrompt.userChoice;deferredPrompt=null;};document.body.appendChild(b);});
if("serviceWorker" in navigator){navigator.serviceWorker.register("/sw.js").catch(()=>{});}
const tid={{ cur|int }};const chat=document.getElementById('chat');const q=document.getElementById('q');
function addMsg(txt,who){const d=document.createElement('div');d.className='msg '+who;const ts=document.createElement('span');ts.className='ts';ts.textContent=new Date().toISOString();d.appendChild(ts);d.appendChild(document.createTextNode("\\n"+txt));chat.appendChild(d);chat.scrollTop=chat.scrollHeight;}

async function sendMsg(){
  const text=q.value.trim(); if(!text) return false;
  addMsg(text,'user'); q.value='';
  // جرّب SSE أولاً
  try{
    const url=`/api/ask_sse?q=${encodeURIComponent(text)}&tid=${tid}`;
    const es=new EventSource(url); let buf=''; const holder=document.createElement('div');
    holder.className='msg assistant'; const ts=document.createElement('span'); ts.className='ts';
    ts.textContent=new Date().toISOString(); holder.appendChild(ts);
    const tn=document.createTextNode('...'); holder.appendChild(tn); chat.appendChild(holder);
    es.onmessage=(e)=>{const d=JSON.parse(e.data); if(d.chunk){buf+=d.chunk; holder.childNodes[1].nodeValue="\\n"+buf; chat.scrollTop=chat.scrollHeight;} if(d.done){es.close();}};
    es.onerror=()=>{es.close(); fallback(text);};
  }catch(_){ fallback(text); }
  return false;
}

async function fallback(text){
  try{
    const r = await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:text, tid:tid})});
    const j = await r.json();
    addMsg(j.answer || 'لم أستطع الحصول على نتيجة الآن.', 'assistant');
  }catch(_){
    addMsg('تعذر الاتصال بالخادم الآن.', 'assistant');
  }
}
</script></body></html>""")

# ===================== صفحات =====================
@app.get("/", response_class=HTMLResponse)
def home(request: Request, t: Optional[int]=None):
    threads = list_threads()
    if t is None: t = threads[0]["id"] if threads else new_thread()
    msgs = get_messages(t)
    return templates.TemplateResponse("index.html", {"request":request,"threads":threads,"cur":t,"msgs":msgs})

@app.post("/thread/new")
def create_thread(title: str = Form("محادثة جديدة")):
    tid = new_thread(title.strip() or "محادثة جديدة")
    return RedirectResponse(url=f"/?t={tid}", status_code=303)

@app.post("/thread/rename")
def rename_thread(tid: int = Form(...), title: str = Form(...)):
    with db() as con: con.execute("UPDATE threads SET title=? WHERE id=?", (title.strip() or "محادثة", tid))
    return RedirectResponse(url=f"/?t={tid}", status_code=303)

# ===================== API — SSE مع heartbeat =====================
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
        # Heartbeat كل 15 ثانية لمنع قطع الاتصال
        last_ping = time.time()

        # ردود خاصة
        quick = id_or_privacy_reply(nq)
        if quick:
            add_msg(tid,"assistant",f"[{now_iso()}] {quick}")
            yield "data: " + json.dumps({"chunk":quick,"done":True}) + "\n\n"
            return

        contextual_q = contextualize_query(tid, q)
        data = await smart_search(contextual_q, 10)
        results, bullets = data["results"], data["bullets"]

        opening = f"[{now_iso()}] تمام! هذا ملخص حسب سياق محادثتنا:\n"
        yield "data: " + json.dumps({"chunk":opening}) + "\n\n"
        await asyncio.sleep(0.03)

        if bullets:
            for b in bullets:
                yield "data: " + json.dumps({"chunk":"• "+b+"\n"}) + "\n\n"
                await asyncio.sleep(0.015)
        else:
            yield "data: " + json.dumps({"chunk":"لم أجد نقاطًا كافية؛ إليك روابط مفيدة.\n"}) + "\n\n"

        if results:
            yield "data: " + json.dumps({"chunk":"\nأهم الروابط:\n"}) + "\n\n"
            for r in results[:6]:
                yield "data: " + json.dumps({"chunk":f"- {r.get('title','')}: {r.get('link','')}\n"}) + "\n\n"
                await asyncio.sleep(0.01)

        closing = f"\n[{now_iso()}] لمتابعة نقطة محددة، اكتب: (عن النقطة …) أو اقتبس سطرًا. وللبدء من جديد: (➕ محادثة جديدة)."
        full = opening + "".join("• "+b+"\n" for b in bullets) + \
               ("\nأهم الروابط:\n" + "\n".join(f"- {r.get('title','')}: {r.get('link','')}" for r in results[:6]) if results else "") + closing
        add_msg(tid,"assistant",full)

        yield "data: " + json.dumps({"chunk":closing,"done":True}) + "\n\n"

        # نبضات إن بقي الاتصال مفتوح (احتياط)
        while not await request.is_disconnected():
            if time.time() - last_ping > 15:
                yield ": ping\n\n"   # تعليق SSE لا يظهر للمستخدم
                last_ping = time.time()
            await asyncio.sleep(5)

    return StreamingResponse(streamer(), media_type="text/event-stream")

# ===== Fallback غير متدفق (للأجهزة التي لا تدعم SSE) =====
@app.post("/api/ask")
async def ask_json(request: Request):
    data = await request.json()
    q = (data.get("q") or "").strip()
    tid = int(data.get("tid") or 0) or new_thread()
    nq = normalize_ar(q)
    add_msg(tid,"user",f"[{now_iso()}] {q}")

    quick = id_or_privacy_reply(nq)
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
        "name":"بسام — خيوط + وعي متابعة",
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
