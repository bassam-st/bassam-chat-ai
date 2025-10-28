# Bassam Chat AI — Pro
واجهة دردشة عربية مع:
- 📚 تعلم يدوي/ذاتي من ملفات ZIP بدون فك على القرص (RAG).
- 🌐 بحث ذكي في الويب (تنفيذ مبدئي قابل للاستبدال بمزود API).
- 🧭 فهم نية المستخدم.
- ⚡ بث فوري للردود (Streaming).
- 🛠 يعمل على Render بسهولة.

## التشغيل محليًا
```bash
pip install -r requirements.txt
export GEMINI_API_KEY=YOUR_KEY
uvicorn main:app --reload
```
ثم افتح: http://127.0.0.1:8000

## على Render
- اربط المتغير `GEMINI_API_KEY` في لوحة Render.
- انشر المستودع؛ سيستخدم `render.yaml` تلقائيًا.

## التغذية اليدوية بالمعرفة (ZIP)
- ارفع ملف `.zip` يحوي نصوصًا (txt, md, json, py, js, html, css, yml, yaml, xml, csv).
- تتم فهرسة المقاطع وحفظها في SQLite، مع متجهات عبر Google Embeddings.
- لاحقًا أي سؤال سيسترجع أفضل المقاطع ويُدمجها في الإجابة.

## أوضاع الإجابة
- **Auto**: يوازن بين الداخلي والويب.
- **RAG**: من الداخلي فقط.
- **Web**: من الويب فقط.

> ملاحظة: بحث الويب هنا مجرد تنفيذ بلا مفاتيح (DuckDuckGo HTML)، وقد يفشل على بعض المنصات. يُستحسن استبداله بمزود مثل Serper/Brave/Tavily بوضع مفتاح والاستهلاك داخل `web_search_summaries`.
