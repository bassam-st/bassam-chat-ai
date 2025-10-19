# main.py — نواة بسام: دردشة + RAG + تعلّم تلقائي من المحادثات + تعلّم تلقائي من الويب كل 30 دقيقة
import os, json, math, sqlite3, uuid, asyncio, re
from typing import List, Tuple, Optional, Dict
from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup
from readability import Document
import google.generativeai as genai

# ---------------- إعداد ----------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise RuntimeError("Environment variable GEMINI_API_KEY is required.")
genai.configure(api_key=GEMINI_API_KEY)

CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-1.5-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")
DB_PATH = os.getenv("DB_PATH", "/tmp/bassam_brain.sqlite3")  # قاعدة بيانات مؤقتة على Render المجاني

# إعدادات التعلم الذاتي من الويب (يمكن تعديلها لاحقًا من الواجهة)
AUTO_CFG_PATH = "/tmp/autolearn.json"
DEFAULT_AUTO_CFG = {
    "enabled": True,
    "interval_minutes": 30,  # كل 30 دقيقة
    "topics": ["الذكاء الاصطناعي", "تعلم الآلة", "برمجة بايثون", "أخبار التقنية"]
}

def load_auto_cfg() -> Dict:
    try:
        with open(AUTO_CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        with open(AUTO_CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_AUTO_CFG, f, ensure_ascii=False, indent=2)
        return DEFAULT_AUTO_CFG.copy()

def save_auto_cfg(cfg: Dict):
    with open(AUTO_CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

AUTO_CFG = load_auto_cfg()

app = FastAPI(title="Bassam Self-Learning AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# ---------------- قاعدة المعرفة ----------------
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
    )
    """)
    con.commit(); con.close()

def embed_text(text: str) -> List[float]:
    text = (text or "").strip()
    if not text: return []
    emb = genai.embed_content(model=EMBED_MODEL, content=text)
    return emb.get("embedding") or emb["data"][0]["embedding"]

def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b): return 0.0
    dot = sum(x*y for x,y in zip(a,b))
    na = (sum(x*x for x in a)) ** 0.5 or 1e-9
    nb = (sum(y*y for y in b)) ** 0.5 or 1e-9
    return dot/(na*nb)

def add_doc(title: str, content: str):
    emb = embed_text(content)
    con = _conn(); cur = con.cursor()
    cur.execute("INSERT INTO docs VALUES(?,?,?,?)",
                (str(uuid.uuid4()), title, content, json.dumps(emb)))
    con.commit(); con.close()

def search_docs(query: str, k=4):
    qemb = embed_text(query)
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT title,content,embedding FROM docs")
    rows = cur.fetchall(); con.close()
    ranked = []
    for t,c,e in rows:
        try: emb = json.loads(e)
        except: emb = []
        ranked.append((t,c,cosine(qemb,emb)))
    ranked.sort(key=lambda x:x[2], reverse=True)
    return ranked[:k]

# ---------------- أدوات الويب للتعلّم الذاتي ----------------
DDG_HTML = "https://duckduckgo.com/html/?q={q}"

async def fetch_text(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as s:
            r = await s.get(url)
            r.raise_for_status()
            html = r.text
        doc = Document(html)
        cleaned = doc.summary(html_partial=False)
        text = BeautifulSoup(cleaned, "html.parser").get_text(separator="\n")
        text = re.sub(r"\n{2,}", "\n", text).strip()
        return text
    except:
        return ""

async def ddg_search(query: str, k: int = 3):
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as s:
            r = await s.get(DDG_HTML.format(q=query.replace(" ", "+")))
            soup = BeautifulSoup(r.text, "html.parser")
            out = []
            for a in soup.select(".result__a")[:k]:
                href = a.get("href")
                title = a.get_text(strip=True)
                if href and href.startswith("http"):
                    out.append({"title": title, "url": href})
            return out
    except:
        return []

async def ingest_from_web(topic: str, max_pages: int = 2):
    links = await ddg_search(topic, k=max_pages)
    for link in links:
        text = await fetch_text(link["url"])
        if len(text) >= 400:
            # تقسيم بسيط لشرائح ~1000 حرف
            chunk_size = 1000
            for i in range(0, min(len(text), 6000), chunk_size):
                chunk = text[i:i+chunk_size].strip()
                if len(chunk) < 300: break
                add_doc(f"{topic} | {link['title']}", chunk)

# حلقة التعلّم الذاتي
async def autolearn_loop():
    await asyncio.sleep(5)  # انتظار إقلاع الخدمة
    while True:
        cfg = load_auto_cfg()
        if cfg.get("enabled", True):
            topics = cfg.get("topics", [])
            for t in topics:
                try:
                    await ingest_from_web(t, max_pages=2)
                except Exception:
                    pass
        await asyncio.sleep(max(5, int(cfg.get("interval_minutes", 30))) * 60)

@app.on_event("startup")
async def on_startup():
    init_db()
    # شغِّل الحلقة في الخلفية
    asyncio.create_task(autolearn_loop())

# ---------------- واجهة الويب ----------------
PAGE = """<!doctype html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bassam Chat AI 🤖</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--text:#e6edf3;--muted:#9aa4b2;--acc:#3b82f6;}
body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,"Noto Naskh Arabic";}
header{text-align:center;padding:20px;}h1{margin:0;}small{color:var(--muted);}
.card{max-width:900px;margin:12px auto;padding:16px;background:var(--panel);border-radius:12px;border:1px solid #20263a;}
textarea,input{width:100%;padding:10px;border-radius:8px;border:1px solid #27314c;background:#0c101a;color:var(--text);}
button{background:var(--acc);border:none;color:#fff;padding:10px 16px;border-radius:10px;font-weight:bold;cursor:pointer;}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:8px 0;}
#chat{height:360px;overflow:auto;background:#0c101a;border-radius:10px;border:1px solid #27314c;padding:12px;margin-bottom:10px;}
.msg{max-width:90%;padding:10px;margin:6px 0;border-radius:10px;white-space:pre-wrap;}
.user{background:#1e293b;margin-left:auto;}
.bot{background:#111827;border:1px solid #1f2937;}
label.chk{display:flex;align-items:center;gap:8px;margin:6px 0;color:#cbd5e1}
small.note{color:var(--muted);}
</style></head>
<body>
<header><h1>Bassam Chat AI 🤖</h1><small>دردشة عربية + بحث دلالي + تعلّم تلقائي من الويب</small></header>

<div class="card">
  <h3>المخزن الدلالي (RAG) — إضافة يدويًا</h3>
  <textarea id="kbtext" rows="5" placeholder="ألصق نصًا أو مقالًا..."></textarea>
  <input id="kbtitle" placeholder="عنوان اختياري">
  <button id="add">إضافة للمخزن</button> <span id="status"></span>
</div>

<div class="card">
  <h3>إعدادات التعلّم التلقائي من الويب</h3>
  <label class="chk"><input type="checkbox" id="auto-enabled"> مفعّل (يجلب معرفة كل فترة)</label>
  <div class="row">
    <input id="topics" placeholder="مواضيع مفصولة بفواصل مثل: الذكاء الاصطناعي, برمجة بايثون">
    <input id="interval" type="number" min="5" value="30" placeholder="الفاصل بالدقائق">
  </div>
  <button id="save-auto">حفظ الإعدادات</button>
  <small class="note">يستخدم DuckDuckGo لجلب أفضل الروابط، ويخزّن نصًا نظيفًا داخل قاعدة المعرفة.</small>
</div>

<div class="card">
  <h3>المحادثة</h3>
  <label class="chk"><input type="checkbox" id="rag" checked> استخدم البحث الدلالي</label>
  <label class="chk"><input type="checkbox" id="learn" checked> فعّل التعلّم التلقائي من المحادثات</label>
  <div id="chat"></div>
  <div class="row"><input id="q" placeholder="اكتب سؤالك..." /><button id="send">إرسال</button></div>
</div>

<script>
const $=s=>document.querySelector(s);const chat=$("#chat");
function push(t,w){let d=document.createElement("div");d.className="msg "+w;d.textContent=t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d;}

async function loadAuto(){
  const r=await fetch("/autolearn/status"); const j=await r.json();
  $("#auto-enabled").checked = !!j.enabled;
  $("#topics").value = (j.topics||[]).join(", ");
  $("#interval").value = j.interval_minutes || 30;
}
async function saveAuto(){
  const enabled=$("#auto-enabled").checked;
  const topics=$("#topics").value.split(",").map(s=>s.trim()).filter(Boolean);
  const interval=parseInt($("#interval").value||"30",10);
  const r=await fetch("/autolearn/config",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({enabled,topics,interval_minutes:interval})});
  const j=await r.json(); alert(j.ok?"تم الحفظ ✓":"تعذّر الحفظ");
}

$("#save-auto").onclick=saveAuto;

$("#add").onclick=async()=>{
  let t=$("#kbtext").value.trim(),h=$("#kbtitle").value.trim();
  if(!t){alert("اكتب نصًا");return}
  $("#status").textContent="جارِ الحفظ...";
  const r=await fetch("/upload",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({title:h,text:t})});
  const j=await r.json(); $("#status").textContent=j.ok?"✔️ تمت الإضافة":"❌ "+(j.error||"");
  if(j.ok){$("#kbtext").value="";$("#kbtitle").value="";}
};

$("#send").onclick=async()=>{
  const msg=$("#q").value.trim(); if(!msg) return;
  $("#q").value=""; push(msg,"user"); let hold=push("…","bot");
  const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({message:msg,use_search:$("#rag").checked,learn:$("#learn").checked})});
  const reader=r.body.getReader(); const dec=new TextDecoder(); hold.textContent="";
  while(1){const{value,done}=await reader.read(); if(done)break; hold.textContent+=dec.decode(value); chat.scrollTop=chat.scrollHeight;}
};

$("#q").addEventListener("keydown",e=>{if(e.key==="Enter")$("#send").click();});
loadAuto();
</script>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home(_: Request): 
    return HTMLResponse(PAGE)

# -------- API: RAG يدوي --------
@app.post("/upload")
async def upload(data: dict):
    try:
        title = (data.get("title") or "مستند")[:80]
        text = (data.get("text") or "").strip()
        if not text: return {"error": "نص فارغ"}
        add_doc(title, text)
        return {"ok": True, "title": title, "chars": len(text)}
    except Exception as e:
        return {"error": str(e)}

# -------- API: دردشة ببثّ حي + تعلم تلقائي من المحادثات --------
@app.post("/chat")
async def chat(payload: dict):
    msg = (payload.get("message") or "").strip()
    use_search = bool(payload.get("use_search", True))
    learn = bool(payload.get("learn", True))
    if not msg: return JSONResponse({"error":"رسالة فارغة"},status_code=400)

    context, cites = [], []
    if use_search:
        for i,(t,c,_) in enumerate(search_docs(msg),1):
            context.append(f"[{i}] {t}: {c[:800]}")
            cites.append(f"[{i}] {t}")

    system = "أنت مساعد عربي. استخدم (السياق) للإجابة بدقة. اكتب الرد بشكل متدرج أثناء البث."
    prompt = "\n\n".join([system]+(["السياق:\n"+'\n\n'.join(context)] if context else [])+["السؤال:\n"+msg])

    def stream():
        try:
            model=genai.GenerativeModel(CHAT_MODEL)
            resp=model.generate_content(prompt,stream=True)
            final=[]
            for ch in resp:
                t=ch.text or ""; final.append(t); yield t.encode("utf-8")
            ans="".join(final).strip()
            if learn and ans: 
                try: add_doc(f"حوار: {msg[:40]}", f"سؤال: {msg}\nإجابة: {ans}")
                except: pass
            if cites: yield f"\n\nالمراجع: {'، '.join(cites)}".encode()
        except Exception as e: 
            yield f"\n❌ خطأ: {e}".encode()
    return StreamingResponse(stream(),media_type="text/plain; charset=utf-8")

# -------- API: إدارة التعلّم التلقائي من الويب --------
@app.get("/autolearn/status")
def autolearn_status():
    return {
        "enabled": AUTO_CFG.get("enabled", True),
        "interval_minutes": AUTO_CFG.get("interval_minutes", 30),
        "topics": AUTO_CFG.get("topics", [])
    }

@app.post("/autolearn/config")
async def autolearn_config(body: dict):
    try:
        enabled = bool(body.get("enabled", True))
        interval = int(body.get("interval_minutes", 30))
        topics = [t.strip() for t in body.get("topics", []) if t and t.strip()]
        cfg = {
            "enabled": enabled,
            "interval_minutes": max(5, interval),
            "topics": topics or DEFAULT_AUTO_CFG["topics"]
        }
        save_auto_cfg(cfg)
        # حدّث النسخة المحمّلة
        global AUTO_CFG
        AUTO_CFG = cfg
        return {"ok": True, "cfg": cfg}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ---------------- تشغيل ----------------
init_db()
