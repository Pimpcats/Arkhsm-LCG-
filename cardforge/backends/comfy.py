"""ComfyUI adapter.

Loads an API-format workflow template (cardforge/workflows/*.json), injects the
composed prompt/params into nodes located BY `_meta.title` tag (so the owner can
rearrange the graph in the UI and re-export without breaking injection), then:
    POST {base}/prompt {"prompt": graph, "client_id": ...} -> {"prompt_id"}
    poll GET {base}/history/{prompt_id} until outputs appear
    GET {base}/view?filename=..&subfolder=..&type=output  -> PNG bytes

Deviation from CARDFORGE_BRIEF §3 (flagged, not hidden): the brief tracks
progress via the /ws websocket; v1 polls /history instead — dependency-free and
sufficient for a serial batch. Swap in websocket tracking if you want live
progress bars.

Tagged nodes a template must carry: CF_CHECKPOINT (CheckpointLoaderSimple),
CF_POSITIVE / CF_NEGATIVE (CLIPTextEncode), CF_LATENT (EmptyLatentImage),
CF_SAMPLER (KSampler). Verify node class names against your ComfyUI version.
"""
import copy
import json
import os
import time
import uuid

import requests

from .base import Backend, STUB_PNG


class ComfyBackend(Backend):
    name = "comfy"
    DEFAULT_URL = "http://127.0.0.1:8188"
    POLL_SECONDS = 1.5

    def __init__(self, base_url, workflows_dir, **kw):
        super().__init__(base_url, **kw)
        self.workflows_dir = workflows_dir
        self.client_id = str(uuid.uuid4())

    def _load_graph(self, workflow_ref):
        path = os.path.join(self.workflows_dir, os.path.basename(workflow_ref))
        return json.load(open(path, encoding="utf-8"))

    @staticmethod
    def _by_title(graph, title):
        for node_id, node in graph.items():
            if node.get("_meta", {}).get("title") == title:
                return node
        raise KeyError("workflow has no node tagged _meta.title=" + title)

    def _inject(self, graph, positive, negative, params):
        g = copy.deepcopy(graph)
        self._by_title(g, "CF_POSITIVE")["inputs"]["text"] = positive
        self._by_title(g, "CF_NEGATIVE")["inputs"]["text"] = negative
        self._by_title(g, "CF_CHECKPOINT")["inputs"]["ckpt_name"] = params["checkpoint"]
        latent = self._by_title(g, "CF_LATENT")["inputs"]
        latent["width"], latent["height"] = params["width"], params["height"]
        sampler = self._by_title(g, "CF_SAMPLER")["inputs"]
        sampler["seed"] = params["seed"]
        sampler["steps"] = params["steps"]
        sampler["cfg"] = params["cfg"]
        sampler["sampler_name"] = params["sampler"]
        return g

    def generate(self, positive, negative, params, job_key):
        graph = self._inject(self._load_graph(params["comfy_workflow"] or
                                              "workflows/txt2img_scene.json"),
                             positive, negative, params)
        payload = {"prompt": graph, "client_id": self.client_id}
        if self.dry_run:
            self._write_payload(job_key, payload)
            return [STUB_PNG]
        r = requests.post(self.base_url + "/prompt", json=payload, timeout=30)
        r.raise_for_status()
        prompt_id = r.json()["prompt_id"]
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            h = requests.get(self.base_url + "/history/" + prompt_id, timeout=30).json()
            entry = h.get(prompt_id)
            if entry and entry.get("outputs"):
                images = []
                for node_out in entry["outputs"].values():
                    for img in node_out.get("images", []):
                        v = requests.get(self.base_url + "/view", params={
                            "filename": img["filename"],
                            "subfolder": img.get("subfolder", ""),
                            "type": img.get("type", "output")}, timeout=60)
                        v.raise_for_status()
                        images.append(v.content)
                return images
            time.sleep(self.POLL_SECONDS)
        raise TimeoutError("ComfyUI job {} exceeded {}s".format(prompt_id, self.timeout))

    def check(self):
        if self.dry_run:
            return True, "dry-run (no backend contacted)"
        try:
            r = requests.get(self.base_url + "/system_stats", timeout=10)
            r.raise_for_status()
            return True, "reachable ({})".format(self.base_url)
        except Exception as e:  # noqa: BLE001
            return False, "unreachable at {} ({})".format(self.base_url, e)
