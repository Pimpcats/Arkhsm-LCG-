"""AUTOMATIC1111 adapter (also Forge/reForge, which speak the same API).

Endpoint (verify against your installed version; payload per the public
sdapi docs): POST {base}/sdapi/v1/txt2img
    {prompt, negative_prompt, steps, sampler_name, cfg_scale, width, height,
     seed, n_iter, override_settings: {sd_model_checkpoint}}
Images return base64-encoded in r["images"]. LoRA rides IN the prompt as
<lora:name:weight> (composition already put it there). Start the UI with --api.

Character reference images without a LoRA are NOT applied on this path in v1
(noted in the report); use the Comfy path + an IPAdapter workflow for that.
"""
import base64
import json

import requests

from .base import Backend, STUB_PNG


class A1111Backend(Backend):
    name = "a1111"
    DEFAULT_URL = "http://127.0.0.1:7860"

    def generate(self, positive, negative, params, job_key):
        payload = {
            "prompt": positive,
            "negative_prompt": negative,
            "steps": params["steps"],
            "sampler_name": params["sampler"],
            "cfg_scale": params["cfg"],
            "width": params["width"],
            "height": params["height"],
            "seed": params["seed"],
            "n_iter": 1,
            "override_settings": {"sd_model_checkpoint": params["checkpoint"]},
        }
        if self.dry_run:
            self._write_payload(job_key, payload)
            return [STUB_PNG]
        r = requests.post(self.base_url + "/sdapi/v1/txt2img",
                          json=payload, timeout=self.timeout)
        r.raise_for_status()
        return [base64.b64decode(b64.split(",", 1)[-1]) for b64 in r.json()["images"]]

    def check(self):
        if self.dry_run:
            return True, "dry-run (no backend contacted)"
        try:
            r = requests.get(self.base_url + "/sdapi/v1/sd-models", timeout=10)
            r.raise_for_status()
            models = [m.get("model_name", "?") for m in r.json()]
            return True, "reachable; {} model(s): {}".format(len(models), ", ".join(models[:5]))
        except Exception as e:  # noqa: BLE001 - report, don't crash the CLI
            return False, "unreachable at {} ({}). Start A1111 with --api.".format(self.base_url, e)

    def inpaint(self, image_png, mask_png, positive, negative, params, job_key):
        """img2img inpainting: regenerate ONLY the white mask regions of
        image_png. Payload per the public sdapi docs (POST /sdapi/v1/img2img);
        inpainting_fill=1 keeps the original pixels as the starting point so
        the result blends with the surrounding frame texture."""
        payload = {
            "init_images": [base64.b64encode(image_png).decode()],
            "mask": base64.b64encode(mask_png).decode(),
            "prompt": positive,
            "negative_prompt": negative,
            "denoising_strength": params.get("denoise", 0.75),
            "mask_blur": params.get("mask_blur", 8),
            "inpainting_fill": 1,
            "inpaint_full_res": False,
            "inpainting_mask_invert": 0,
            "steps": params.get("steps", 34),
            "sampler_name": params.get("sampler", "DPM++ 2M Karras"),
            "cfg_scale": params.get("cfg", 6.0),
            "width": params["width"],
            "height": params["height"],
            "seed": params.get("seed", 11),
            "n_iter": 1,
            "override_settings": {"sd_model_checkpoint": params["checkpoint"]},
        }
        if self.dry_run:
            slim = dict(payload,
                        init_images=["<{} bytes>".format(len(image_png))],
                        mask="<{} bytes>".format(len(mask_png)))
            self._write_payload(job_key, slim)
            return [STUB_PNG]
        r = requests.post(self.base_url + "/sdapi/v1/img2img",
                          json=payload, timeout=self.timeout)
        r.raise_for_status()
        return [base64.b64decode(b64.split(",", 1)[-1]) for b64 in r.json()["images"]]

    def list_models(self):
        if self.dry_run:
            return list(self.DRY_MODELS)
        r = requests.get(self.base_url + "/sdapi/v1/sd-models", timeout=15)
        r.raise_for_status()
        # 'title' ("file.safetensors [hash]") is what override_settings matches
        # most precisely; A1111 also accepts the bare filename.
        return [m.get("title") or m.get("model_name", "?") for m in r.json()]

    def current_model(self):
        """The checkpoint the backend has LOADED right now (ground truth for
        'is Painter's actually selected?')."""
        if self.dry_run:
            return self.DRY_MODELS[0]
        r = requests.get(self.base_url + "/sdapi/v1/options", timeout=15)
        r.raise_for_status()
        return r.json().get("sd_model_checkpoint")
