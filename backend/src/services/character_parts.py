"""Run a fixed material-boundary recipe in an isolated Blender process."""

import os
from pathlib import Path
import shutil
import subprocess

from src.services.asset_delivery import DeliveryPolicy, inspect_glb
from src.services.asset_editor import _write_json
from src.services.wardrobe import _digest


def blender_executable() -> str | None:
    configured = os.getenv("BLENDER_EXECUTABLE")
    if configured:
        return configured if Path(configured).is_file() else None
    found = shutil.which("blender")
    if found:
        return found
    if os.name == "nt":
        candidates = sorted(Path(os.environ.get("ProgramFiles", "C:/Program Files")).glob("Blender Foundation/Blender */blender.exe"))
        return str(candidates[-1]) if candidates else None
    return None


def separate_materials(model: Path, output: Path, selections: list[dict] | None = None, source_sha256: str | None = None) -> dict:
    executable = blender_executable()
    if not executable:
        raise ValueError("Blender executable is unavailable")
    source = inspect_glb(model.read_bytes())
    if source["errors"] or not source["metrics"]["skins"]:
        raise ValueError("A valid rigged source is required")
    output.mkdir(parents=True, exist_ok=False)
    worker_model = model
    if selections is not None:
        from src.services.character_segmentation import split_faces
        content, parts = split_faces(model.read_bytes(), source_sha256, selections)
        worker_model = output / "selected.glb"
        worker_model.write_bytes(content)
        _write_json(output / "selection.json", {"source_sha256": source_sha256, "selections": selections, "parts": parts})
    _write_json(output / "input.json", {"model": str(worker_model.resolve()), "output": str(output.resolve()),
                                      "source_sha256": _digest(worker_model), "review_only": selections is not None})
    command = [executable, "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
               "--python", str(Path(__file__).with_name("character_parts_blender.py")), "--", str(output / "input.json")]
    with (output / "blender.log").open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        _write_json(output / "runner.json", {"pid": process.pid, "source_sha256": _digest(model)})
        try:
            code = process.wait(timeout=240)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise ValueError("Blender timed out; isolated worker was stopped")
    if code:
        raise ValueError("Blender separation failed; original model is preserved")
    if selections is not None:
        # The GLB retains exact source buffers; Blender produces the editable .blend and render.
        shutil.copyfile(worker_model, output / "character.glb")
    policy = DeliveryPolicy(required_joints=source["metrics"]["joints"],
                            required_animations=source["metrics"]["animations"])
    quality = inspect_glb((output / "character.glb").read_bytes(), policy)
    _write_json(output / "quality.json", quality)
    if quality["errors"]:
        raise ValueError("Separated model failed validation; original model is preserved")
    result = {"source_sha256": _digest(model), "model_sha256": _digest(output / "character.glb"),
              "recipe": "authored-faces-v1" if selections is not None else "material-boundaries-v1", "status": "review_required"}
    _write_json(output / "complete.json", result)
    return result
