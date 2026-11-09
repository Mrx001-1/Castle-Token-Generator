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
    <script>
      const JS_URL = "{t['js']}";
      const PK = "{t['pk']}";

      window.addEventListener('error', function(e){{
        // Swallow the "import statement outside a module" error — expected for ES-module bundles.
        if (e.message && e.message.indexOf('import statement') !== -1) return;
      }});

      function findCastle(obj){{
        if(!obj) return null;
        if(typeof obj.configure === 'function') return obj;
        if(obj.default && typeof obj.default.configure === 'function') return obj.default;
        if(obj.Castle && typeof obj.Castle.configure === 'function') return obj.Castle;
        return null;
      }}

      async function tryClassicScript(){{
        return new Promise((resolve) => {{
          const s = document.createElement('script');
          s.src = JS_URL;
          s.onload = () => setTimeout(() => {{
            const lib = findCastle(window.Castle) || findCastle(window['@castleio/castle-js']);
            resolve(lib);
          }}, 300);
          s.onerror = () => resolve(null);
          document.head.appendChild(s);
        }});
      }}

      async function tryModuleImport(){{
        try {{
          const mod = await import(JS_URL);
          return findCastle(mod);
        }} catch(e) {{
          console.log("MODULE_IMPORT_ERR=" + e.message);
          return null;
        }}
      }}

      (async function(){{
        try {{
          let CastleLib = await tryClassicScript();
          if(!CastleLib) CastleLib = await tryModuleImport();

          if(!CastleLib){{
            console.log("CASTLE_ERROR=Castle SDK could not be loaded as classic script or ES module");
            return;
          }}

          const castle = CastleLib.configure({{pk: PK}});
          const token = await castle.createRequestToken();
          console.log("CASTLE_TOKEN=" + token);
        }} catch(e) {{
          console.log("CASTLE_ERROR=" + e.message + " || " + (e.stack || ''));
        }}
      }})();
    </script>
    </body></html>
    """


def generate_token(task_id, pk, js_url):
    token_holder = {"value": None}

    def on_console(msg):
        text = msg.text
        print(f"[browser:{task_id}] {msg.type}: {text}")
        if text.startswith("CASTLE_TOKEN="):
            token_holder["value"] = text.split("CASTLE_TOKEN=")[1].strip()
            print(f"[OK] Token captured for {task_id}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("console", on_console)
            page.on("pageerror", lambda exc: print(f"[pageerror:{task_id}] {exc}"))
            page.on("requestfailed", lambda req: print(f"[reqfail:{task_id}] {req.url} {req.failure}"))
            page.on("response", lambda resp: print(f"[resp:{task_id}] {resp.status} {resp.url}") if 'castle' in resp.url.lower() or resp.url.endswith('.js') else None)
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
    app.run(host="127.0.0.1", port=5001, debug=False)
