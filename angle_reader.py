import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "100.82.127.15"   # use "127.0.0.1" to accept local connections only
PORT = 8000
JOINTS = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")
MAX_BODY = 4096


class AngleReader(threading.Thread):
    """Background thread: serve HTTP POST /angles, keep the newest sample."""

    def __init__(self, host=HOST, port=PORT, joints=JOINTS):
        super().__init__(daemon=True)
        self.joints = tuple(joints)
        self.n = len(self.joints)

        self._lock = threading.Lock()
        self._latest = None
        self._seq = 0
        self.bad_lines = 0
        self.error = None

        # Binds and listens immediately, like your old socket setup did.
        self._server = ThreadingHTTPServer((host, port), self._make_handler())
        print(f"server is listening on {host}:{port}...")

    # ---------- thread body ----------
    def run(self):
        try:
            self._server.serve_forever()
        except Exception as e:
            self.error = e

    # ---------- public API ----------
    def get(self):
        with self._lock:
            # deepcopy because the sample contains a nested "angles" dict
            return self._seq, copy.deepcopy(self._latest)

    def close(self):
        if self.is_alive():
            self._server.shutdown()   # would block forever if run() never started
        self._server.server_close()
        self.join(timeout=1)

    # ---------- internals ----------
    def _validate(self, msg):
        """Return None if msg has the expected shape, else an error string."""
        if not isinstance(msg, dict):
            return "body must be a JSON object"
        if not (msg.get("units") == "deg" or msg.get("units") == "rad"):
            return "'units' must be either deg or rad"
        angles = msg.get("angles")
        if not isinstance(angles, dict):
            return "'angles' must be an object"
        if set(angles) != set(self.joints):
            return f"'angles' must have exactly: {', '.join(self.joints)}"
        for name, value in angles.items():
            # bool is a subclass of int, so exclude it explicitly
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return f"'{name}' must be a number"
        return None

    def _store(self, msg):
        with self._lock:
            self._latest = msg
            self._seq += 1
            return self._seq

    def _reject(self, reason):
        with self._lock:
            self.bad_lines += 1
        self.error = reason

    def _make_handler(self):
        reader = self  # the Handler class below captures this

        class Handler(BaseHTTPRequestHandler):
            timeout = 5  # a stalled client can't hold a worker thread forever

            def do_POST(self):
                if self.path != "/angles":
                    return self._reply(404, {"error": "not found"})

                # 1. How many body bytes are coming?
                try:
                    length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    reader._reject("missing Content-Length")
                    return self._reply(411, {"error": "Content-Length required"})
                if not 0 < length <= MAX_BODY:
                    reader._reject(f"bad body size: {length}")
                    return self._reply(413, {"error": "bad body size"})

                # 2. Read exactly that many bytes
                try:
                    body = self.rfile.read(length)
                except OSError:  # includes socket timeout
                    reader._reject("timed out reading body")
                    self.close_connection = True
                    return

                # 3. bytes -> dict
                try:
                    msg = json.loads(body)
                except ValueError:  # JSONDecodeError and UnicodeDecodeError
                    reader._reject("invalid JSON")
                    return self._reply(400, {"error": "invalid JSON"})

                # 4. Right shape?
                err = reader._validate(msg)
                if err:
                    reader._reject(err)
                    return self._reply(422, {"error": err})

                # 5. Save and confirm
                seq = reader._store(msg)
                self._reply(200, {"ok": True, "seq": seq})

            def _reply(self, status, obj):
                data = json.dumps(obj).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, fmt, *args):
                pass  # silence per-request console output

        return Handler