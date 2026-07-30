"""OpenAI image adapter — generate card art through the OpenAI API.

Endpoint: POST https://api.openai.com/v1/images/generations
    {model, prompt, n, size, quality}
Images come back base64 in r["data"][i]["b64_json"].

This is a hosted API, not a local diffusion UI, so several Stable Diffusion
concepts simply don't exist here and are adapted rather than passed through:

  negative prompt  there is no negative field, so the campaign's style_negative
                   is folded onto the end of the prompt as an "avoid" clause.
  seed             not supported — the same prompt won't reproduce the same
                   image. Re-rolling a variant works; pinning one doesn't.
  steps/cfg/sampler
                   diffusion knobs with no equivalent; ignored on purpose.
  checkpoint       replaced by the model choice (gpt-image-1 / dall-e-3), and
                   the "look" comes from the campaign's style text instead of
                   a .safetensors file.

The API key is NOT a ChatGPT subscription — it is a separate, pay-per-image
credit balance from platform.openai.com.
"""
import base64
import os

import requests

from .base import Backend, STUB_PNG

# the sizes the image models actually accept; everything else is snapped to the
# closest of these by aspect ratio
_SIZES = {"square": "1024x1024", "landscape": "1536x1024", "portrait": "1024x1536"}


def key_path():
    from .. import runner
    return os.path.join(runner.repo_root(), "state", "openai_key.txt")


def load_key():
    """The API key: the saved file first, then OPENAI_API_KEY from the env."""
    try:
        p = key_path()
        if os.path.exists(p):
            k = open(p, encoding="utf-8").read().strip()
            if k:
                return k
    except OSError:
        pass
    return (os.environ.get("OPENAI_API_KEY") or "").strip()


def save_key(key):
    p = key_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write((key or "").strip())


def pick_size(width, height):
    """Snap a requested pixel size to the nearest shape the API supports."""
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        return _SIZES["square"]
    if w <= 0 or h <= 0:
        return _SIZES["square"]
    r = w / float(h)
    if r >= 1.2:
        return _SIZES["landscape"]
    if r <= 0.83:
        return _SIZES["portrait"]
    return _SIZES["square"]


def build_prompt(positive, negative):
    """One prompt string: the composed subject+style, plus the campaign's
    negative list turned into a plain-language avoid clause, since the API has
    no negative field."""
    text = (positive or "").strip()
    neg = (negative or "").strip()
    if neg:
        text += "\n\nDo not include: " + neg + "."
    return text


class OpenAIBackend(Backend):
    name = "openai"
    DEFAULT_URL = "https://api.openai.com"
    DEFAULT_MODEL = "gpt-image-1"
    MODELS = ["gpt-image-1", "dall-e-3"]

    def __init__(self, base_url=None, dry_run=False, payload_dir=None,
                 timeout=300, api_key=None, model=None):
        Backend.__init__(self, base_url or self.DEFAULT_URL, dry_run=dry_run,
                         payload_dir=payload_dir, timeout=timeout)
        self.api_key = api_key or load_key()
        self.model = model or self.DEFAULT_MODEL

    def _headers(self):
        return {"Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json"}

    def generate(self, positive, negative, params, job_key):
        model = (params.get("checkpoint") or self.model or "").strip()
        if model.lower().endswith((".safetensors", ".ckpt")) or not model:
            model = self.DEFAULT_MODEL      # campaign was set up for a local SD
        payload = {
            "model": model,
            "prompt": build_prompt(positive, negative),
            "n": 1,
            "size": pick_size(params.get("width"), params.get("height")),
        }
        # dall-e-* returns a URL unless asked for base64; the gpt-image family
        # returns base64 already and takes a quality tier instead
        if model.lower().startswith("dall-e"):
            payload["response_format"] = "b64_json"
        else:
            payload["quality"] = params.get("quality") or "high"
        if self.dry_run:
            self._write_payload(job_key, payload)
            return [STUB_PNG]
        if not self.api_key:
            raise RuntimeError(
                "no OpenAI API key — paste one in 2 · Illustrate → Backend, or "
                "set OPENAI_API_KEY. Get it from platform.openai.com → API keys "
                "(a ChatGPT subscription does not include API access).")
        r = requests.post(self.base_url + "/v1/images/generations",
                          json=payload, headers=self._headers(),
                          timeout=self.timeout)
        if r.status_code >= 400:
            raise RuntimeError(self._explain(r))
        return [base64.b64decode(d["b64_json"]) for d in r.json().get("data", [])
                if d.get("b64_json")]

    @staticmethod
    def _explain(r):
        """Turn an API error into something the Activity log can act on."""
        try:
            msg = r.json().get("error", {}).get("message", r.text[:300])
        except ValueError:
            msg = r.text[:300]
        if r.status_code == 401:
            return "OpenAI rejected the API key (401). Check it at platform.openai.com → API keys."
        if r.status_code == 429:
            return ("OpenAI rate limit / no credit (429). Image calls bill against a "
                    "prepaid balance that a ChatGPT subscription does not cover: " + msg)
        if r.status_code == 400 and "safety" in msg.lower():
            return ("OpenAI refused this prompt on content policy — horror wording "
                    "sometimes trips it. Reword the scene and retry: " + msg)
        return "OpenAI error {}: {}".format(r.status_code, msg)

    def check(self):
        if self.dry_run:
            return True, "dry-run (no backend contacted)"
        if not self.api_key:
            return False, ("no API key saved. Get one at platform.openai.com → API "
                           "keys and paste it into the Backend row. Note this bills "
                           "per image and is separate from a ChatGPT subscription.")
        try:
            r = requests.get(self.base_url + "/v1/models",
                             headers=self._headers(), timeout=15)
            if r.status_code == 401:
                return False, "the saved API key was rejected (401)."
            r.raise_for_status()
            return True, "API key accepted; generating with " + self.model
        except Exception as e:                     # noqa: BLE001 - report, don't crash
            return False, "could not reach the OpenAI API ({}).".format(e)

    def list_models(self):
        """Ask the account which image models it can actually use.

        Deliberately NOT a hardcoded list: OpenAI ships new image models on its
        own schedule, so anything baked in here goes stale. We query /v1/models
        and keep the image-generation ones, falling back to the known names only
        if the call fails. A model typed by hand is always allowed through —
        `generate` does not reject unknown names.
        """
        if self.dry_run:
            return list(self.DRY_MODELS)
        if not self.api_key:
            return list(self.MODELS)
        try:
            r = requests.get(self.base_url + "/v1/models",
                             headers=self._headers(), timeout=15)
            r.raise_for_status()
            ids = sorted(m.get("id", "") for m in r.json().get("data", []))
            found = [m for m in ids if self._is_image_model(m)]
            return found or list(self.MODELS)
        except Exception:                          # noqa: BLE001 - fall back quietly
            return list(self.MODELS)

    @staticmethod
    def _is_image_model(mid):
        """Name-shaped test for an image generator, so models released after
        this code was written are still picked up."""
        m = (mid or "").lower()
        if "image" in m and not m.startswith("text-"):
            return True
        return m.startswith("dall-e")
