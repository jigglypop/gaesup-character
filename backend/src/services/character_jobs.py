"""Persisted Meshy jobs shared by CLI and HTTP. Callers hold the run lock."""

import base64
import io
import json
from src.services.object_storage import StoredPath as Path
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


def generate(directory: Path, image: Path, height: float, client: httpx.Client, profile: str = "meshy-7", *, isolated_part: bool = False, body_type: str = "humanoid") -> dict:
    if (directory / "character.json").exists():
        raise ValueError("Existing run: refresh or recover; never resubmit an uncertain task")
    if not 0.1 <= height <= 100:
        raise ValueError("Invalid height")
    if body_type not in {"humanoid", "quadruped"}:
        raise ValueError("Unknown body type")
    image = image.resolve()
    if image.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("Image must be PNG or JPEG")
    with Image.open(io.BytesIO(image.read_bytes())) as reference:
        reference.verify()
    if profile not in {"meshy-7", "smart-topology"}:
        raise ValueError("Unknown generation profile")
    value = {"image": str(image), "image_sha256": _digest(image), "height_meters": height, "profile": profile,
             "stage": "generation", "status": "submission_uncertain", "body_type": body_type}
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
    if body_type == "quadruped":
        payload.pop("pose_mode", None)
    value["generation_settings"] = {k: v for k, v in payload.items() if k != "image_url"}
    return _submit(directory, value, "/openapi/v1/image-to-3d", payload, client)


def rig(directory: Path, client: httpx.Client) -> dict:
    value = state(directory)
    if value.get("body_type", "humanoid") != "humanoid":
        raise ValueError("Quadruped rigging requires the Meshy web app; the public Rigging API supports humanoids only")
    if value["stage"] != "generation" or value["status"] != "SUCCEEDED":
        raise ValueError("A successful generation is required before rigging")
    task_id = value.pop("task_id")
    value.update(generation_task_id=task_id, stage="rigging", status="submission_uncertain")
    return _submit(directory, value, "/openapi/v1/rigging",
                   {"input_task_id": task_id, "height_meters": value["height_meters"]}, client)


def generate_multiview_part(directory: Path, images: list[Path], client: httpx.Client, *, isolated_part=True, height=1.2) -> dict:
    """One fixed Meshy 7 submission; caller validates object/view lineage."""
    if (directory/'character.json').exists():
        raise ValueError('Existing run: recover or refresh, never resubmit')
    if not 1 <= len(images) <= 4:
        raise ValueError('One to four views of the same object are required')
    urls, sources = [], []
    for image in images:
        with Image.open(io.BytesIO(image.read_bytes())) as reference:
            if reference.format != 'PNG':
                raise ValueError('Prepared PNG required')
            reference.verify()
        sources.append({'image_sha256': _digest(image)})
        urls.append('data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode('ascii'))
    payload = {'image_urls': urls, 'ai_model': 'meshy-7', 'should_texture': True, 'enable_pbr': True,
               'should_remesh': True, 'target_polycount': 10000, 'image_enhancement': False, 'target_formats': ['glb']}
    if not isolated_part:
        payload.update(target_polycount=30000, pose_mode='a-pose')
    endpoint = '/openapi/v1/multi-image-to-3d'
    value = {'stage': 'generation', 'status': 'submission_uncertain', 'profile': 'meshy-7',
             'generation_endpoint': endpoint, 'sources': sources, 'isolated_part': isolated_part,
             'height_meters': height, 'body_type': 'humanoid',
             'generation_settings': {k: v for k, v in payload.items() if k != 'image_urls'}}
    return _submit(directory, value, endpoint, payload, client)


def rig_model(directory: Path, model: Path, height: float, client: httpx.Client, *, body_type: str = "humanoid") -> dict:
    """Rig an existing textured assembly without regenerating its source parts.

    Callers hold run_lock. A lost POST leaves its durable intent for task-ID
    recovery, exactly like image generation. The input GLB is never overwritten.
    """
    from src.services.asset_delivery import inspect_glb
    from src.services.glb import parse_glb
    import hashlib

    if body_type != "humanoid":
        raise ValueError("Quadruped rigging requires the Meshy web app; the public Rigging API supports humanoids only")
    if (directory / "character.json").exists() or (directory / "rig-input.glb").exists():
        raise ValueError("Existing run: refresh or recover; never resubmit an uncertain task")
    if not 0.1 <= height <= 100:
        raise ValueError("Invalid height")
    content = model.read_bytes()
    quality = inspect_glb(content, budget_warnings=True)
    doc, _ = parse_glb(content, strict=True)
    if quality["errors"] or not doc.get("textures") or not doc.get("images"):
        raise ValueError("Meshy rigging requires a valid textured humanoid GLB")
    source_hash = hashlib.sha256(content).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "rig-input.glb").open("xb") as target:
        target.write(content)
    value = {"stage": "rigging", "status": "submission_uncertain", "body_type": body_type,
             "height_meters": height, "source_sha256": source_hash, "input_kind": "model",
             "source_model": str(model.resolve()), "provider": "meshy"}
    return _submit(directory, value, "/openapi/v1/rigging", {
        "model_url": "data:model/gltf-binary;base64," + base64.b64encode(content).decode("ascii"),
        "height_meters": height,
    }, client)


def refresh(directory: Path, client: httpx.Client, task_id: str | None = None) -> dict:
    value = state(directory)
    task_id = task_id or value.get("task_id", "")
    if not isinstance(task_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", task_id):
        raise ValueError("Recover the existing Meshy task ID first")
    endpoint = value.get('generation_endpoint', '/openapi/v1/image-to-3d') if value["stage"] == "generation" else "/openapi/v1/rigging"
    if endpoint not in ('/openapi/v1/image-to-3d', '/openapi/v1/multi-image-to-3d', '/openapi/v1/rigging'):
        raise ValueError('Unknown provider endpoint')
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
