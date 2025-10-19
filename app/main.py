import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Please set GEMINI_API_KEY environment variable on Render.")

genai.configure(api_key=GEMINI_API_KEY)
MODEL = genai.GenerativeModel("gemini-1.5-flash")  # مجاني وسريع

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/chat")
async def chat(prompt: str):
    def stream():
        try:
            resp = MODEL.generate_content(prompt, stream=True)
            for chunk in resp:
                text = getattr(chunk, "text", None)
                if text:
                    yield text
        except Exception as e:
            yield f"\n[ERROR] {e}"
        finally:
            yield "\n[DONE]"
    return EventSourceResponse(stream())
