# main.py — تشات بسام: صفحة واحدة + وعي متابعة + رد فوري (SSE) + بحث ويب موثوق + إخراج عربي دائم + PWA
import os, sqlite3, re, json, time, asyncio, urllib.parse
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import httpx
from duckduckgo_search import DDGS

# ───────── المسارات الأساسية
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data"); os.makedirs(DATA, exist_ok=True)
DB_PATH = os.path.join(DATA, "chat.db")

STATIC_DIR = os.path.join(BASE, "static"); os.makedirs(STATIC_DIR, exist_ok=True)
TEMPLATES_DIR = os.path.join(BASE, "templates"); os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(title="تشات بسام — محادثة ووعي متابعة")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ───────── قاعدة البيانات (خيوط + رسائل)
def db():
    con = sqlite3.connect(DB_PATH); con.row_factory = sqlite3.Row
    return con

def now_iso(): return datetime.utcnow().isoformat(timespec="seconds")+"Z"

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

# ───────── أدوات سياقية (وعي متابعة بالعربية)
AR_VARIANTS = str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه"})
def normalize_ar(s:str)->str: return (s or "").strip().lower().translate(AR_VARIANTS)

FOLLOWUP_HINTS = ["النقطه","النقطة","وضح","توضيح","المقصود","هذا","تلك","سابق","الاول","الأول","تابع","بالنسبه","بالنسبة","عن النقطة","عن النقطه"]
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
    msgs = get_messages(tid); return [f"{m['role']}:{m['text']}" for m in msgs[-n:]]

def condense_context(tid:int, n:int=8)->str:
    lines = last_texts(tid, n)
    if not lines: return ""
    keys = extract_keywords(lines, top=14)
    lastQ = next((m['text'] for m in get_messages(tid)[::-1] if m['role']=='user'), "")
    return f"سياق قصير: ({'؛ '.join(keys[:10])}). آخر سؤال: {lastQ[:160]}"

def contextualize_query(tid:int, q:str)->str:
    return f"{q} — [متابعة: {condense_context(tid)}]" if is_followup(q) else q

# ───────── بحث ويب (DuckDuckGo + Wikipedia)
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
    for reg in ["xa-ar", "wt-wt", "us-en"]:
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(q, region=reg, safesearch="moderate", max_results=k):
                    out.append({"title":r.get("title",""),"link":r.get("href") or r.get("url") or "","snippet":r.get("body","")})
                    if len(out)>=k: break
        except Exception:
            pass
        if out: break
    return out

async def wiki_summary(title:str, lang:str="ar")->Optional[Dict]:
    safe = urllib.parse.quote(title.replace(" ","_"))
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{safe}"
    try:
        async with httpx.AsyncClient(timeout=10) as cl:
            r = await cl.get(url)
            if r.status_code != 200: return None
            j = r.json()
            desc = (j.get("extract") or "").strip()
            link = (j.get("content_urls",{}).get("desktop",{}).get("page") or f"https://{lang}.wikipedia.org/wiki/{safe}")
            if desc:
                return {"title": j.get("title") or title, "link": link, "snippet": desc}
    except Exception:
        return None
    return None

async def smart_search(q:str, k:int=10)->Dict:
    resA = ddg_search_text(q, k)
    ar_sum = await wiki_summary(q, "ar")
    if ar_sum: resA = merge_results([ar_sum], resA, k)
    bullets = bullets_from_snips([r.get("snippet") for r in resA], 8)
    return {"results": resA, "bullets": bullets}

# ───────── ردود الهوية/الخصوصية
def id_or_privacy_reply(nq:str)->Optional[str]:
    if "من هو بسام" in nq or "المطور" in nq:
        return "بسام الشتيمي هو مطور هذا النظام الذكي."
    return None

# ───────── واجهة HTML تلقائية
INDEX = os.path.join(TEMPLATES_DIR, "index.html")
if not os.path.exists(INDEX):
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write("""<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>تشات بسام</title>
<link rel="manifest" href="/static/pwa/manifest.json"/><meta name="theme-color" content="#7c3aed"/>
<style>
body{background:#0b0f19;color:#e5e7eb;font-family:system-ui,Segoe UI,Roboto,"Noto Naskh Arabic UI";}
.card{background:#121826;border-radius:14px;padding:12px;border:1px solid #1f2937;margin:12px auto;max-width:900px;}
.msg{white-space:pre-wrap;line-height:1.7;margin:8px 0;padding:10px;border-radius:10px}
.user{background:#0f1421}.assistant{background:#0f1220;border:1px solid #2a2f45}
.ts{opacity:.75;font-size:12px;display:block;margin-bottom:4px}
input{width:80%;padding:10px;border:none;border-radius:10px;background:#0f1421;color:#fff}
button{padding:10px 16px;background:#7c3aed;color:#fff;border:none;border-radius:10px;font-weight:700}
</style></head><body>
<div class="card" id="chat"></div>
<form class="card" onsubmit="return sendMsg()">
<input id="q" placeholder="اكتب سؤالك..." required/>
<button>إرسال</button></form>
<script>
function addMsg(txt,who){const c=document.getElementById('chat');const d=document.createElement('div');d.className='msg '+who;
const t=document.createElement('span');t.className='ts';t.textContent=new Date().toISOString();d.appendChild(t);
d.appendChild(document.createTextNode("\\n"+txt));c.appendChild(d);c.scrollTop=c.scrollHeight;}
addMsg("👋 مرحبًا! أنا تشات بسام — اسألني أي شيء.","assistant");
async function sendMsg(){const i=document.getElementById('q');const v=i.value.trim();if(!v)return false;addMsg(v,"user");i.value='';
const es=new EventSource(`/api/ask_sse?q=${encodeURIComponent(v)}&tid=0`);let buf='';const h=document.createElement('div');
h.className='msg assistant';const ts=document.createElement('span');ts.className='ts';ts.textContent=new Date().toISOString();
h.appendChild(ts);const tn=document.createTextNode('...');h.appendChild(tn);document.getElementById('chat').appendChild(h);
es.onmessage=(e)=>{const d=JSON.parse(e.data);if(d.chunk){buf+=d.chunk;h.childNodes[1].nodeValue="\\n"+buf;}if(d.done){es.close();}};es.onerror=()=>es.close();return false;}
</script></body></html>""")

# ───────── الرد الفوري SSE
@app.get("/api/ask_sse")
async def ask_sse(request: Request, q: str, tid: int=0):
    if tid == 0:
        threads = list_threads()
        tid = threads[0]["id"] if threads else new_thread()
    q = (q or "").strip()
    nq = normalize_ar(q)
    add_msg(tid,"user",f"[{now_iso()}] {q}")

    async def streamer():
        quick = id_or_privacy_reply(nq)
        if quick:
            yield f"data: {json.dumps({'chunk':quick,'done':True})}\n\n"; return

        contextual_q = contextualize_query(tid, q)
        data = await smart_search(contextual_q, 10)
        results, bullets = data["results"], data["bullets"]

        opening = f"[{now_iso()}] هذا ملخص بالعربية:\n"
        yield f"data: {json.dumps({'chunk':opening})}\n\n"; await asyncio.sleep(0.02)

        if bullets:
            for b in bullets:
                if re.search(r"[A-Za-z]{6,}", b):
                    b = "معلومة بالإنجليزية: " + b
                yield f"data: {json.dumps({'chunk':'• '+b+'\\n'})}\n\n"; await asyncio.sleep(0.01)
        else:
            yield f"data: {json.dumps({'chunk':'لم أجد تفاصيل كافية، هذه روابط قد تفيد:'})}\n\n"

        if results:
            yield f"data: {json.dumps({'chunk':'\\nأهم الروابط:\\n'})}\n\n"
            for r in results[:6]:
                yield f"data: {json.dumps({'chunk':f'- {r.get(\"title\",\"")}: {r.get(\"link\",\"\")}\\n'})}\n\n"; await asyncio.sleep(0.01)

        closing = f"\\n[{now_iso()}] يمكنك متابعة نقطة محددة بقولك (عن النقطة ...)."
        yield f"data: {json.dumps({'chunk':closing,'done':True})}\n\n"

    return StreamingResponse(streamer(), media_type="text/event-stream")

# ───────── PWA
@app.get("/sw.js")
def sw_js():
    return HTMLResponse("self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>self.clients.claim());self.addEventListener('fetch',()=>{});",
                        media_type="application/javascript")

@app.get("/static/pwa/manifest.json")
def manifest():
    return JSONResponse({
        "name":"تشات بسام",
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
