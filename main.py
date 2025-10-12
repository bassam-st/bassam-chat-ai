# main.py — وضعان في ملف واحد: (OpenAI ChatGPT-like) أو (بحث مجاني) + بث فوري + عربي دائم + PWA
import os, json, re, asyncio, urllib.parse
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import httpx
from duckduckgo_search import DDGS

# OpenAI (اختياري)
from openai import OpenAI

APP_NAME = "Chat-Like (Dual Mode)"

# مفاتيح/إعدادات
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
USE_OPENAI = bool(OPENAI_API_KEY)

client = OpenAI(api_key=OPENAI_API_KEY) if USE_OPENAI else None

# مسارات ثابتة
BASE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE, "static"); os.makedirs(STATIC_DIR, exist_ok=True)
TEMPLATES_DIR = os.path.join(BASE, "templates"); os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

# ───────── هوية/خصوصية (ردود جاهزة)
AR_MAP = str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه"})
def norm_ar(s:str)->str: return (s or "").strip().lower().translate(AR_MAP)

def identity_or_privacy(q:str)->Optional[str]:
    nq = norm_ar(q)
    if ("من هو بسام" in nq) or ("المطور" in nq):
        return "بسام الشتيمي هو مطور هذا النظام."
    if ("اسم ام بسام" in nq) or ("اسم زوجة بسام" in nq) or ("مرت بسام" in nq):
        return "حرصًا على الخصوصية، لا يقدّم النظام معلومات شخصية عن الأفراد."
    return None

# ───────── بحث مجاني (DuckDuckGo + Wikipedia)
def ddg_search(q:str, k:int=8)->List[Dict]:
    out=[]
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(q, region="xa-ar", safesearch="moderate", max_results=k):
                out.append({
                    "title": r.get("title",""),
                    "link": r.get("href") or r.get("url") or "",
                    "snippet": r.get("body","")
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
            if desc:
                return {"title": j.get("title") or title, "link": link, "snippet": desc}
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
    if wiki:
        res.insert(0, wiki)
    bullets = bullets_from_snips([r.get("snippet") for r in res], 8)
    return {"results": res, "bullets": bullets}

# ───────── صفحات
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "mode": "OpenAI" if USE_OPENAI else "Free Search",
        "model": LLM_MODEL if USE_OPENAI else "—"
    })

@app.get("/healthz")
def health():
    return {"ok": True, "mode": ("openai" if USE_OPENAI else "free"), "model": LLM_MODEL if USE_OPENAI else None}

# ───────── بث فوري (SSE): وضعان
@app.get("/api/chat_sse")
async def chat_sse(request: Request, q: str):
    q = (q or "").strip()
    if not q:
        async def err():
            yield "data: " + json.dumps({"chunk":"⚠️ اكتب سؤالك أولًا.","done":True}) + "\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    # إن كان سؤال هوية/خصوصية — رد فوري
    quick = identity_or_privacy(q)
    if quick:
        async def fast():
            yield "data: " + json.dumps({"chunk":quick,"done":True}) + "\n\n"
        return StreamingResponse(fast(), media_type="text/event-stream")

    # وضع OpenAI (إن توفر المفتاح)
    if USE_OPENAI and client:
        async def stream_openai():
            system_msg = (
                "أنت مساعد عربي ودود ومباشر. أجب بالعربية الفصيحة باختصار واضح، "
                "وعند الحاجة لشرح طويل قسّم الإجابة إلى نقاط."
            )
            try:
                resp = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role":"system","content":system_msg},
                        {"role":"user","content":q},
                    ],
                    temperature=0.4,
                    max_tokens=800,
                    stream=True,
                )
                # بث تدريجي
                for chunk in resp:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield "data: " + json.dumps({"chunk": delta.content}) + "\n\n"
                        await asyncio.sleep(0.003)
                yield "data: " + json.dumps({"done": True}) + "\n\n"
            except Exception as e:
                yield "data: " + json.dumps({"chunk": f'❌ خطأ من واجهة OpenAI: {e}', "done": True}) + "\n\n"
        return StreamingResponse(stream_openai(), media_type="text/event-stream")

    # وضع مجاني (بحث ويب + تلخيص بالعربية)
    async def stream_free():
        yield "data: " + json.dumps({"chunk": f"[{now_iso()}] هذا ملخص عربي مع روابط:",}) + "\n\n"
        data = await smart_search(q, 10)
        bullets = data.get("bullets", [])
        results = data.get("results", [])

        if bullets:
            for b in bullets:
                yield "data: " + json.dumps({"chunk": "• " + b + "\n"}) + "\n\n"
                await asyncio.sleep(0.005)
        else:
            yield "data: " + json.dumps({"chunk": "لم أجد تفاصيل كافية؛ إليك روابط قد تفيد:\n"}) + "\n\n"

        if results:
            yield "data: " + json.dumps({"chunk": "\nأهم الروابط:\n"}) + "\n\n"
            for r in results[:6]:
                title = r.get("title","")
                link = r.get("link","")
                yield "data: " + json.dumps({"chunk": f"- {title}: {link}\n"}) + "\n\n"
                await asyncio.sleep(0.005)

        yield "data: " + json.dumps({"chunk": f"\n[{now_iso()}] لمتابعة نقطة محددة اكتب: (عن النقطة ...).","done":True}) + "\n\n"

    return StreamingResponse(stream_free(), media_type="text/event-stream")

# ───────── Service Worker (PWA) بسيط
@app.get("/sw.js")
def sw():
    js = "self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>self.clients.claim());self.addEventListener('fetch',()=>{});"
    return HTMLResponse(js, media_type="application/javascript")
