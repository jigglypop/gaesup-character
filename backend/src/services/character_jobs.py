"""Persisted Meshy jobs shared by CLI and HTTP. Callers hold the run lock."""

import base64
import json
from pathlib import Path
import re

import httpx
from PIL import Image

from src.services.asset_editor import _write_json
from src.services.wardrobe import _digest, download_glb


def state(directory: Path) -> dict:
    return json.loads((directory / "character.json").read_text(encoding="utf-8"))


def _submit(directory: Path, value: dict, endpoint: str, payload: dict, client: httpx.Client) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(directory / "character.json", value)
    response = client.post(endpoint, json=payload)
    if response.status_code in {400, 401, 402, 403, 404, 422, 429}:
        value.update(status="submission_rejected", http_status=response.status_code)
        _write_json(directory / "character.json", value)
    response.raise_for_status()
    task_id = response.json().get("result")
    if not isinstance(task_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", task_id):
        raise ValueError("Invalid task ID; recover existing submission before retrying")
    value.update(task_id=task_id, status="PENDING")
    _write_json(directory / "character.json", value)
    return value


def generate(directory: Path, image: Path, height: float, client: httpx.Client, profile: str = "meshy-7", *, isolated_part: bool = False) -> dict:
    if (directory / "character.json").exists():
        raise ValueError("Existing run: refresh or recover; never resubmit an uncertain task")
    if not 0.1 <= height <= 100:
        raise ValueError("Invalid height")
    image = image.resolve()
    if image.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("Image must be PNG or JPEG")
    with Image.open(image) as reference:
        reference.verify()
    if profile not in {"meshy-7", "smart-topology"}:
        raise ValueError("Unknown generation profile")
    value = {"image": str(image), "image_sha256": _digest(image), "height_meters": height, "profile": profile,
             "stage": "generation", "status": "submission_uncertain"}
    mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
    payload = {"image_url": f"data:{mime};base64," + base64.b64encode(image.read_bytes()).decode(),
               "ai_model": "meshy-7", "model_type": "standard", "should_texture": True, "enable_pbr": True,
               "should_remesh": True, "target_polycount": 30000, "pose_mode": "a-pose",
               "image_enhancement": False, "target_formats": ["glb"]}
    if profile == "smart-topology":
        payload.update(model_type="smart-topology", ai_model="meshy-t2", target_polycount=15000)
        payload.pop("should_remesh")
        payload.pop("image_enhancement")  # Documented only for Meshy 6/7; do not send unsupported controls.
    if isolated_part:
        payload.pop('pose_mode', None)  # A hat or shoe is not a humanoid to pose/auto-rig.
        payload['target_polycount'] = 10000  # Seven pieces plus the shared body stay within the assembly triangle budget.
    value["generation_settings"] = {k: v for k, v in payload.items() if k != "image_url"}
    return _submit(directory, value, "/openapi/v1/image-to-3d", payload, client)


def rig(directory: Path, client: httpx.Client) -> dict:
    value = state(directory)
    if value["stage"] != "generation" or value["status"] != "SUCCEEDED":
        raise ValueError("A successful generation is required before rigging")
    task_id = value.pop("task_id")
    value.update(generation_task_id=task_id, stage="rigging", status="submission_uncertain")
    return _submit(directory, value, "/openapi/v1/rigging",
                   {"input_task_id": task_id, "height_meters": value["height_meters"]}, client)


def refresh(directory: Path, client: httpx.Client, task_id: str | None = None) -> dict:
    value = state(directory)
    task_id = task_id or value.get("task_id", "")
    if not isinstance(task_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", task_id):
        raise ValueError("Recover the existing Meshy task ID first")
    endpoint = "/openapi/v1/image-to-3d" if value["stage"] == "generation" else "/openapi/v1/rigging"
    response = client.get(f"{endpoint}/{task_id}")
    response.raise_for_status()
    task = response.json()
    _write_json(directory / (value["stage"] + "-result.json"), task)
    value.update(task_id=task_id, status=task["status"], progress=task.get("progress"))
    _write_json(directory / "character.json", value)
    return value


def download(directory: Path, stage: str, download_model=download_glb) -> dict:
    task = json.loads((directory / (stage + "-result.json")).read_text(encoding="utf-8"))
    if task.get("status") != "SUCCEEDED":
        raise ValueError("Download requires a successful task; refresh status first")
    if stage == "generation":
        urls = {"generated": task.get("model_urls", {}).get("glb")}
    else:
        result = task.get("result") or {}
        urls = {"rigged": result.get("rigged_character_glb_url")}
        for name in ("walking", "running"):
            url = (result.get("basic_animations") or {}).get(name + "_glb_url")
            if url:
                urls[name] = url
    if not next(iter(urls.values())):
        raise ValueError("Task succeeded without a GLB URL")
    artifacts = {}
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        for name, url in urls.items():
            output = directory / (name + ".glb")
            quality = download_model(client, url, output)
            _write_json(directory / (name + "-quality.json"), quality)
            artifacts[name] = {"path": str(output.resolve()), "sha256": _digest(output)}
    _write_json(directory / (stage + "-artifacts.json"), artifacts)
    return artifacts
