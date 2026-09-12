import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=60010)
parser.add_argument("--mode", choices=("timeout", "429", "500", "invalid", "malformed", "ok"), required=True)
args = parser.parse_args()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        self.rfile.read(length)
        if args.mode == "timeout":
            time.sleep(5)
        status = {"429": 429, "500": 500, "invalid": 401}.get(args.mode, 200)
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream" if status == 200 else "application/json")
        self.end_headers()
        if status != 200:
            self.wfile.write(json.dumps({"error": {"message": f"provider fault {args.mode}"}}).encode())
        elif args.mode == "malformed":
            self.wfile.write(b"data: not-json\n\ndata: [DONE]\n\n")
        else:
            event = {"choices": [{"delta": {"content": "PROVIDER-RECOVERED-OK"}}]}
            self.wfile.write(f"data: {json.dumps(event)}\n\ndata: [DONE]\n\n".encode())

    def log_message(self, _format, *_args):
        return


ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
