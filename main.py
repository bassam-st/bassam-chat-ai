# main.py — تشات بسام (وعي + بحث مباشر + رد عربي طبيعي + صفحة واحدة)
import os, sqlite3, re, json, time, asyncio, urllib.parse
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
from duckduckgo_search import DDGS

# ───── إعداد المسارات
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data"); os.makedirs(DATA, exist_ok=True)
DB_PATH = os.path.join(DATA, "chat.db")
STATIC_DIR = os.path.join(BASE, "static"); os.makedirs(STATIC_DIR, exist_ok=True)
TEMPLATES_DIR = os.path.join(BASE, "templates"); os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(title="تشات بسام — وعي + بحث عربي")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ───── قاعدة البيانات
def db():
    con = sqlite3.connect(DB_PATH); con.row_factory = sqlite3.Row
    return con

def now_iso(): return datetime.utcnow().isoformat(timespec="seconds")+"Z"

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL
        );""")
init_db()

def add_msg(role:str, text:str):
    with db() as con:
        con.execute("INSERT INTO messages(ts,role,text) VALUES(?,?,?)",(now_iso(),role,text))

# ───── وعي المتابعة
AR_VARIANTS = str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه"})
def normalize_ar(s:str)->str: return (s or "").strip().lower().translate(AR_VARIANTS)
FOLLOWUP_HINTS = ["النقطة","وضح","توضيح","سابق","تابع","عن النقطة","بالنسبة","هذا","تلك"]
def is_followup(q:str)->bool: return any(h in normalize_ar(q) for h in FOLLOWUP_HINTS)

# ───── البحث عبر DuckDuckGo + ويكيبيديا
def ddg_search(q:str, k:int=8)->List[Dict]:
    out=[]
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(q, region="xa-ar", safesearch="moderate", max_results=k):
                out.append({
                    "title":r.get("title",""),
                    "link":r.get("href") or r.get("url") or "",
                    "snippet":r.get("body","")
                })
                if len(out)>=k: break
    except Exception:
        pass
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
            link = j.get("content_urls",{}).get("desktop",{}).get("page","")
            if desc: return {"title": j.get("title") or title, "link": link, "snippet": desc}
    except Exception:
        return None
    return None

def _clean(s:str)->str: return re.sub(r"[^\w\s\u0600-\u06FF]", " ", (s or "").strip())

def bullets_from_snips(snips:List[str], m:int=8)->List[str]:
    txt = " ".join(_clean(s) for s in snips if s).strip()
    parts = re.split(r"[.!؟\n]", txt); seen=set(); out=[]
    for p in parts:
        p = re.sub(r"\s+"," ", p).strip(" -•،,")
        if len(p.split())>=4 and p not in seen:
            seen.add(p); out.append(p)
        if len(out)>=m: break
    return out

async def smart_search(q:str, k:int=10)->Dict:
    res = ddg_search(q, k)
    wiki = await wiki_summary(q, "ar")
    if wiki: res.insert(0, wiki)
    bullets = bullets_from_snips([r.get("snippet") for r in res], 8)
    return {"results": res, "bullets": bullets}

# ───── ردود الهوية والخصوصية
def id_or_privacy_reply(q:str)->Optional[str]:
    nq = normalize_ar(q)
    if "من هو بسام" in nq or "المطور" in nq:
        return "بسام الشتيمي هو مطور هذا النظام الذكي."
    return None

# ───── واجهة HTML بسيطة (تشات مباشر)
INDEX = os.path.join(TEMPLATES_DIR,"index.html")
if not os.path.exists(INDEX):
    with open(INDEX,"w",encoding="utf-8") as f:
        f.write("""<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>تشات بسام</title>
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
const es=new EventSource(`/api/ask_sse?q=${encodeURIComponent(v)}`);let buf='';const h=document.createElement('div');
h.className='msg assistant';const ts=document.createElement('span');ts.className='ts';ts.textContent=new Date().toISOString();
h.appendChild(ts);const tn=document.createTextNode('...');h.appendChild(tn);document.getElementById('chat').appendChild(h);
es.onmessage=(e)=>{const d=JSON.parse(e.data);if(d.chunk){buf+=d.chunk;h.childNodes[1].nodeValue="\\n"+buf;}if(d.done){es.close();}};es.onerror=()=>es.close();return false;}
</script></body></html>""")

# ───── واجهة الرد الفوري SSE
@app.get("/api/ask_sse")
async def ask_sse(request: Request, q: str):
    q = (q or "").strip()
    add_msg("user", f"[{now_iso()}] {q}")

    async def stream():
        quick = id_or_privacy_reply(q)
        if quick:
            yield f"data: {json.dumps({'chunk':quick,'done':True})}\n\n"; return

        data = await smart_search(q, 10)
        results, bullets = data["results"], data["bullets"]

        opening = f"[{now_iso()}] هذا ملخص بالعربية:\n"
        yield f"data: {json.dumps({'chunk':opening})}\n\n"; await asyncio.sleep(0.02)

        if bullets:
            for b in bullets:
                if re.search(r"[A-Za-z]{6,}", b):
                    b = "معلومة بالإنجليزية: " + b
                yield f"data: {json.dumps({'chunk':'• '+b+'\\n'})}\n\n"; await asyncio.sleep(0.01)
        else:
            yield f"data: {json.dumps({'chunk':'لم أجد تفاصيل كافية؛ إليك روابط قد تفيد:'})}\n\n"

        if results:
            yield f"data: {json.dumps({'chunk':'\\nأهم الروابط:\\n'})}\n\n"
            for r in results[:6]:
                title = r.get('title', '')
                link = r.get('link', '')
                chunk = f"- {title}: {link}\\n"
                yield f"data: {json.dumps({'chunk':chunk})}\n\n"
                await asyncio.sleep(0.01)

        closing = f"\\n[{now_iso()}] يمكنك متابعة نقطة محددة بقولك (عن النقطة ...)."
        yield f"data: {json.dumps({'chunk':closing,'done':True})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

# ───── فحص الصحة
@app.get("/healthz")
def health(): return {"ok": True}
