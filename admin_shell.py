from future import annotations from fastapi import APIRouter, HTTPException, status, Request from pydantic import BaseModel import subprocess, shlex, os, time from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()

=== إعدادات ===

ADMIN_PIN = os.getenv("ADMIN_PIN", "bassam1234")  # غيّرها من متغيرات البيئة في Render ALLOW_UNSAFE = os.getenv("ADMIN_SHELL_MODE", "safe").lower() == "unsafe" WORKDIR = os.getenv("APP_WORKDIR", ".")

SAFE_PREFIXES = ( "python", "python3", "pip", "pip3", "ls", "pwd", "echo", "cat", "head", "tail", "whoami", )

_last_hit: dict[str, float] = {}

class ShellIn(BaseModel): pin: str command: str

@router.get("/shell", response_class=HTMLResponse) async def shell_page(_: Request): return HTMLResponse(content=_SHELL_HTML, status_code=200)

@router.post("/shell/run") async def shell_run(req: Request, body: ShellIn): if body.pin != ADMIN_PIN: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN")

ip = req.client.host if req.client else "unknown"
now = time.time()
last = _last_hit.get(ip, 0)
if now - last < 1.0:
    raise HTTPException(status_code=429, detail="Too many requests; slow down")
_last_hit[ip] = now

cmd = body.command.strip()
if not cmd:
    raise HTTPException(status_code=400, detail="Empty command")

if not ALLOW_UNSAFE and not cmd.startswith(SAFE_PREFIXES):
    raise HTTPException(status_code=400, detail="Command not allowed in safe mode. Allowed prefixes: " + ", ".join(SAFE_PREFIXES))

use_shell = False
args: list[str]
try:
    args = shlex.split(cmd)
except Exception:
    if not ALLOW_UNSAFE:
        raise HTTPException(status_code=400, detail="Unable to parse command safely")
    use_shell = True
    args = [cmd]

try:
    start = time.time()
    completed = subprocess.run(
        args if not use_shell else cmd,
        cwd=WORKDIR,
        capture_output=True,
        text=True,
        shell=use_shell,
        timeout=120,
    )
    dur = time.time() - start
    return JSONResponse(
        {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "duration_sec": round(dur, 3),
            "stdout": completed.stdout[-20000:],
            "stderr": completed.stderr[-20000:],
            "workdir": os.path.abspath(WORKDIR),
            "mode": "unsafe" if ALLOW_UNSAFE else "safe",
        }
    )
except subprocess.TimeoutExpired:
    raise HTTPException(status_code=408, detail="Command timed out after 120s")

_SHELL_HTML = r""" <!doctype html>

<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Shell المطوّر — bassam-chat-ai</title>
  <style>
    :root { --ink:#0f172a; --bg:#0b1020; --muted:#9aa4b2; --ok:#16a34a; --err:#dc2626; --card:#0f172a; }
    *{box-sizing:border-box}
    body{margin:0; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background:linear-gradient(180deg,#0b1020,#0b1428); color:#e5e7eb}
    .wrap{max-width:920px;margin:16px auto;padding:12px}
    .card{background:#0f172a;border:1px solid #1f2937;border-radius:16px;padding:16px}
    h1{font-size:20px;margin:0 0 12px}
    .row{display:flex;gap:8px;flex-wrap:wrap}
    input,button,textarea{border-radius:10px;border:1px solid #334155;background:#0b1220;color:#e5e7eb}
    input,button{height:44px}
    input{padding:0 12px;}
    button{padding:0 16px;cursor:pointer}
    button:hover{filter:brightness(1.15)}
    textarea{width:100%;min-height:300px;padding:12px;resize:vertical;white-space:pre-wrap}
    .hint{color:#94a3b8;font-size:12px;margin-top:8px}
    .ok{color:var(--ok)} .err{color:var(--err)}
    .badge{display:inline-block;padding:2px 8px;border:1px solid #334155;border-radius:999px;color:#94a3b8;font-size:12px}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>🛠️ Shell المطوّر — bassam-chat-ai <span id="mode" class="badge"></span></h1>
      <div class="row">
        <input id="pin" type="password" placeholder="PIN" style="flex:1 1 160px"/>
        <input id="cmd" type="text" placeholder="أكتب الأمر هنا (مثال: pip list)" style="flex:3 1 420px"/>
        <button id="run">تشغيل</button>
      </div>
      <div class="hint">سيحفظ المتصفح الـ PIN محليًا فقط على جهازك.</div>
      <textarea id="out" placeholder="> الناتج سيظهر هنا..."></textarea>
      <div class="hint">في الوضع الآمن يُسمح بالأوامر التي تبدأ بـ: python, pip, ls, pwd, echo, cat, head, tail, whoami</div>
    </div>
  </div>
  <script>
    const $ = (id)=>document.getElementById(id);
    const pinEl = $("pin"), cmdEl=$("cmd"), outEl=$("out"), runBtn=$("run"), modeEl=$("mode");
    pinEl.value = localStorage.getItem("dev_pin") || "";async function run(){
  const pin = pinEl.value.trim();
  const command = cmdEl.value.trim();
  if(!pin || !command){ alert("أدخل PIN والأمر"); return; }
  localStorage.setItem("dev_pin", pin);
  outEl.value = "⏳ Running: " + command + "\n\n";
  runBtn.disabled = true;
  try{
    const res = await fetch("/admin/shell/run",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({pin, command})
    });
    const data = await res.json();
    if(!res.ok){
      outEl.value += `❌ Error (${res.status}): ${data.detail || JSON.stringify(data)}\n`;
    } else {
      modeEl.textContent = `mode: ${data.mode}`;
      outEl.value += (data.stdout || "") + (data.stderr? `\n[stderr]\n${data.stderr}`:"") + `\n\n— exit=${data.exit_code}, duration=${data.duration_sec}s`;
    }
  }catch(err){
    outEl.value += `❌ ${err}`;
  } finally {
    runBtn.disabled = false;
    outEl.scrollTop = outEl.scrollHeight;
  }
}
runBtn.addEventListener("click", run);
cmdEl.addEventListener("keydown", e=>{ if(e.key==="Enter" && (e.ctrlKey||e.metaKey)) run(); });

  </script>
</body>
</html>
"""
