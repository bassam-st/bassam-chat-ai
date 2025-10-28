# main.py — Bassam Chat AI Pro
import os, io, re, json, math, uuid, sqlite3, itertools, zipfile, base64, datetime, textwrap
from typing import List, Tuple, Optional, Dict
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates
import httpx
import google.generativeai as genai

APP_TITLE = "Bassam Chat AI — Pro"
DB_PATH = os.getenv("DB_PATH", "data.db")

# -------------------- مفاتيح / إعداد --------------------
RAW_KEYS = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY", "")
KEYS = [k.strip() for k in RAW_KEYS.split(",") if k.strip()]
if not KEYS:
    raise RuntimeError("يرجى ضبط GEMINI_API_KEY أو GEMINI_API_KEYS (يمكن فصل عدة مفاتيح بفاصلة)")
_key_cycle = itertools.cycle(KEYS)
_current_key = None

CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-1.5-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")

def _set_key():
    global _current_key
    _current_key = next(_key_cycle)
    genai.configure(api_key=_current_key)

_set_key()

# -------------------- قاعدة البيانات --------------------
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS docs(
        id TEXT PRIMARY KEY,
        source TEXT,
        path TEXT,
        chunk TEXT,
        embedding BLOB
    )""")
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_docs_source_path ON docs(source, path)""")
    con.commit()
    con.close()

def db_insert_many(rows: List[Tuple[str,str,str,str,bytes]]):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executemany("INSERT OR REPLACE INTO docs(id,source,path,chunk,embedding) VALUES(?,?,?,?,?)", rows)
    con.commit()
    con.close()

def db_search_similar(qvec: List[float], k=8) -> List[Dict]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id, source, path, chunk, embedding FROM docs")
    res = []
    for rid, source, path, chunk, emb_blob in cur.fetchall():
        emb = json.loads(emb_blob.decode("utf-8"))
        # cosine similarity
        dot = sum(a*b for a,b in zip(qvec, emb))
        na = math.sqrt(sum(a*a for a in qvec)) + 1e-9
        nb = math.sqrt(sum(b*b for b in emb)) + 1e-9
        sim = dot/(na*nb)
        res.append((sim, {"id": rid, "source": source, "path": path, "chunk": chunk}))
    res.sort(key=lambda x: x[0], reverse=True)
    con.close()
    return [r for _, r in res[:k]]

# -------------------- أدوات الذكاء --------------------
def embed_texts(texts: List[str]) -> List[List[float]]:
    # إعادة المحاولة بتبديل المفتاح عند الفشل
    for attempt in range(2*len(KEYS)):
        try:
            model = genai.embed_content(model=EMBED_MODEL, content=texts, task_type="retrieval_document")
            data = model["embedding"] if "embedding" in model else model["data"]
            # واجهة gemini قد تعيد مفرد أو متعدد؛ نطبّع إلى قائمة قوائم
            if isinstance(data, list) and isinstance(data[0], float):
                return [data]
            elif isinstance(data, dict) and "embedding" in data:
                return [data["embedding"]]
            else:
                # قد تكون {"data":[{"embedding":[...]}...]}
                if isinstance(model, dict) and "data" in model:
                    out = []
                    for item in model["data"]:
                        out.append(item["embedding"])
                    return out
                return data
        except Exception as e:
            _set_key()
    raise RuntimeError("فشل إنشاء المتجهات")

def embed_for_query(q: str) -> List[float]:
    vecs = embed_texts([q])
    return vecs[0]

def chunk_text(txt: str, max_len=1200, overlap=120) -> List[str]:
    words = re.split(r'(\s+)', txt)
    chunks, cur, cur_len = [], [], 0
    for w in words:
        cur.append(w); cur_len += len(w)
        if cur_len >= max_len:
            chunks.append(''.join(cur).strip())
            cur = cur[-1*overlap:] if overlap < len(cur) else []
            cur_len = sum(len(x) for x in cur)
    if cur:
        chunks.append(''.join(cur).strip())
    return [c for c in chunks if c]

# -------------------- فهرسة ZIP بدون فك على القرص --------------------
def index_zip_bytes(data: bytes, source_name="zip-upload") -> Dict:
    zf = zipfile.ZipFile(io.BytesIO(data))
    rows = []
    total_files = 0
    for name in zf.namelist():
        if name.endswith('/'):
            continue
        # ندعم النصوص الشائعة
        if not re.search(r'\.(txt|md|csv|json|py|js|ts|html|css|xml|yml|yaml)$', name, re.I):
            continue
        try:
            raw = zf.read(name)
            try:
                txt = raw.decode("utf-8")
            except UnicodeDecodeError:
                txt = raw.decode("cp1256", errors="replace")
        except Exception:
            continue
        total_files += 1
        for ch in chunk_text(txt):
            rows.append((str(uuid.uuid4()), source_name, name, ch, json.dumps(embed_for_query(ch)).encode("utf-8")))
    if rows:
        db_insert_many(rows)
    return {"files_indexed": total_files, "chunks": len(rows)}

# -------------------- بحث ويب مبسط (قابل للاستبدال بمزود API) --------------------
async def web_search_summaries(q: str, client: httpx.AsyncClient) -> str:
    """
    تنفيذ خفيف الوزن: نحاول الطلب من DuckDuckGo HTML البسيط (بدون مفتاح).
    في بيئات مقيّدة قد يفشل. الكود مصمم بحيث يمكنك استبداله بسهولة بمزود مثل Serper/Brave/Tavily.
    """
    try:
        r = await client.get("https://duckduckgo.com/html/", params={"q": q}, timeout=15)
        text = r.text
        # اقتطاف بسيط للعناوين والسنبت
        items = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>.*?<a class="result__url".*?>(.*?)</a>.*?class="result__snippet">(.*?)</a>', text, re.S)
        bullets = []
        for title, url, snip in items[:5]:
            t = re.sub('<.*?>', '', title)
            s = re.sub('<.*?>', '', snip)
            bullets.append(f"- {t.strip()} — {s.strip()}")
        if not bullets:
            bullets = ["- (تعذر استخراج نتائج موثوقة، جرّب مزود API للبحث)"]
        return "نتائج بحث مبدئية:\n" + "\n".join(bullets)
    except Exception:
        return "لم ينجح البحث المباشر بدون مفاتيح. يُفضّل ضبط مزود API للبحث عن الويب."

# -------------------- تحديد النية --------------------
INTENT_HINTS = {
    "شرح": ["اشرح", "وضح", "فهم"],
    "ترجمة": ["ترجم", "translate"],
    "برمجة": ["كود", "شيفرة", "بايثون", "جافاسكربت", "API"],
    "رياضيات": ["حل", "معادلة", "تفاضل", "تكامل"],
    "معلومة_سريعة": ["ماهو", "ما هي", "متى", "أين"],
}

def detect_intent(q: str) -> str:
    low = q.strip().lower()
    for intent, keys in INTENT_HINTS.items():
        for k in keys:
            if k in low:
                return intent
    # fallback إلى نموذج خفيف عبر جيميني
    try:
        model = genai.GenerativeModel(CHAT_MODEL)
        prompt = f"""صنّف نية هذا السؤال بإجابة كلمة واحدة فقط من القائمة:
        [شرح, ترجمة, برمجة, رياضيات, معلومة_سريعة, غير_ذلك]
        السؤال: {q}"""
        out = model.generate_content(prompt)
        ans = (out.text or "").strip()
        ans = re.sub(r'[^اأء-ي_a-zA-Z]+', '', ans)
        return ans or "غير_ذلك"
    except Exception:
        return "غير_ذلك"

# -------------------- تكوين الإجابة (RAG + ويب) --------------------
def build_system_prompt(q: str, intent: str, ctx_docs: List[Dict], web_sum: Optional[str]) -> str:
    ctx_text = ""
    if ctx_docs:
        ctx_text = "\n\n".join([f"[{d['path']}]\n{d['chunk']}" for d in ctx_docs[:6]])
    web_text = f"\n\n[ملخص الويب]\n{web_sum}" if web_sum else ""
    guide = """قواعد الإجابة:
- أجب بالعربية الفصحى البسيطة.
- اذكر الخطوات العملية عندما يكون ذلك مفيدًا (نفذ/ثبّت/ابدأ/اعمل/...).
- عندما تكون متأكدًا من المعلومة، كن حاسمًا؛ وإلا، وضّح درجة عدم اليقين.
- إن كانت الإجابة تعتمد على نصوص داخلية، استشهد بأسماء الملفات داخل الأقواس [].
- لا تنسق Markdown مفرطًا؛ فقط عناوين فرعية بسيطة وقوائم."""
    return f"""[نية المستخدم]: {intent}
[السؤال]: {q}

[سياق داخلي مفهرس من ملفات ZIP]:
{ctx_text}

{web_text}

{guide}
— ابدأ الإجابة الآن:"""

async def generate_stream(q: str, mode: str):
    intent = detect_intent(q)
    # استرجاع داخلي
    ctx_docs = []
    try:
        qvec = embed_for_query(q)
        ctx_docs = db_search_similar(qvec, k=8)
    except Exception:
        ctx_docs = []
    # بحث ويب عند الحاجة
    web_sum = None
    if mode in ("auto", "web"):
        async with httpx.AsyncClient() as client:
            web_sum = await web_search_summaries(q, client)

    prompt = build_system_prompt(q, intent, ctx_docs if mode != "web" else [], web_sum if mode != "rag" else None)

    # بث من Gemini
    model = genai.GenerativeModel(CHAT_MODEL)
    try:
        resp = model.generate_content(
            [{"role": "user", "parts": [prompt]}],
            stream=True
        )
        acc = ""
        for chunk in resp:
            text = getattr(chunk, "text", None)
            if text:
                acc += text
                yield text.encode("utf-8")
        # نهاية
    except Exception as e:
        yield f"\n[خطأ أثناء التوليد: {e}]".encode("utf-8")

# -------------------- FastAPI --------------------
app = FastAPI(title=APP_TITLE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def _startup():
    init_db()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": APP_TITLE})

@app.get("/diag", response_class=PlainTextResponse)
def diag():
    masked = (_current_key[:6] + "..." + _current_key[-4:]) if _current_key else "NONE"
    return textwrap.dedent(f"""
    Model: {CHAT_MODEL}
    Embed: {EMBED_MODEL}
    DB: {DB_PATH}
    API(masked): {masked}
    """).strip()

@app.post("/chat")
def chat(req: dict, mode: str = "auto"):
    q = (req or {}).get("q", "").strip()
    if not q:
        return PlainTextResponse("مطلوب سؤال.", status_code=400)
    return StreamingResponse(generate_stream(q, mode), media_type="text/plain; charset=utf-8")

@app.post("/ingest-zip", response_class=JSONResponse)
async def ingest_zip(zip_url: Optional[str] = None, file: UploadFile = File(None)):
    # قراءة من ملف مرفوع
    if file is not None:
        data = await file.read()
        info = index_zip_bytes(data, source_name=file.filename or "zip-upload")
        return {"ok": True, "message": f"تم فهرسة {info['files_indexed']} ملفًا و {info['chunks']} مقطع."}
    # قراءة من رابط
    if zip_url:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(zip_url, timeout=30)
                r.raise_for_status()
                info = index_zip_bytes(r.content, source_name=zip_url)
                return {"ok": True, "message": f"تم فهرسة {info['files_indexed']} ملفًا و {info['chunks']} مقطع."}
        except Exception as e:
            return {"ok": False, "message": f"تعذر تنزيل ZIP: {e}"}
    return {"ok": False, "message": "يرجى رفع ملف ZIP أو تزويد رابط zip_url."}
