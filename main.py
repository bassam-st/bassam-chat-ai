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

# ───────── مسارات أساسية
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

# ───────── بحث ويب موثوق (DDG + Instant Answer + ويكيبيديا عربي→إنجليزي)
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
    regions_try = ["xa-ar", "wt-wt", "us-en"]
    for reg in regions_try:
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(q, region=reg, safesearch="moderate", max_results=k, backend="duckduckgo"):
                    out.append({"title":r.get("title",""),"link":r.get("href") or r.get("url") or "","snippet":r.get("body","")})
                    if len(out)>=k: break
        except Exception:
            pass
        if out: break
    return out

async def ddg_instant_answer(q:str, k:int=6)->List[Dict]:
    url=f"https://api.duckduckgo.com/?q={urllib.parse.quote(q)}&format=json&no_html=1&skip_disambig=1"
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            r = await cl.get(url); data = r.json()
    except Exception:
        return []
    out=[]
    abs_txt = (data.get("AbstractText") or "").strip()
    if abs_txt:
        out.append({"title": data.get("Heading") or "ملخص",
                    "link": data.get("AbstractURL") or "",
                    "snippet": abs_txt})
    for t in (data.get("RelatedTopics") or []):
        if isinstance(t, dict):
            txt = (t.get("Text") or "").strip(); href = (t.get("FirstURL") or "").strip()
            if txt:
                out.append({"title": txt[:60], "link": href, "snippet": txt})
                if len(out)>=k: break
    return out

async def wiki_summary(title:str, lang:str="ar")->Optional[Dict]:
    # يلخص من ويكيبيديا (عربي ثم إنجليزي)
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

def rough_en(q: str) -> str:
    rep = {
        "اين": "where", "أين": "where", "تقع": "is", "اليمن": "Yemen",
        "ماهو": "what is", "ما هو": "what is", "من هو": "who is", "اخبار": "news"
    }
    s = q
    for ar,en in rep.items(): s = s.replace(ar, en)
    return s

async def smart_search(q:str, k:int=10)->Dict:
    # 1) DDG نصي
    resA = ddg_search_text(q, k)
    # 2) DDG Instant Answer
    resB = await ddg_instant_answer(q, k)
    merged = merge_results(resA, resB, k)

    # 3) ويكيبيديا عربي لمحاولة استخراج وصف عربي واضح
    if merged:
        top_title = merged[0].get("title","").split(" — ")[0].split(" - ")[0][:60]
        if top_title:
            ar_sum = await wiki_summary(top_title, "ar")
            if ar_sum: merged = merge_results([ar_sum], merged, k)

    # 4) لو النتائج قليلة جدًا جرّب الإنجليزية
    if len(merged) < max(2, k//3):
        q_en = rough_en(q)
        resA_en = ddg_search_text(q_en, k)
        resB_en = await ddg_instant_answer(q_en, k)
        merged = merge_results(merged, merge_results(resA_en, resB_en, k), k)

        # ويكيبيديا إنجليزي احتياط
        if merged:
            top_title = merged[0].get("title","").split(" — ")[0].split(" - ")[0][:60]
            en_sum = await wiki_summary(top_title, "en")
            if en_sum: merged = merge_results([en_sum], merged, k)

    bullets = bullets_from_snips([r.get("snippet") for r in merged], 8)
    return {"results": merged, "bullets": bullets}

# ───────── ردود خاصة بالهوية/الخصوصية
def id_or_privacy_reply(nq:str)->Optional[str]:
    if ("من هو بسام" in nq) or ("من هو بسام الذكي" in nq) or ("من هو بسام الشتيمي" in nq) \
       or ("من صنع التطبيق" in nq) or ("من المطور" in nq) or ("من هو صاحب التطبيق" in nq):
        return "بسام الشتيمي هو منصوريّ الأصل، وهو صانع هذا التطبيق."
    if ("اسم ام بسام" in nq) or ("اسم ام بسام الشتيمي" in nq) or ("اسم زوجة بسام" in nq) or ("مرت بسام" in nq):
        return "حرصًا على الخصوصية، لا يقدّم بسام معلومات شخصية مثل أسماء أفراد العائلة. رجاءً تجنّب مشاركة بيانات حساسة."
    return None

# ───────── صفحة HTML افتراضية تُولّد تلقائيًا
INDEX = os.path.join(TEMPLATES_DIR, "index.html")
if not os.path.exists(INDEX):
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write("""<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>تشات بسام — محادثة ووعي متابعة</title>
<link rel="manifest" href="/static/pwa/manifest.json"/><meta name="theme-color" content="#7c3aed"/>
<style>
:root{--bg:#0b0f19;--card:#121826;--muted:#98a2b3;--pri:#7c3aed}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#e5e7eb;font-family:system-ui,Segoe UI,Roboto,"Noto Naskh Arabic UI","Noto Kufi Arabic",Tahoma,Arial,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:14px}
.card{background:#121826;border-radius:14px;padding:12px;border:1px solid #1f2937;box-shadow:0 10px 30px rgba(0,0,0,.25);margin:12px 0}
h1{font-size:18px;margin:8px 0}
.msg{white-space:pre-wrap;line-height:1.7;margin:8px 0;padding:10px;border-radius:10px}
.user{background:#0f1421}.assistant{background:#0f1220;border:1px solid #2a2f45}
.ts{opacity:.75;font-size:12px;display:block;margin-bottom:4px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
input[type=text]{flex:1;min-width:220px;padding:12px 14px;border:none;border-radius:12px;background:#0f1421;color:#fff}
button{padding:12px 16px;border:none;border-radius:12px;background:var(--pri);color:#fff;font-weight:700;cursor:pointer}
button:hover{opacity:.92}
.install{position:fixed;right:12px;bottom:12px;background:#7c3aed;color:#fff;border:none;border-radius:12px;padding:10px 14px;font-weight:700}
.footer{color:var(--muted);text-align:center;margin-top:18px}
</style></head><body>
<div class="wrap">
  <h1>تشات بسام — محادثة ووعي متابعة</h1>
  <div id="chat" class="card"></div>
  <form class="card row" onsubmit="return sendMsg()">
    <input id="q" type="text" placeholder="اكتب سؤالك..." required />
    <button type="submit">أرسل</button>
  </form>
  <div class="footer">© Bassam 2025 — يرد دائمًا بالعربية ويعرض أهم الروابط.</div>
</div>
<script>
// زر تثبيت PWA يظهر تلقائيًا من الحدث
let deferredPrompt=null;window.addEventListener("beforeinstallprompt",(e)=>{e.preventDefault();deferredPrompt=e;
  const b=document.createElement("button");b.className="install";b.textContent="📱 تثبيت تشات بسام";
  b.onclick=async()=>{b.style.display="none";deferredPrompt.prompt();await deferredPrompt.userChoice;deferredPrompt=null;};
  document.body.appendChild(b);
});
// Service Worker
if("serviceWorker" in navigator){navigator.serviceWorker.register("/sw.js").catch(()=>{});}

function addMsg(txt, who){
  const chat=document.getElementById('chat');
  const d=document.createElement('div'); d.className='msg '+(who||'assistant');
  const ts=document.createElement('span'); ts.className='ts'; ts.textContent=new Date().toISOString();
  d.appendChild(ts); d.appendChild(document.createTextNode("\\n"+txt)); chat.appendChild(d); chat.scrollTop=chat.scrollHeight;
}

addMsg("مرحبًا! أنا تشات بسام — اسألني أي شيء وسأجيبك بالعربية مع أهم الروابط 👌","assistant");

async function sendMsg(){
  const inp=document.getElementById('q'); const text=inp.value.trim(); if(!text)return false;
  addMsg(text,"user"); inp.value='';
  try{
    const es=new EventSource(`/api/ask_sse?q=${encodeURIComponent(text)}&tid=0`);
    let buf=''; const holder=document.createElement('div'); holder.className='msg assistant';
    const ts=document.createElement('span'); ts.className='ts'; ts.textContent=new Date().toISOString();
    holder.appendChild(ts); const tn=document.createTextNode('...'); holder.appendChild(tn);
    const chat=document.getElementById('chat'); chat.appendChild(holder);

    es.onmessage=(e)=>{const d=JSON.parse(e.data); if(d.chunk){buf+=d.chunk; holder.childNodes[1].nodeValue="\\n"+buf; chat.scrollTop=chat.scrollHeight;} if(d.done){es.close();}};
    es.onerror=()=>{es.close(); fallback(text);};
  }catch(_){ fallback(text); }
  return false;
}

async function fallback(text){
  try{
    const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:text, tid:0})});
    const j=await r.json(); addMsg(j.answer || 'لم أستطع الحصول على نتيجة الآن.', 'assistant');
  }catch(_){ addMsg('تعذر الاتصال بالخادم الآن.', 'assistant'); }
}
</script>
</body></html>""")

# ───────── صفحات أساسية
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    # خيط واحد افتراضي في الواجهة المبسطة
    threads = list_threads()
    tid = threads[0]["id"] if threads else new_thread()
    msgs = get_messages(tid)
    return templates.TemplateResponse("index.html", {"request":request})

# ───────── API: SSE مع Heartbeat وإخراج عربي
@app.get("/api/ask_sse")
async def ask_sse(request: Request, q: str, tid: int=0):
    # اجعل tid=0 دائمًا خيطًا واحدًا بسيطًا
    if tid == 0:
        threads = list_threads()
        tid = threads[0]["id"] if threads else new_thread()

    q = (q or "").strip()
    if not q:
        async def gen_err():
            yield "data: " + json.dumps({"chunk":"⚠️ الرجاء كتابة سؤالك أولًا."}) + "\n\n"
        return StreamingResponse(gen_err(), media_type="text/event-stream")

    nq = normalize_ar(q)
    add_msg(tid,"user",f"[{now_iso()}] {q}")

    async def streamer():
        last_ping = time.time()

        # ردود خاصة
        quick = id_or_privacy_reply(nq)
        if quick:
            ans = quick
            add_msg(tid,"assistant",f"[{now_iso()}] {ans}")
            yield "data: " + json.dumps({"chunk":ans,"done":True}) + "\n\n"
            return

        contextual_q = contextualize_query(tid, q)
        data = await smart_search(contextual_q, 10)
        results, bullets = data["results"], data["bullets"]

        # إخراج عربي حتى لو النصوص إنجليزية
        opening = f"[{now_iso()}] هذا ملخص واضح بالعربية لما وجدته:\n"
        yield "data: " + json.dumps({"chunk":opening}) + "\n\n"; await asyncio.sleep(0.02)

        if bullets:
            for b in bullets:
                # إن وُجدت جملة إنجليزية خالصة، نوّضح للمستخدم
                if re.search(r"[A-Za-z]{6,}", b):
                    b = "معلومة بالإنجليزية: " + b
                yield "data: " + json.dumps({"chunk":"• "+b+"\n"}) + "\n\n"; await asyncio.sleep(0.01)
        else:
            yield "data: " + json.dumps({"chunk":"لم أعثر على نقاط كافية، ولكن هذه روابط موثوقة:\n"}) + "\n\n"

        if results:
            yield "data: " + json.dumps({"chunk":"\nأهم الروابط:\n"}) + "\n\n"
            for r in results[:6]:
                title = r.get('title',''); link = r.get('link','')
                yield "data: " + json.dumps({"chunk":f"- {title}: {link}\n"}) + "\n\n"; await asyncio.sleep(0.01)

        closing = f"\n[{now_iso()}] لو أردت متابعة نقطة محددة، اكتب: (عن النقطة …) أو اقتبس سطرًا من الملخص."
        full = opening + "".join("• "+b+"\n" for b in bullets) + \
               ("\nأهم الروابط:\n" + "\n".join(f"- {r.get('title','')}: {r.get('link','')}" for r in results[:6]) if results else "") + closing
        add_msg(tid,"assistant",full)

        yield "data: " + json.dumps({"chunk":closing,"done":True}) + "\n\n"

        # Heartbeat احتياطي إن ظل الاتصال مفتوحًا
        while not await request.is_disconnected():
            if time.time() - last_ping > 15:
                yield ": ping\n\n"; last_ping = time.time()
            await asyncio.sleep(5)

    return StreamingResponse(streamer(), media_type="text/event-stream")

# ───────── Fallback غير متدفق
@app.post("/api/ask")
async def ask_json(request: Request):
    data = await request.json()
    q = (data.get("q") or "").strip()
    tid = int(data.get("tid") or 0)
    if tid == 0:
        threads = list_threads()
        tid = threads[0]["id"] if threads else new_thread()

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
        ans = "حاولتُ البحث الآن لكن يبدو أنّ النتائج قليلة. جرّب إعادة الصياغة أو حدد النقطة أكثر وسأحاول ثانية."
    else:
        ans = "هذا ملخص عربي موجز:\n" + "".join("• "+(("معلومة بالإنجليزية: "+b) if re.search(r\"[A-Za-z]{6,}\", b) else b) + "\n" for b in bullets[:6])
        if results:
            ans += "\nأهم الروابط:\n" + "\n".join(f"- {r.get('title','')}: {r.get('link','')}" for r in results[:6])

    add_msg(tid,"assistant",ans)
    return {"ok": True, "answer": ans}

# ───────── PWA
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
        "name":"تشات بسام — محادثة ووعي متابعة",
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
