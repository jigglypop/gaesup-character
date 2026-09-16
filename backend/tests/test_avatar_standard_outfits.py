import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.avatar_standard import get_standard, router
from src.api.characters import pipeline_error_handler
from src.auth import UserContext, get_current_user
from src.services.asset_editor import _write_json
from src.services.avatar_standard import AvatarStandard
from src.services.avatar_standard_outfits import AvatarStandardOutfits
from src.services.character_pipeline import PipelineError


def digest(content):
    return hashlib.sha256(content).hexdigest()


def record(service, owner, item_id, value, artifacts):
    directory = service.directory(owner, item_id)
    directory.mkdir(parents=True)
    files = {}
    for name, content in artifacts.items():
        (directory / name).write_bytes(content)
        files[name] = digest(content)
    _write_json(directory / 'record.json', {**value, 'id': item_id, 'files': files})
    return service.raw(owner, item_id)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.delenv('MESHY_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    service = AvatarStandard(tmp_path)
    base_id = 'a' * 24
    base_bytes = b'approved-base'
    base = record(service, 1, base_id, {
        'kind': 'base', 'status': 'approved', 'model_sha256': digest(base_bytes),
    }, {'model.glb': base_bytes})
    part_ids = ['b' * 24, 'c' * 24]
    for part_id, slot in zip(part_ids, ('top', 'bottom')):
        part_bytes = f'part-{slot}'.encode()
        record(service, 1, part_id, {
            'kind': 'part', 'status': 'review_required',
            'contract': {'base_id': base_id, 'base_sha256': base['model_sha256'], 'slot': slot},
        }, {'part.glb': part_bytes})
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.add_exception_handler(PipelineError, pipeline_error_handler)
    app.dependency_overrides[get_standard] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: UserContext(1, 'tester', [])
    with TestClient(app) as client:
        yield client, service, app, base, part_ids


def test_empty_save_persistence_owner_scope_and_artifact_hash(setup):
    client, service, app, base, part_ids = setup
    url = f"/api/avatar-standard/outfits/{base['id']}"
    assert client.get(url).json() == {
        'base_id': base['id'], 'base_sha256': base['model_sha256'], 'revision': '0', 'part_ids': [],
    }
    response = client.put(url, json={'base_sha256': base['model_sha256'], 'part_ids': part_ids}, headers={
        'If-Match': '0', 'Idempotency-Key': 'outfit-save-001',
    })
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['part_ids'] == part_ids and saved['saved_at']
    assert AvatarStandardOutfits(AvatarStandard(service.root.parent)).get(1, base['id']) == saved
    part = service.public(1, part_ids[0])
    assert part['artifacts'][0]['sha256'] == service.raw(1, part_ids[0])['files']['part.glb']
    assert 'C:' not in json.dumps(saved)
    app.dependency_overrides[get_current_user] = lambda: UserContext(2, 'other', [])
    assert client.get(url).status_code == 404


def test_idempotent_replay_precedes_revision_and_changed_payload_conflicts(setup):
    client, _, _, base, part_ids = setup
    url = f"/api/avatar-standard/outfits/{base['id']}"
    body = {'base_sha256': base['model_sha256'], 'part_ids': part_ids}
    headers = {'If-Match': '0', 'Idempotency-Key': 'outfit-save-002'}
    saved = client.put(url, json=body, headers=headers).json()
    replay = client.put(url, json=body, headers={**headers, 'If-Match': 'stale'})
    assert replay.status_code == 200 and replay.json() == saved
    changed = client.put(url, json={**body, 'part_ids': part_ids[:1]}, headers=headers)
    assert changed.status_code == 409 and changed.json()['error']['code'] == 'idempotency_conflict'


def test_revision_conflict_is_serialized_without_lost_update(setup):
    _, service, _, base, part_ids = setup
    outfits = AvatarStandardOutfits(service)
    payloads = [
        {'base_sha256': base['model_sha256'], 'part_ids': [part_ids[0]]},
        {'base_sha256': base['model_sha256'], 'part_ids': [part_ids[1]]},
    ]

    def save(index):
        try:
            return outfits.put(1, base['id'], payloads[index], '0', f'concurrent-{index:03d}')
        except PipelineError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, (0, 1)))
    assert sum(isinstance(value, dict) for value in results) == 1
    assert results.count('revision_conflict') == 1
    assert outfits.get(1, base['id']) in [value for value in results if isinstance(value, dict)]


def test_parts_must_match_base_slot_status_and_unchanged_artifact(setup):
    client, service, _, base, part_ids = setup
    url = f"/api/avatar-standard/outfits/{base['id']}"
    headers = {'If-Match': '0', 'Idempotency-Key': 'outfit-invalid-001'}
    duplicate_slot = service.raw(1, part_ids[1])
    duplicate_slot['contract']['slot'] = 'top'
    _write_json(service.directory(1, part_ids[1]) / 'record.json', duplicate_slot)
    response = client.put(url, json={'base_sha256': base['model_sha256'], 'part_ids': part_ids}, headers=headers)
    assert response.status_code == 422 and response.json()['error']['code'] == 'slot_conflict'

    duplicate_slot['contract']['slot'] = 'bottom'
    _write_json(service.directory(1, part_ids[1]) / 'record.json', duplicate_slot)
    (service.directory(1, part_ids[0]) / 'part.glb').write_bytes(b'changed')
    response = client.put(url, json={'base_sha256': base['model_sha256'], 'part_ids': [part_ids[0]]}, headers={
        'If-Match': '0', 'Idempotency-Key': 'outfit-invalid-002',
    })
    assert response.status_code == 409 and response.json()['error']['code'] == 'artifact_changed'


def test_headers_and_request_limits_are_enforced(setup):
    client, _, _, base, part_ids = setup
    url = f"/api/avatar-standard/outfits/{base['id']}"
    body = {'base_sha256': base['model_sha256'], 'part_ids': part_ids}
    assert client.put(url, json=body).status_code == 422
    assert client.put(url, json={**body, 'part_ids': ['d' * 24] * 13}, headers={
        'If-Match': '0', 'Idempotency-Key': 'outfit-limits-001',
    }).status_code == 422
