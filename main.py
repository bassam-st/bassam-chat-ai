# main.py — نواة بسام المتكاملة (بحث دلالي + تعلّم ذاتي + بثّ حيّ)
import os, json, math, sqlite3, uuid
from typing import List, Tuple, Optional
from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

# ---------------- إعداد ----------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise RuntimeError("Environment variable GEMINI_API_KEY is required.")
genai.configure(api_key=GEMINI_API_KEY)

CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-1.5-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")
DB_PATH = os.getenv("DB_PATH", "/tmp/bassam_brain.sqlite3")  # قاعدة بيانات مؤقتة على Render المجاني

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
    na = math.sqrt(sum(x*x for x in a)) or 1e-9
    nb = math.sqrt(sum(y*y for y in b)) or 1e-9
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

# ---------------- واجهة الويب ----------------
PAGE = """<!doctype html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bassam Chat AI 🤖</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--text:#e6edf3;--muted:#9ca3af;--acc:#3b82f6;}
body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,"Noto Naskh Arabic";}
header{text-align:center;padding:20px;}h1{margin:0;}small{color:var(--muted);}
.card{max-width:900px;margin:12px auto;padding:16px;background:var(--panel);border-radius:12px;}
textarea,input{width:100%;padding:10px;border-radius:8px;border:1px solid #27314c;background:#0c101a;color:var(--text);}
button{background:var(--acc);border:none;color:#fff;padding:10px 16px;border-radius:10px;font-weight:bold;cursor:pointer;}
#chat{height:360px;overflow:auto;background:#0c101a;border-radius:10px;border:1px solid #27314c;padding:12px;margin-bottom:10px;}
.msg{max-width:90%;padding:10px;margin:6px 0;border-radius:10px;white-space:pre-wrap;}
.user{background:#1e293b;margin-left:auto;}
.bot{background:#111827;border:1px solid #1f2937;}
</style></head>
<body>
<header><h1>Bassam Chat AI 🤖</h1><small>نظام تعلّم ذاتي + بحث دلالي + بثّ حيّ للرد</small></header>
<div class="card">
  <h3>إضافة إلى قاعدة المعرفة</h3>
  <textarea id="kbtext" rows="5" placeholder="ألصق نصًا أو مقالًا..."></textarea>
  <input id="kbtitle" placeholder="عنوان اختياري"><br>
  <button id="add">إضافة للمخزن</button><div id="status"></div>
</div>
<div class="card">
  <h3>المحادثة</h3>
  <label><input type="checkbox" id="rag" checked> استخدم البحث الدلالي</label><br>
  <label><input type="checkbox" id="learn" checked> فعّل التعلّم التلقائي</label>
  <div id="chat"></div>
  <input id="q" placeholder="اكتب سؤالك..." /><button id="send">إرسال</button>
</div>
<script>
const $=s=>document.querySelector(s);const chat=$("#chat");
function push(t,w){let d=document.createElement("div");d.className="msg "+w;d.textContent=t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d;}
$("#add").onclick=async()=>{let t=$("#kbtext").value.trim(),h=$("#kbtitle").value.trim();if(!t){alert("اكتب نصًا");return}
$("#status").textContent="جارِ الحفظ...";const r=await fetch("/upload",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({title:h,text:t})});
const j=await r.json();$("#status").textContent=j.ok?"✔️ تمت الإضافة":"❌ "+j.error;$("#kbtext").value="";}
$("#send").onclick=async()=>{const msg=$("#q").value.trim();if(!msg)return;$("#q").value="";push(msg,"user");let hold=push("...","bot");
const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({message:msg,use_search:$("#rag").checked,learn:$("#learn").checked})});
const reader=r.body.getReader();const dec=new TextDecoder();hold.textContent="";
while(1){const{value,done}=await reader.read();if(done)break;hold.textContent+=dec.decode(value);chat.scrollTop=chat.scrollHeight;}
}
$("#q").addEventListener("keydown",e=>{if(e.key==="Enter")$("#send").click();});
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
def home(_: Request): return HTMLResponse(PAGE)

# ---------------- رفع النص للمخزن ----------------
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

# ---------------- الدردشة ببث حي ----------------
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

    system = "أنت مساعد عربي ذكي. استخدم النصوص في (السياق) للإجابة. اكتب الإجابة بالتدريج أثناء البث."
    prompt = "\n\n".join([system]+(["السياق:\n"+'\n\n'.join(context)] if context else [])+["السؤال:\n"+msg])

    def stream():
        try:
            model=genai.GenerativeModel(CHAT_MODEL)
            resp=model.generate_content(prompt,stream=True)
            final=[]
            for ch in resp:
                t=ch.text or "";final.append(t);yield t.encode("utf-8")
            ans="".join(final)
            if learn and ans: add_doc(f"حوار: {msg[:40]}", f"سؤال: {msg}\nإجابة: {ans}")
            if cites: yield f"\n\nالمراجع: {'، '.join(cites)}".encode()
        except Exception as e: yield f"\n❌ خطأ: {e}".encode()
    return StreamingResponse(stream(),media_type="text/plain; charset=utf-8")

# ---------------- تشغيل ----------------
init_db()
