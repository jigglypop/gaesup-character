"""Bounded action workers. No client-provided code, commands, or paths."""

import json
import logging
import os

import httpx

from src.services import character_jobs
from src.services.asset_delivery import inspect_glb
from src.services.asset_editor import _write_json
from src.services.glb import parse_glb
from src.services.character_pipeline import CharacterPipeline, PipelineError, now, read_json
from src.services.wardrobe import _digest

logger = logging.getLogger(__name__)


def inspect_model(path) -> dict:
    content = path.read_bytes()
    quality = inspect_glb(content)
    doc, _ = parse_glb(content, strict=True)
    nodes = [{"index": index, "name": node.get("name", f"Mesh {index}"),
              "skinned": "skin" in node}
             for index, node in enumerate(doc.get("nodes", [])) if "mesh" in node]
    return {"model_sha256": _digest(path), "checked_at": now(),
            "errors": quality["errors"], "metrics": quality["metrics"], "nodes": nodes,
            "material_boundaries": any(len({p.get("material") for p in mesh.get("primitives", [])}) > 1
                                       for mesh in doc.get("meshes", []))}


def perform(pipeline: CharacterPipeline, entry, run, control, operation):
    action = operation["action_id"]
    payload = operation["payload"]
    files = pipeline.files(entry, run, control)
    model_id, model = pipeline.model(files)
    if operation["input_sha256"] and (not model or _digest(model) != operation["input_sha256"]):
        raise PipelineError("input_changed", "작업 수락 이후 모델이 변경되었습니다.")
    if action == "submit_generation" and (not files.get("reference") or _digest(files["reference"]) != operation.get("image_sha256")):
        raise PipelineError("input_changed", "작업 수락 이후 입력 이미지가 변경되었습니다.")
    if action in {"refresh_provider", "recover_task", "submit_generation", "submit_rigging"}:
        key = os.getenv("MESHY_API_KEY")
        if not key:
            raise PipelineError("provider_unconfigured", "서버의 Meshy API 설정이 필요합니다.")
        with httpx.Client(base_url=os.getenv("MESHY_API_BASE_URL", "https://api.meshy.ai"),
                          headers={"Authorization": f"Bearer {key}"}, timeout=120) as client:
            if action in {"refresh_provider", "recover_task"}:
                character_jobs.refresh(run, client, payload.get("task_id"))
            elif action == "submit_generation":
                character_jobs.generate(run, files["reference"], control.get("height_meters", entry.get("height_meters")), client)
            else:
                character_jobs.rig(run, client)
    elif action.startswith("download_"):
        character_jobs.download(run, action.removeprefix("download_"))
    elif action == "inspect_model":
        control["inspection"] = inspect_model(model)
    elif action == "separate_materials":
        from src.services.character_parts import separate_materials
        output = run / "operations" / operation["id"] / "blender"
        try:
            separate_materials(model, output)
        except ValueError as exc:
            raise PipelineError("separation_failed", "재질 분리를 완료하지 못했습니다. 원본은 보존되며 영역별 Blender 편집이 필요할 수 있습니다.") from exc
        control.update(parts_model=str((output / "character.glb").relative_to(pipeline.root)),
                       parts_blend=str((output / "source.blend").relative_to(pipeline.root)),
                       rest_render=str((output / "rest.png").relative_to(pipeline.root)),
                       rig_origin=pipeline.detail(entry["id"], operation["user_id"])["rig_origin"],
                       inspection=inspect_model(output / "character.glb"), parts=[], review={}, body_coverage="unknown")
    elif action == "organize_parts":
        inspection = inspect_model(model)
        known = {node["index"] for node in inspection["nodes"]}
        parts = payload["parts"]
        selected = [part["node_index"] for part in parts]
        if set(selected) != known or len(selected) != len(set(selected)):
            raise PipelineError("invalid_parts", "모든 메시를 중복 없이 하나의 역할에 배정해 주세요.", 400)
        if not {"body", "outfit_base"}.issubset({part["role"] for part in parts}):
            raise PipelineError("missing_parts", "몸과 원래 의상을 각각 지정해 주세요.", 400)
        names = {node["index"]: node["name"] for node in inspection["nodes"]}
        control.update(parts=[{**part, "name": names[part["node_index"]]} for part in parts],
                       parts_sha256=_digest(model), body_coverage=payload["body_coverage"], review={})
        # Receipt is immutable; active metadata points to the same unchanged GLB.
        _write_json(run / "operations" / operation["id"] / "parts.json",
                    {"model_sha256": _digest(model), "parts": control["parts"],
                     "body_coverage": control["body_coverage"], "status": "review_required"})
    elif action == "record_review":
        inspection = inspect_model(model)
        if inspection["errors"]:
            raise PipelineError("technical_failure", "구조 검사의 오류를 해결한 뒤 검수해 주세요.")
        if payload["decision"] == "approved":
            roles = {part["role"] for part in control.get("parts", [])}
            if control.get("parts_sha256") != _digest(model) or not {"body", "outfit_base"}.issubset(roles):
                raise PipelineError("parts_required", "현재 모델의 몸·의상 파츠 역할을 먼저 기록해 주세요.")
            if not payload["motion_checked"] or not payload["appearance_checked"]:
                raise PipelineError("review_required", "외형과 대상 동작을 확인한 뒤 승인해 주세요.")
            if control.get("body_coverage", "unknown") == "unknown":
                raise PipelineError("coverage_required", "몸의 coverage를 확인해 주세요.")
        control["review"] = {**payload, "model_sha256": _digest(model), "reviewed_at": now(),
                             "reviewer_id": operation["user_id"]}
        _write_json(run / "operations" / operation["id"] / "review.json", control["review"])
    else:
        raise PipelineError("unknown_action", "지원하지 않는 작업입니다.", 400)
    _write_json(run / "control.json", control)


def execute(pipeline: CharacterPipeline, character_id: str, user_id: int, operation_id: str):
    _, run, _ = pipeline.entry(character_id, user_id)
    path = run / "operations" / operation_id / "operation.json"
    operation = read_json(path)
    if operation.get("status") != "accepted" or operation.get("executor") != pipeline.instance:
        return
    try:
        with pipeline.lock(run):
            entry, _, control = pipeline.entry(character_id, user_id)
            operation.update(status="running", updated_at=now(), user_id=user_id)
            _write_json(path, operation)
            perform(pipeline, entry, run, control, operation)
            operation.update(status="succeeded", updated_at=now())
            _write_json(path, operation)
    except Exception as exc:
        code, message = "action_failed", "작업을 완료하지 못했습니다. 상태를 확인한 뒤 다시 진행해 주세요."
        if isinstance(exc, PipelineError):
            code, message = exc.code, exc.message
        elif isinstance(exc, httpx.HTTPStatusError):
            code, message = "provider_error", f"Meshy HTTP {exc.response.status_code}. 기존 작업 상태를 확인해 주세요."
        elif isinstance(exc, httpx.RequestError):
            code, message = "provider_connection", "Meshy 응답을 확인하지 못했습니다. 기존 작업 상태부터 복구해 주세요."
        else:
            logger.exception("Character action failed: %s", operation["action_id"])
        provider = read_json(run / "character.json")
        status = "recovery_required" if provider.get("status") == "submission_uncertain" else "failed"
        operation.update(status=status, updated_at=now(), error={"code": code, "message": message})
        _write_json(path, operation)
