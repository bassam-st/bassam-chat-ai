import os, json, math, sqlite3, uuid
from typing import List, Tuple

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import google.generativeai as genai

# -------- إعدادات عامة --------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise RuntimeError("Environment variable GEMINI_API_KEY is required.")

genai.configure(api_key=GEMINI_API_KEY)

CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-1.5-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")

# استخدم مسار مؤقّت قابل للكتابة على Render المجاني
DB_PATH = os.getenv("DB_PATH", "/tmp/kb.sqlite3")

app = FastAPI(title="Bassam Chat AI")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# -------- قاعدة المعرفة (SQLite + Embeddings) --------
def _connect():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS docs(
            id TEXT PRIMARY KEY,
            title TEXT,
            content TEXT,
            embedding TEXT
        )
    """)
    conn.commit()
    conn.close()

def embed_text(text: str) -> List[float]:
    text = (text or "").strip()
    if not text:
        return []
    data = genai.embed_content(model=EMBED_MODEL, content=text)
    # الاستجابة عادة: {'embedding': [floats ...]}
    return data.get("embedding") or data["data"][0]["embedding"]

def upsert_doc(title: str, content: str) -> str:
    emb = embed_text(content)
    doc_id = str(uuid.uuid4())
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO docs(id, title, content, embedding) VALUES (?, ?, ?, ?)",
        (doc_id, title, content, json.dumps(emb)),
    )
    conn.commit()
    conn.close()
    return doc_id

def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(y*y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

def search_docs(query: str, k: int = 4) -> List[Tuple[str, str, float]]:
    q_emb = embed_text(query)
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT title, content, embedding FROM docs")
    rows = cur.fetchall()
    conn.close()

    scored = []
    for title, content, emb_json in rows:
        try:
            emb = json.loads(emb_json)
        except Exception:
            emb = []
        score = cosine(q_emb, emb)
        scored.append((title, content, score))
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:k]


# -------- الواجهات --------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_to_kb(
    title: str = Form(None),
    text: str = Form(None),
    file: UploadFile | None = File(None),
):
    """
    ارفع نصًّا إلى قاعدة المعرفة:
    - إمّا عبر الحقل النصّي 'text'
    - أو ملف (txt, md, html, csv, json) سيتم قراءته كنص
    """
    try:
        content = text or ""
        if file and not content:
            raw = await file.read()
            content = raw.decode("utf-8", errors="ignore")
            if not title:
                title = file.filename or "مستند"

        if not content.strip():
            return JSONResponse({"error": "لا يوجد محتوى لرفعه"}, status_code=400)

        if not title:
            title = (content.strip().splitlines() or ["مستند"])[0][:80]

        _id = upsert_doc(title, content)
        return {"ok": True, "id": _id, "title": title, "chars": len(content)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/chat")
async def chat(payload: dict):
    """
    دردشة مع خيار استخدام البحث الدلالي من قاعدة المعرفة.
    (بدون Streaming لتفادي أخطاء 500 على Render المجاني)
    """
    try:
        message = (payload.get("message") or "").strip()
        use_search = bool(payload.get("use_search", True))
        if not message:
            return JSONResponse({"error": "No message provided"}, status_code=400)

        # —— جمع سياق من قاعدة المعرفة —— #
        context_blocks, citations = [], []
        if use_search:
            hits = search_docs(message, k=4)
            for i, (title, content, score) in enumerate(hits, 1):
                snippet = content[:800]
                context_blocks.append(f"[{i}] {title}: {snippet}")
                citations.append(f"[{i}] {title}")

        system_hint = (
            "أنت مساعد عربي. استخدم المعلومات المقتبسة ضمن (السياق) للإجابة بدقة، "
            "وأشر إلى المصادر بصيغة [1], [2] إن وُجدت. إذا لم تجد الإجابة في السياق، "
            "اصدُق القارئ وأخبره بذلك واقترح خطوات للحصول على الإجابة."
        )

        parts = [system_hint]
        if context_blocks:
            parts.append("السياق:\n" + "\n\n".join(context_blocks))
        parts.append("السؤال:\n" + message)

        model = genai.GenerativeModel(CHAT_MODEL)
        resp = model.generate_content("\n\n".join(parts))
        final_text = resp.text or "لم أتمكن من توليد إجابة حالياً."

        if citations:
            final_text += "\n\nالمراجع: " + "، ".join(citations)

        return {"reply": final_text}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# -------- بدء التشغيل --------
init_db()
