from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import threading, time, uuid

app = Flask(__name__)
CORS(app)

_tokens = {}
_html_tasks = {}


@app.route("/castle/<task_id>")
def castle_page(task_id):
    """Serves task-specific Castle HTML"""
    t = _html_tasks.get(task_id)
    if not t:
        return "<h3>Invalid task</h3>", 404
    return f"""
    <html><body>
    <script src="{t['js']}"></script>
    <script>
    async function go(){{
        try {{
            const castle = Castle.configure({{pk:"{t['pk']}"}}); 
            const token = await castle.createRequestToken();
            console.log("CASTLE_TOKEN=" + token);
        }}catch(e){{console.log("CASTLE_ERROR=" + e.message);}}
    }}
    window.onload=go;
    </script></body></html>
    """


def generate_token(task_id, pk, js_url):
    token_holder = {"value": None}

    def on_console(msg):
        text = msg.text
        if text.startswith("CASTLE_TOKEN="):
            token_holder["value"] = text.split("CASTLE_TOKEN=")[1].strip()
            print(f"[OK] Token captured for {task_id}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("console", on_console)
            page.goto(f"http://127.0.0.1:5001/castle/{task_id}")
            time.sleep(8)
            browser.close()

        _tokens[task_id] = {
            "token": token_holder["value"],
            "ts": time.time(),
            "status": "stored" if token_holder["value"] else "error: no token",
        }
    except Exception as e:
        _tokens[task_id] = {
            "token": None,
            "ts": time.time(),
            "status": f"error: {e}",
        }


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    pk = data.get("pk")
    js = data.get("js")
    if not pk or not js:
        return jsonify({"error": "missing pk or js"}), 400

    task_id = str(uuid.uuid4())
    _tokens[task_id] = {"token": None, "ts": None, "status": "running"}
    _html_tasks[task_id] = {"pk": pk, "js": js}

    threading.Thread(target=generate_token, args=(task_id, pk, js), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/token", methods=["GET"])
def get_token():
    tid = request.args.get("task_id")
    if not tid:
        return jsonify({"error": "missing task_id"}), 400
    return jsonify({"task_id": tid, **_tokens.get(tid, {"error": "not found"})})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
