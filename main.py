# main.py — نواة بسّام المتكاملة (RAG + بثّ حي + تعلّم ذاتي + تعلّم من الويب)
# Author: Bassam

import os, json, math, sqlite3, uuid, re, itertools, textwrap
from typing import List
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from urllib.parse import quote_plus  # ← إصلاح الاقتباس للبحث
import google.generativeai as genai

# ============================ الإعداد والمفاتيح ============================

RAW_KEYS = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY", "")
KEYS = [k.strip() for k in RAW_KEYS.split(",") if k.strip()]
if not KEYS:
    raise RuntimeError("ضع مفتاحًا في GEMINI_API_KEYS أو GEMINI_API_KEY")

_keys_cycle = itertools.cycle(KEYS)
_current_key = None

def _use_next_key():
    """بدّل مفتاح Gemini الحالي."""
    global _current_key
    _current_key = next(_keys_cycle)
    genai.configure(api_key=_current_key)

_use_next_key()

# استخدم أسماء نماذج حديثة ومتوافقة
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-1.5-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")
DB_PATH     = os.getenv("DB_PATH", "/tmp/bassam_brain.sqlite3")

# ============================ التطبيق و CORS ============================

app = FastAPI(title="Bassam Chat AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ============================ قاعدة المعرفة (SQLite + Embeddings) ============================

def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    con = _conn(); cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS docs(
        id TEXT PRIMARY KEY,
        title TEXT,
        content TEXT,
        embedding TEXT
    );""")
    con.commit(); con.close()

def _is_rate_limit(msg:str)->bool:
    m = msg.lower()
    return ("429" in m) or ("rate" in m and "limit" in m) or ("quota" in m)

def _with_key_rotation(fn, max_tries=None):
    """شغّل fn() وإذا ظهرت 429 يبدّل المفتاح ويحاول مجددًا."""
    tries = 0
    max_tries = max_tries or len(KEYS)
    last = None
    while tries < max_tries:
        try:
            return fn()
        except Exception as e:
            last = e
            if _is_rate_limit(str(e)):
                _use_next_key()
                tries += 1
                continue
            raise
    raise last

def embed_text(text: str) -> List[float]:
    text = (text or "").strip()
    if not text: return []
    def _do():
        return genai.embed_content(model=EMBED_MODEL, content=text)
    emb = _with_key_rotation(_do)
    # إرجاع الشكل المناسب حسب نسخة المكتبة
    return emb.get("embedding") or emb.get("data",[{}])[0].get("embedding", [])

def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a)!=len(b): return 0.0
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a)) or 1e-9
    nb = math.sqrt(sum(y*y for y in b)) or 1e-9
    return dot/(na*nb)

def add_doc(title: str, content: str):
    emb = embed_text(content)
    con = _conn(); cur = con.cursor()
    cur.execute("INSERT INTO docs VALUES(?,?,?,?)",
                (str(uuid.uuid4()), title, content, json.dumps(emb)))
    con.commit(); con.close()

def search_docs(query: str, k=5):
    qemb = embed_text(query)
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT title,content,embedding FROM docs")
    rows = cur.fetchall(); con.close()
    ranked=[]
    for t,c,e in rows:
        try: emb = json.loads(e)
        except: emb = []
        ranked.append((t,c,cosine(qemb,emb)))
    ranked.sort(key=lambda x:x[2], reverse=True)
    return ranked[:k]

# ============================ واجهة الويب (HTML + JS) ============================

PAGE = """<!doctype html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bassam Chat AI 🤖</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--text:#e6edf3;--muted:#9ca3af;--acc:#3b82f6;--ok:#22c55e;--err:#ef4444}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,"Noto Naskh Arabic"}
header{text-align:center;padding:18px} h1{margin:0} small{color:var(--muted)}
.card{max-width:980px;margin:12px auto;padding:16px;background:var(--panel);border-radius:14px;border:1px solid #263041}
label{display:inline-flex;gap:8px;align-items:center;margin:6px 10px 10px 0}
textarea,input{width:100%;padding:10px;border-radius:10px;border:1px solid #27314c;background:#0c101a;color:var(--text)}
button{background:var(--acc);border:none;color:#fff;padding:10px 16px;border-radius:10px;font-weight:700;cursor:pointer}
#chat{height:380px;overflow:auto;background:#0c101a;border-radius:10px;border:1px solid #27314c;padding:12px;margin:10px 0}
.msg{max-width:92%;padding:10px;margin:6px 0;border-radius:10px;white-space:pre-wrap}
.user{background:#1e293b;margin-left:auto}
.bot{background:#111827;border:1px solid #1f2937}
.pill{display:inline-block;font:12px/1.6 system-ui;padding:3px 8px;border-radius:999px}
.ok{background:rgba(34,197,94,.12);color:#22c55e;border:1px solid rgba(34,197,94,.25)}
.err{background:rgba(239,68,68,.12);color:#ef4444;border:1px solid rgba(239,68,68,.25)}
.row{display:flex;gap:8px}
.row > * {flex:1}
</style></head>
<body>
<header><h1>Bassam Chat AI 🤖</h1>
<small>دردشة عربية + بحث دلالي + تعلّم تلقائي + تعلّم من الويب</small></header>

<div class="card">
  <h3>المخزن الدلالي (RAG) — إضافة يدويًا</h3>
  <textarea id="kbtext" rows="5" placeholder="ألصق نصًا أو مقالًا..."></textarea>
  <div class="row">
    <input id="kbtitle" placeholder="عنوان اختياري">
    <button id="add">إضافة للمخزن</button>
  </div>
  <div id="status"></div>
</div>

<div class="card">
  <h3>إعدادات التعلّم من الويب</h3>
  <label><input type="checkbox" id="web_on" checked> مفعل (يجلب معرفة نظيفة ويخزنها)</label>
  <div class="row">
    <input id="web_q" value="الذكاء الاصطناعي, تعلم الآلة, برمجة" placeholder="كلمات مفتاحية (مفصولة بفواصل)">
    <button id="web_go">جلب وتلخيص الآن</button>
  </div>
  <small>يستخدم DuckDuckGo لجلب أفضل الروابط، ويخزن نصًا نظيفًا داخل قاعدة المعرفة.</small>
  <div id="web_status"></div>
</div>

<div class="card">
  <h3>المحادثة</h3>
  <label><input type="checkbox" id="rag" checked> استخدم البحث الدلالي</label>
  <label><input type="checkbox" id="learn" checked> فعّل التعلّم التلقائي من المحادثات</label>
  <div id="chat"></div>
  <div class="row">
    <input id="q" placeholder="اكتب سؤالك...">
    <button id="send">إرسال</button>
  </div>
</div>

<script>
const $=s=>document.querySelector(s); const chat=$("#chat");
function push(t,w){let d=document.createElement("div");d.className="msg "+w;d.textContent=t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d;}

$("#add").onclick=async()=>{
  let t=$("#kbtext").value.trim(),h=$("#kbtitle").value.trim();
  if(!t){alert("اكتب نصًا");return}
  $("#status").innerHTML='<span class="pill">جارِ الحفظ...</span>';
  const r=await fetch("/upload",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({title:h,text:t})});
  const j=await r.json();
  $("#status").innerHTML=j.ok?'<span class="pill ok">✔ تمت الإضافة</span>':'<span class="pill err">❌ '+j.error+'</span>';
  if(j.ok){$("#kbtext").value="";$("#kbtitle").value="";}
};

$("#web_go").onclick=async()=>{
  if(!$("#web_on").checked){alert("فعّل التعلّم من الويب أولًا");return}
  $("#web_status").innerHTML='<span class="pill">يجلب المعرفة...</span>';
  const r=await fetch("/web_learn",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({q:$("#web_q").value})});
  const j=await r.json();
  $("#web_status").innerHTML=j.ok?('<span class="pill ok">جلب '+j.added+' مادة</span>'):('<span class="pill err">❌ '+j.error+'</span>');
};

$("#send").onclick=async()=>{
  const msg=$("#q").value.trim(); if(!msg) return;
  $("#q").value=""; push(msg,"user"); let hold=push("...","bot");
  const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({message:msg,use_search:$("#rag").checked,learn:$("#learn").checked})});
  if(!r.body){ hold.textContent="❌ لا يوجد بث"; return }
  const reader=r.body.getReader(); const dec=new TextDecoder(); hold.textContent="";
  while(1){const {value,done}=await reader.read(); if(done) break; hold.textContent+=dec.decode(value); chat.scrollTop=chat.scrollHeight;}
};
$("#q").addEventListener("keydown",e=>{if(e.key==="Enter")$("#send").click();});
</script>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home(_: Request):
    return HTMLResponse(PAGE)

# =============== أدوات Debug لمعرفة النماذج المتاحة =================
@app.get("/_debug/models")
def debug_models():
    try:
        names = []
        for m in genai.list_models():
            if "generateContent" in getattr(m, "supported_generation_methods", []):
                names.append(m.name)
        return {"ok": True, "models": names[:50]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============================ رفع نص للمخزن ============================

@app.post("/upload")
async def upload(data: dict):
    try:
        title = (data.get("title") or "مستند").strip()[:80]
        text  = (data.get("text")  or "").strip()
        if not text: return {"error":"نص فارغ"}
        add_doc(title, text)
        return {"ok": True, "title": title, "chars": len(text)}
    except Exception as e:
        return {"error": str(e)}

# ============================ تعلّم من الويب (DuckDuckGo + تلخيص) ============================

DDG_URL = "https://duckduckgo.com/html/?q="

def _clean_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<.*?>", " ", html)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return textwrap.shorten(text.strip(), width=4000, placeholder="...")

async def _fetch(url: str) -> str:
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent":"Mozilla/5.0"}) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text

async def _ddg_links(query: str, n=4) -> List[str]:
    html = await _fetch(DDG_URL + quote_plus(query))  # ← هنا الإصلاح
    links = re.findall(r'<a[^>]+class="result__a"[^>]+href="(.*?)"', html)
    if not links:
        links = re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)"', html)
    links = [u for u in links if "duckduckgo.com" not in u][:n]
    return links

async def _summarize(text: str, url:str) -> str:
    prompt = f"""لخّص النص التالي في نقاط عربية واضحة مع ذكر المصدر في السطر الأخير.
المصدر: {url}

النص:
{text[:3500]}"""
    def _do():
        model = genai.GenerativeModel(CHAT_MODEL)
        return model.generate_content(prompt)
    resp = _with_key_rotation(_do)
    return resp.text.strip()

@app.post("/web_learn")
async def web_learn(data: dict):
    try:
        q = (data.get("q") or "").strip()
        if not q: return {"error":"أدخل كلمات مفتاحية"}
        added = 0
        topics = [t.strip() for t in q.split(",") if t.strip()]
        for topic in topics:
            links = await _ddg_links(topic, n=3)
            for u in links:
                try:
                    html = await _fetch(u)
                    text = _clean_text(html)
                    if len(text) < 200: continue
                    summary = await _summarize(text, u)
                    add_doc(f"ويب: {topic}", f"الرابط: {u}\n\nالملخص:\n{summary}")
                    added += 1
                except Exception:
                    continue
        return {"ok": True, "added": added}
    except Exception as e:
        return {"error": str(e)}

# ============================ الدردشة (بث حي + تعلّم ذاتي) ============================

@app.post("/chat")
async def chat(payload: dict):
    msg        = (payload.get("message") or "").strip()
    use_search = bool(payload.get("use_search", True))
    learn      = bool(payload.get("learn", True))
    if not msg:
        return JSONResponse({"error":"رسالة فارغة"}, status_code=400)

    context, cites = [], []
    if use_search:
        for i,(t,c,_) in enumerate(search_docs(msg),1):
            snippet = c[:1200]
            context.append(f"[{i}] {t}: {snippet}")
            cites.append(f"[{i}] {t}")

    system = ("أنت مساعد عربي ذكي. استخدم (السياق) إن وُجد للإجابة بأمانة، "
              "واكتب الجواب متسلسلًا أثناء البث. إن كان السؤال غامضًا فاطلب إيضاحًا.")
    parts = [system]
    if context: parts.append("السياق:\n" + "\n\n".join(context))
    parts.append("السؤال:\n" + msg)
    prompt = "\n\n".join(parts)

    def stream():
        try:
            def _start():
                model = genai.GenerativeModel(CHAT_MODEL)
                return model.generate_content(prompt, stream=True)
            resp = _with_key_rotation(_start)

            final=[]
            for ch in resp:
                t = ch.text or ""
                final.append(t)
                yield t.encode("utf-8")
            ans = "".join(final).strip()
            if learn and ans:
                add_doc(f"حوار: {msg[:40]}", f"سؤال: {msg}\nإجابة: {ans}")
            if cites:
                yield f"\n\nالمراجع: {'، '.join(cites)}".encode()
        except Exception as e:
            if _is_rate_limit(str(e)):
                try:
                    _use_next_key()
                    model = genai.GenerativeModel(CHAT_MODEL)
                    resp = model.generate_content(prompt, stream=True)
                    for ch in resp:
                        yield (ch.text or "").encode("utf-8")
                    return
                except Exception as e2:
                    yield f"\n❌ خطأ: {e2}".encode()
            else:
                yield f"\n❌ خطأ: {e}".encode()
    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")

# ============================ تشغيل ============================
init_db()
