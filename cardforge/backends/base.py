"""Backend interface — the rest of CardForge never knows which engine runs.

generate() returns a list of PNG byte strings (one per image). In dry-run mode a
backend writes its exact HTTP payload to `payload_dir` and returns a 1x1 stub
image instead of calling the network — the owner's rig does the live smoke test.
"""
import json
import os
import struct
import zlib


def _stub_png():
    """A valid 1x1 grey PNG, built correctly (CRCs and all) so dry runs exercise
    the whole file pipeline — variants, contact sheets, index — end to end."""
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)      # 1x1, 8-bit RGB
    idat = zlib.compress(b"\x00\x40\x40\x48")                 # filter 0 + one pixel
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


STUB_PNG = _stub_png()


class Backend:
    name = "base"

    def __init__(self, base_url, dry_run=False, payload_dir=None, timeout=300):
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run
        self.payload_dir = payload_dir
        self.timeout = timeout

    def generate(self, positive, negative, params, job_key):
        raise NotImplementedError

    def check(self):
        """Return (ok, message) — reachability + config sanity."""
        raise NotImplementedError

    def _write_payload(self, job_key, payload):
        os.makedirs(self.payload_dir, exist_ok=True)
        path = os.path.join(self.payload_dir, "{}.{}.json".format(job_key, self.name))
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        return path
