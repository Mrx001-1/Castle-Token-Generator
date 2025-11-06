````md
# Castle Token Generator

This tool generates **Castle browser request tokens** using a **headless Chromium** environment.  
Useful for automation tools (OB2, custom bots, HTTP clients) that need a valid Castle token but **cannot run browser JavaScript** themselves.

---

## How it Works

1. You send your **publishable key (`pk`)** and the **Castle JS script URL (`js`)** to the `/generate` endpoint.
2. The server launches a **headless browser**, loads the Castle script, and calls:
   ```js
   Castle.configure({ pk: pk }).createRequestToken();
````

3. The token is stored and can be retrieved from `/token?task_id=<id>`.

---

## Requirements

```bash
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

---

## Start the Server

```bash
python app.py
```

The server runs at:

```
http://127.0.0.1:5001
```

---

## API Usage

### 1) Create a Token Task

```bash
curl -X POST http://127.0.0.1:5001/generate \
  -H "Content-Type: application/json" \
  -d '{"pk":"YOUR_PUBLISHABLE_KEY","js":"https://example.com/static/scripts/castle.browser.js"}'
```

Example response:

```json
{"task_id": "c1d6c094-5bf3-4efe-ae02-7c9616eb7102"}
```

---

### 2) Retrieve the Token

Wait ~6-8 seconds, then:

```bash
curl "http://127.0.0.1:5001/token?task_id=c1d6c094-5bf3-4efe-ae02-7c9616eb7102"
```

Example response:

```json
{
  "task_id": "c1d6c094-5bf3-4efe-ae02-7c9616eb7102",
  "token": "w8_C6XuWi6UYMDoggjpihN...",
  "ts": 1762036501.124,
  "status": "stored"
}
```
