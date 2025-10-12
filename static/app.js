const chat = document.getElementById('chat');
const q = document.getElementById('q');

function addMsg(txt, who){
  const d = document.createElement('div');
  d.className = 'msg ' + (who || 'bot');
  const ts = document.createElement('span');
  ts.className = 'ts';
  ts.textContent = new Date().toISOString();
  d.appendChild(ts);
  d.appendChild(document.createTextNode('\n' + txt));
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
}

addMsg("👋 أهلاً! اكتب سؤالك وسأجيبك فورًا — إذا وُجد مفتاح OpenAI أعمل مثل ChatGPT، وإلا ألخّص من الويب بالعربية.", "bot");

function sendMsg(){
  const text = q.value.trim();
  if(!text) return false;
  addMsg(text, 'user');
  q.value = '';

  const holder = document.createElement('div');
  holder.className = 'msg bot';
  const ts = document.createElement('span');
  ts.className = 'ts';
  ts.textContent = new Date().toISOString();
  holder.appendChild(ts);
  const tn = document.createTextNode('...');
  holder.appendChild(tn);
  chat.appendChild(holder);

  const es = new EventSource(`/api/chat_sse?q=${encodeURIComponent(text)}`);
  let buf = '';
  es.onmessage = (e) => {
    const d = JSON.parse(e.data);
    if (d.chunk) {
      buf += d.chunk;
      holder.childNodes[1].nodeValue = '\n' + buf;
      chat.scrollTop = chat.scrollHeight;
    }
    if (d.done) es.close();
  };
  es.onerror = () => es.close();
  return false;
}
