import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .chat import ChatError, stream_chat

MAX_BODY = 256 * 1024


def make_server(api_key, port=0, groq_key=None):
    token = secrets.token_urlsafe(32)
    cooldowns = {}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def valid_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def reply(self, status, body, content_type="text/plain; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.valid_host():
                self.reply(403, b"Forbidden")
                return
            path = urlsplit(self.path).path
            files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path not in files:
                self.reply(404, b"Not found")
                return
            name, kind = files[path]
            content = (Path(__file__).parent / "static" / name).read_bytes()
            if path == "/":
                content = content.replace(b"__TOKEN__", token.encode("ascii"))
            self.reply(200, content, kind)

        def do_POST(self):
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if (not self.valid_host() or self.headers.get("Origin") != origin
                    or not secrets.compare_digest(self.headers.get("X-Chat-Token", ""), token)):
                self.reply(403, b"Forbidden")
                return
            if self.path != "/chat" or self.headers.get_content_type() != "application/json":
                self.reply(400, b"Bad request")
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
                if length <= 0 or length > MAX_BODY:
                    raise ValueError()
                data = json.loads(self.rfile.read(length))
                messages = data["messages"]
                model = data.get("model", "auto")
                mode = data.get("provider", "openrouter")
                if (mode not in ("auto", "openrouter", "groq") or not isinstance(model, str) or not isinstance(messages, list) or not messages
                        or len(messages) > 200 or any(not isinstance(m, dict)
                        or m.get("role") not in ("user", "assistant")
                        or not isinstance(m.get("content"), str) or not m["content"].strip()
                        for m in messages) or messages[-1]["role"] != "user"):
                    raise ValueError()
            except (ValueError, TypeError, KeyError, UnicodeError):
                self.reply(400, b"Bad request")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()

            def send(event, value):
                payload = json.dumps({"type": event, "value": value}, ensure_ascii=True)
                self.wfile.write(f"data: {payload}\n\n".encode())
                self.wfile.flush()

            try:
                candidates = (["groq", "openrouter"] if mode == "auto" else [mode])
                keys = {"groq": groq_key, "openrouter": api_key}
                last_error = "사용 가능한 제공업체가 없습니다."
                for provider in candidates:
                    if not keys[provider]:
                        continue
                    with lock:
                        if mode == "auto" and cooldowns.get(provider, 0) > time.monotonic():
                            continue
                    selected = ("openai/gpt-oss-120b" if provider == "groq" and model == "auto"
                                else "openrouter/free" if provider == "openrouter" and model == "auto" else model)
                    send("provider", f"{provider}: {selected}")
                    emitted = False
                    try:
                        if provider == "openrouter":
                            stream = stream_chat(keys[provider], messages, selected)
                        else:
                            stream = stream_chat(keys[provider], messages, selected, provider="groq")
                        for part in stream:
                            emitted = True
                            send("text", part)
                        send("done", "")
                        return
                    except ChatError as exc:
                        last_error = str(exc)
                        if exc.retry_after:
                            with lock:
                                cooldowns[provider] = time.monotonic() + exc.retry_after
                        if mode != "auto" or emitted or not exc.retryable:
                            raise
                        send("notice", f"{provider}: {exc} 다른 제공업체를 시도합니다.")
                send("error", last_error)
            except ChatError as exc:
                send("error", str(exc))
            except (BrokenPipeError, ConnectionResetError):
                pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
