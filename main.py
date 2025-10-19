import os, json, sqlite3, textwrap
from pathlib import Path
from typing import List, Tuple

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import numpy as np
import google.generativeai as genai

# ===== إعدادات عامة =====
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise RuntimeError("Environment variable GEMINI_API_KEY is missing")

genai.configure(api_key=GEMINI_API_KEY)
CHAT_MODEL = "gemini-1.5-flash"
EMBED_MODEL = "text-embedding-004"

BASE_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Bassam Chat AI (Gemini) + Semantic Search")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ===== قاعدة بيانات خفيفة للمعرفة =====
DB_PATH = BASE_DIR / "kb.sqlite3"

def db_init():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS docs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            embedding BLOB
        )
        """)
db_init()

def _embed(text: str) -> np.ndarray:
    text = text.strip()
    if not text:
        return np.zeros(768, dtype=np.float32)
    resp = genai.embed_content(model=EMBED_MODEL, content=text)
    vec = np.array(resp["embedding"], dtype=np.float32)
    return vec

def add_doc(title: str, content: str):
    vec = _embed(content)
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO docs(title, content, embedding) VALUES (?,?,?)",
            (title, content, vec.tobytes()),
        )

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(np.dot(a, b) / denom)

def search_docs(query: str, k: int = 4) -> List[Tuple[str, str, float]]:
    qv = _embed(query)
    rows: List[Tuple[int, str, str, bytes]] = []
    with sqlite3.connect(DB_PATH) as con:
        rows = list(con.execute("SELECT id, title, content, embedding FROM docs"))
    scored = []
    for _id, title, content, emb in rows:
        v = np.frombuffer(emb, dtype=np.float32)
        s = cosine_sim(qv, v)
        scored.append((title, content, s))
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:k]

# ===== الواجهات =====
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # عدّاد المستندات للواجهة
    with sqlite3.connect(DB_PATH) as con:
        (count,) = con.execute("SELECT COUNT(*) FROM docs").fetchone()
    return TEMPLATES.TemplateResponse("index.html", {"request": request, "doc_count": count})

@app.post("/upload")
async def upload_knowledge(title: str = Form(...), content: str = Form(...)):
    add_doc(title.strip() or "بدون عنوان", content)
    return JSONResponse({"ok": True})

@app.post("/chat")
async def chat(payload: dict):
    message = payload.get("message", "").strip()
    use_search = bool(payload.get("use_search", True))

    context_blocks = []
    citations = []
    if use_search and message:
        hits = search_docs(message, k=4)
        for i, (title, content, score) in enumerate(hits, 1):
            snippet = content[:800]
            context_blocks.append(f"[{i}] العنوان: {title}\n{snippet}")
            citations.append(f"[{i}] {title}")

    system_hint = (
        "أنت مساعد عربي واضح ومختصر. "
        "إن زُوّدتَ بسياق من (البحث الدلالي) فاستخدمه بدقة للإجابة واذكر المراجع بين أقواس مثل [1], [2]. "
        "إن لم تجد الجواب في السياق فاذكر ذلك بوضوح."
    )

    parts = []
    if context_blocks:
        parts.append("السياق المسترجع:\n" + "\n\n".join(context_blocks))

    prompt = "\n\n".join(parts + [f"السؤال: {message}"])
    model = genai.GenerativeModel(CHAT_MODEL)
    resp = model.generate_content(
        [{"role": "user", "parts": [{"text": system_hint + "\n\n" + prompt}]}],
        stream=True,
    )

    async def streamer():
        full = ""
        async for chunk in resp:
            if chunk.text:
                full += chunk.text
                yield chunk.text
        # في نهاية البث، أضف سطر المراجع إن وُجدت
        if citations:
            yield f"\n\nالمراجع: " + "، ".join(citations)

    return StreamingResponse(streamer(), media_type="text/plain; charset=utf-8")
