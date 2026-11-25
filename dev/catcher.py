"""Stand-in for Outcraft: logs every POSTed JSON body to stdout and captured.jsonl."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        line = json.dumps({"path": self.path, "body": body})
        print(line, flush=True)
        with open("/data/captured.jsonl", "a") as f:
            f.write(line + "\n")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')


HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
