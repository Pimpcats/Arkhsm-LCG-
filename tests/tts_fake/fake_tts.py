"""Fake Tabletop Simulator for relay tests: speaks TTS's External Editor
protocol on the TTS side (listens on tts_port, reports to editor_port) and
executes "Execute Lua Code" chunks with tests/tts_fake/mock_tts.lua."""
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = shutil.which("lua5.2") or shutil.which("lua")


class FakeTTS(threading.Thread):
    def __init__(self, tts_port, editor_port, preexisting=None):
        super().__init__(daemon=True)
        self.editor_port = editor_port
        self.preexisting = preexisting      # JSON list of objects already on the table
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", tts_port))
        self.sock.listen(8)
        self.executed = []
        self.stderr = []

    def run(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                data = b""
                conn.settimeout(5)
                try:
                    while True:
                        b = conn.recv(65536)
                        if not b:
                            break
                        data += b
                except OSError:
                    pass
            if not data.strip():
                continue                    # reachability probe
            msg = json.loads(data.decode("utf-8"))
            if msg.get("messageID") == 3:
                self.execute(msg["script"])

    def to_editor(self, message):
        with socket.create_connection(("127.0.0.1", self.editor_port), timeout=5) as s:
            s.sendall(json.dumps(message).encode("utf-8"))

    def execute(self, script):
        self.executed.append(script)
        with tempfile.TemporaryDirectory() as td:
            chunk = os.path.join(td, "chunk.lua")
            with open(chunk, "w", encoding="utf-8") as f:
                f.write(script)
            cmd = [LUA, os.path.join(HERE, "mock_tts.lua"), chunk]
            if self.preexisting is not None:
                pre = os.path.join(td, "pre.json")
                with open(pre, "w", encoding="utf-8") as f:
                    json.dump(self.preexisting, f)
                cmd.append(pre)
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.stderr.append(p.stderr)
        for line in p.stdout.splitlines():
            if line.startswith("@@MSG "):
                self.to_editor(json.loads(line[6:]))

    def close(self):
        self.sock.close()
