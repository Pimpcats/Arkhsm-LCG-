"""Resume ledger — crash-safe overnight runs never redo completed work.

A completed unit is one (card id, seed) pair. The ledger is a flat JSON list of
"id:seed" keys, rewritten atomically on every mark so a kill -9 mid-run loses at
most the in-flight image.
"""
import json
import os
import tempfile


class Ledger:
    def __init__(self, path):
        self.path = path
        self.done = set()
        if os.path.exists(path):
            self.done = set(json.load(open(path)))

    @staticmethod
    def key(job_id, seed):
        return "{}:{}".format(job_id, seed)

    def is_done(self, job_id, seed):
        return self.key(job_id, seed) in self.done

    def mark(self, job_id, seed):
        self.done.add(self.key(job_id, seed))
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path) or ".")
        with os.fdopen(fd, "w") as f:
            json.dump(sorted(self.done), f)
        os.replace(tmp, self.path)
