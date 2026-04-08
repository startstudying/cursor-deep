import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw_body or b"{}")

        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        model = data.get("model", "unknown-model")

        if data.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            chunks = [
                {
                    "id": "mock-stream-1",
                    "object": "chat.completion.chunk",
                    "created": 1710000000,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"role": "assistant", "content": "Hello"}, "finish_reason": None}],
                },
                {
                    "id": "mock-stream-1",
                    "object": "chat.completion.chunk",
                    "created": 1710000000,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": " world"}, "finish_reason": "stop"}],
                },
            ]
            for chunk in chunks:
                payload = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8")
                self.wfile.write(payload)
                self.wfile.flush()
                time.sleep(0.05)
            return

        response = {
            "id": "mock-1",
            "object": "chat.completion",
            "created": 1710000000,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello world"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }
        encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


HTTPServer(("127.0.0.1", 18081), Handler).serve_forever()
