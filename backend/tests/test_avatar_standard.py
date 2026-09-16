import io
import json

import pytest
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from src.api.avatar_standard import router, get_standard
from src.api.characters import pipeline_error_handler
from src.auth import UserContext, get_current_user
from src.services.avatar_standard import AvatarStandard, sha
from src.services.avatar_standard_models import BaseInput, PartInput, ImageInput, ReviewInput, ShapeInput
from src.services import avatar_standard_provider as provider
from src.services import avatar_standard_design as design
from src.services.avatar_standard_models import DesignInput, AlignDesignInput
from PIL import ImageDraw
import base64
from src.services.asset_editor import _write_json
from src.services.character_pipeline import PipelineError
from api.test_characters import rigged_glb


@pytest.fixture
def setup(tmp_path, monkeypatch):
    service = AvatarStandard(tmp_path)
    monkeypatch.setattr('src.services.avatar_standard.blender_executable', lambda: 'fixture-blender')
    monkeypatch.setattr(service, 'execute', lambda *args: None)
    app = FastAPI(); app.include_router(router, prefix='/api')
    app.add_exception_handler(PipelineError, pipeline_error_handler)
    app.dependency_overrides[get_standard] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: UserContext(1, 'tester', [])
    with TestClient(app) as client:
        yield client, service, app


def source(service):
    character = service.characters.create('Test body', 1.2, 1)
    return service.characters.upload(character['id'], 1, rigged_glb(), 'model', character['revision'])


def accepted_base(client, service):
    char = source(service)
    payload = BaseInput(character_id=char['id'], source_sha256=char['model_sha256'], name='Base').model_dump()
    response = client.post('/api/avatar-standard/bases', json=payload, headers={'Idempotency-Key': 'base-test-123'})
    assert response.status_code == 202, response.text
    return response.json(), payload


def prepared_base(client, service):
    base, _ = accepted_base(client, service)
    path = service.directory(1, base['id']); (path/'model.glb').write_bytes(rigged_glb())
    value = service.raw(1, base['id'])
    value.update(status='review_required', files={'model.glb': sha(path/'model.glb')}, model_sha256=sha(path/'model.glb'),
                 result={'bones': ['root'], 'height_m': 1.2})
    _write_json(path/'record.json', value)
    return value


def approve(service, base):
    return service.review(1, base['id'], ReviewInput(model_sha256=base['model_sha256'], decision='approved',
        bald_complete_body=True, neutral_apose=True, motion_checked=True, notes='Test-only review fixture').model_dump())


def test_acceptance_idempotency_owner_and_source(setup):
    client, service, app = setup
    base, payload = accepted_base(client, service)
    response = client.post('/api/avatar-standard/bases', json=payload, headers={'Idempotency-Key': 'base-test-123'})
    assert response.status_code == 202 and response.json()['id'] == base['id']
    payload['name'] = 'Changed'
    assert client.post('/api/avatar-standard/bases', json=payload, headers={'Idempotency-Key': 'base-test-123'}).status_code == 409
    assert 'C:' not in json.dumps(base) and 'process' not in base
    assert client.get(f"/api/avatar-standard/items/{base['id']}/artifacts/input.json").status_code == 404
    app.dependency_overrides[get_current_user] = lambda: UserContext(2, 'other', [])
    assert client.get('/api/avatar-standard/items').json() == {'items': []}
    assert client.get(f"/api/avatar-standard/items/{base['id']}").status_code == 404


def test_review_requires_version_and_all_checks(setup):
    client, service, _ = setup
    base = prepared_base(client, service)
    payload = ReviewInput(model_sha256=base['model_sha256'], decision='approved', notes='Not all checks performed').model_dump()
    assert client.post(f"/api/avatar-standard/items/{base['id']}/review", json=payload).status_code == 422
    payload.update(bald_complete_body=True, neutral_apose=True, motion_checked=True, model_sha256='0'*64)
    assert client.post(f"/api/avatar-standard/items/{base['id']}/review", json=payload).status_code == 409
    approved = approve(service, base)
    assert approved['status'] == 'approved'
    (service.directory(1, base['id'])/'model.glb').write_bytes(b'changed')
    with pytest.raises(PipelineError, match='해시'):
        service.base(1, base['id'], base['model_sha256'])


def test_image_coordinates_and_original_survive_crop(setup):
    client, service, _ = setup
    base = approve(service, prepared_base(client, service))
    stream = io.BytesIO(); Image.new('RGBA', (2048, 2048), 'red').save(stream, format='PNG')
    asset = service.upload(1, stream.getvalue(), 'png')
    payload = ImageInput(base_id=base['id'], base_sha256=base['model_sha256'], image_asset=asset['id'], object_key='cardigan',
                         view='front', crop=[400, 600, 800, 400]).model_dump()
    result = service.image(1, payload)
    assert result['result']['crop_scale'] == 1.28
    assert result['result']['export_offset_px'] == [0, 256]
    assert result['result']['target_crop_size_m'] == [.64, .32]
    assert service.artifact(1, result['id'], 'canvas.png').read_bytes() == stream.getvalue()
    assert service.image(1, payload)['id'] == result['id']
    with Image.open(service.artifact(1, result['id'], 'provider.png')) as image:
        assert image.size == (1024, 1024) and image.getchannel('A').getbbox() == (0, 256, 1024, 768)
    stream = io.BytesIO(); Image.new('RGBA', (1024, 1024), 'red').save(stream, format='PNG')
    payload['image_asset'] = service.upload(1, stream.getvalue(), 'png')['id']
    with pytest.raises(PipelineError, match='2048'):
        service.image(1, payload)
    with pytest.raises(ValidationError):
        ImageInput(**{**payload, 'crop': [2000, 0, 200, 500]})


def test_binding_contract_and_unapproved_base(setup):
    client, service, _ = setup
    base = prepared_base(client, service)
    asset = service.upload(1, rigged_glb(), 'glb')
    payload = dict(name='pants', base_id=base['id'], base_sha256=base['model_sha256'], model_asset=asset['id'],
        slot='bottom', garment_type='pants', binding='transfer', anchors=[{'name': str(i), 'source': p, 'target': p} for i, p in enumerate([[0,0,0], [1,0,0], [0,1,0]])])
    with pytest.raises(ValidationError):
        PartInput(**{**payload, 'binding': 'rigid', 'bone': 'root'})
    with pytest.raises(ValidationError):
        PartInput(**{**payload, 'slot': 'hat'})
    response = client.post('/api/avatar-standard/parts', json=payload, headers={'Idempotency-Key': 'part-test-123'})
    assert response.status_code == 409
    approve(service, base)
    payload.update(slot='hat', garment_type='hat', binding='rigid', bone='missing')
    assert client.post('/api/avatar-standard/parts', json=payload, headers={'Idempotency-Key': 'part-test-123'}).status_code == 422


def test_recovery_does_not_restart_uncertain_worker(setup, monkeypatch):
    client, service, _ = setup
    base, _ = accepted_base(client, service)
    assert client.post(f"/api/avatar-standard/items/{base['id']}/recover").status_code == 409
    monkeypatch.setattr('src.services.avatar_standard.process_state', lambda value: 'unknown')
    assert client.post(f"/api/avatar-standard/items/{base['id']}/recover").status_code == 409
    monkeypatch.setattr('src.services.avatar_standard.process_state', lambda value: 'exited')
    response = client.post(f"/api/avatar-standard/items/{base['id']}/recover")
    assert response.status_code == 200 and response.json()['status'] == 'failed'
    assert service.public(1, base['id'])['status'] == 'failed'


def shape_input(client, service):
    base = approve(service, prepared_base(client, service))
    stream = io.BytesIO(); Image.new('RGBA', (2048, 2048), 'blue').save(stream, format='PNG')
    asset = service.upload(1, stream.getvalue(), 'png')
    images = [service.image(1, ImageInput(base_id=base['id'], base_sha256=base['model_sha256'], image_asset=asset['id'],
        object_key='shirt', view=view, crop=[100, 100, 800, 800]).model_dump())['id'] for view in ('front', 'side')]
    return ShapeInput(base_id=base['id'], base_sha256=base['model_sha256'], image_ids=images, name='Shirt').model_dump()


def test_multiview_provider_one_post_recovery_and_download(setup, monkeypatch):
    client, service, _ = setup
    monkeypatch.setenv('MESHY_API_KEY', 'test-key')
    payload = shape_input(client, service)
    item, created = provider.create(service, 1, 'shape-request-123', payload)
    assert created
    directory = service.directory(1, item['id']); calls = []
    real_client = httpx.Client
    def handle(request):
        calls.append(request)
        if request.method == 'POST':
            intent = json.loads((directory/'meshy/character.json').read_text())
            assert intent['status'] == 'submission_uncertain'
            body = json.loads(request.content)
            assert len(body['image_urls']) == 2 and body['ai_model'] == 'meshy-7'
            assert 'pose_mode' not in body
            raise httpx.ReadTimeout('lost result')
        assert request.url.path == '/openapi/v1/multi-image-to-3d/recovered-task'
        return httpx.Response(200, json={'status': 'SUCCEEDED', 'progress': 100})
    monkeypatch.setattr(provider.httpx, 'Client', lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(handle)))
    paused = provider.execute(service, 1, item['id'])
    assert paused['status'] == 'provider_paused' and 'recover_task' in paused['next_actions']
    # Restarted service and identical request cannot emit another paid POST.
    restored = AvatarStandard(service.root.parent)
    same, created = provider.create(restored, 1, 'shape-request-123', payload)
    assert not created and same['id'] == item['id']
    provider.execute(restored, 1, item['id'])
    assert len(calls) == 1
    def download(run, stage):
        assert stage == 'generation'
        (run/'generated.glb').write_bytes(rigged_glb())
        value = {'generated': {'sha256': sha(run/'generated.glb')}}
        _write_json(run/'generation-artifacts.json', value)
        return value
    monkeypatch.setattr(provider.character_jobs, 'download', download)
    ready = provider.execute(restored, 1, item['id'], poll=True, task_id='recovered-task')
    assert ready['status'] == 'model_ready' and ready['result']['model_asset']
    assert ready['provider']['task_id'] == 'recovered-task'
    assert service.artifact(1, item['id'], 'generated.glb').read_bytes() == rigged_glb()
    assert len([c for c in calls if c.method == 'POST']) == 1
    assert 'test-key' not in json.dumps(ready) and 'base_url' not in json.dumps(ready)


def test_multiview_rejects_mixed_objects_and_wrong_order(setup, monkeypatch):
    client, service, _ = setup
    monkeypatch.setenv('MESHY_API_KEY', 'test-key')
    payload = shape_input(client, service)
    with pytest.raises(PipelineError, match='정면'):
        provider.create(service, 1, 'wrong-order-123', {**payload, 'image_ids': list(reversed(payload['image_ids']))})
    path = service.directory(1, payload['image_ids'][1])/'record.json'
    value = json.loads(path.read_text()); value['contract']['object_key'] = 'different-shoe'; _write_json(path, value)
    with pytest.raises(PipelineError, match='동일 물체'):
        provider.create(service, 1, 'wrong-object-123', payload)
    with pytest.raises(ValidationError):
        ShapeInput(**{**payload, 'max_new_tasks': 2})


def design_input(client, service):
    base = prepared_base(client, service); directory = service.directory(1, base['id'])
    Image.new('RGBA', (2048, 2048), 'white').save(directory/'front.png')
    base['files']['front.png'] = sha(directory/'front.png'); _write_json(directory/'record.json', base)
    approve(service, base)
    return DesignInput(name='Measured cardigan', base_id=base['id'], base_sha256=base['model_sha256'],
        object_key='cardigan', view='front', description='Cream cardigan matching the frozen body.').model_dump()


@pytest.mark.parametrize('failure', [None, 'timeout', 'rejected'])
def test_design_body_reference_frozen_model_and_single_attempt(setup, monkeypatch, failure):
    client, service, _ = setup
    monkeypatch.setenv('OPENAI_API_KEY', 'fixture-only')
    monkeypatch.setenv('OPENAI_API_BASE', 'https://example.test/v1')
    payload = design_input(client, service)
    item, created = design.create(service, 1, 'design-request-123', payload)
    assert created
    monkeypatch.setenv('OPENAI_API_BASE', 'https://must-not-switch.test/v1')
    monkeypatch.setenv('AVATAR_IMAGE_MODEL', 'must-not-switch-model')
    directory = service.directory(1, item['id']); calls = []
    image = Image.new('RGBA', (1024, 1024)); ImageDraw.Draw(image).rectangle((100,100,400,400), fill='blue')
    output = io.BytesIO(); image.save(output, format='PNG')
    real_client = httpx.Client
    def handle(request):
        calls.append(request)
        assert request.url.host == 'example.test'
        assert b'gpt-image-2.5-sunburst' in request.content and b'2048x2048' in request.content
        assert request.headers['content-type'] == 'application/json'
        sent = json.loads(request.content)
        assert sent['images'][0]['image_url'].startswith('data:image/png;base64,')
        assert base64.b64decode(sent['images'][0]['image_url'].split(',', 1)[1]) == (directory/'reference-0.png').read_bytes()
        assert b'Cream cardigan' in request.content and b'scalp at y=300' in request.content
        assert json.loads((directory/'design.json').read_text())['attempt'] == 'submitting'
        if failure == 'timeout':
            raise httpx.ReadTimeout('lost response')
        if failure == 'rejected':
            return httpx.Response(400, json={'error': {'message': 'rejected'}})
        return httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(output.getvalue()).decode()}]})
    monkeypatch.setattr(design.httpx, 'Client', lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(handle)))
    value = design.execute(service, 1, item['id'])
    design.execute(AvatarStandard(service.root.parent), 1, item['id'])
    assert len(calls) == 1
    if failure:
        assert value['status'] == 'image_paused'
        return
    assert value['status'] == 'design_review_required'
    assert value['result']['normalization']['source_size'] == [1024,1024]
    assert service.artifact(1, item['id'], 'provider-original.png').read_bytes() == output.getvalue()
    anchors = [{'name': str(i), 'source': p, 'target': [p[0]+100,p[1]+100]} for i,p in enumerate([[200,200],[800,200],[200,800]])]
    aligned = design.align(service, 1, item['id'], AlignDesignInput(source_sha256=value['result']['image_asset'],
        anchors=anchors, isolated_part_checked=True, same_object_checked=True).model_dump())
    assert aligned['kind'] == 'image' and aligned['lineage']['alignment']['translation_px'] == [100,100]
    assert aligned['lineage']['source_sha256'] == value['result']['image_asset']
    with Image.open(service.artifact(1, aligned['id'], 'canvas.png')) as result:
        assert result.size == (2048,2048)
        assert abs(result.getchannel('A').getbbox()[0]-300) <= 5
    bad = [dict(a) for a in anchors]; bad[2] = {**bad[2], 'target': [600,900]}
    with pytest.raises(PipelineError, match='비율'):
        design.similarity(bad, 8)
    assert 'fixture-only' not in json.dumps(value) and 'example.test' not in json.dumps(value)


def test_provider_disk_lease_respects_cli_owner(setup, monkeypatch):
    client, service, _ = setup
    monkeypatch.setenv('MESHY_API_KEY', 'fixture-only')
    item, _ = provider.create(service, 1, 'cli-lock-test-123', shape_input(client, service))
    from src.services.wardrobe import run_lock
    run = service.directory(1, item['id'])/'meshy'
    with run_lock(run, 0, blender=False):
        with pytest.raises(PipelineError, match='잠금'):
            provider.execute(service, 1, item['id'])
    assert not (run/'character.json').exists()
