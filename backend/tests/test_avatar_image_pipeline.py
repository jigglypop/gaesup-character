import hashlib
import io
import json

import httpx
from PIL import Image
import pytest

from src.services import avatar_image_pipeline as module
from src.services.asset_editor import _write_json
from src.services.avatar_factory import AvatarFactory
from src.services.avatar_image_pipeline import AvatarImagePipeline, PARTS
from src.services.character_pipeline import PipelineError, read_json
from api.test_characters import rigged_glb


def png(color='red'):
    stream = io.BytesIO(); Image.new('RGBA', (24, 24), color).save(stream, format='PNG'); return stream.getvalue()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'fixture-image-key')
    monkeypatch.setenv('MESHY_API_KEY', 'fixture-mesh-key')
    monkeypatch.setattr(module, 'blender_executable', lambda: 'fixture-blender')
    factory = AvatarFactory(tmp_path); service = AvatarImagePipeline(factory)
    character = factory.pipeline.create('Image Fixture', None, 1)
    character = factory.pipeline.upload(character['id'], 1, png(), 'image', character['revision'])
    blueprint = service.blueprints.read(1, character['id'])
    payload = {'character_id': character['id'], 'source_sha256': blueprint['source_sha256'],
               'blueprint_revision': blueprint['revision'], 'slots': PARTS, 'image_mode': 'generate'}
    calls = {'images': [], 'posts': [], 'gets': [], 'compiled': []}
    def image(source, prompt, model, base):
        calls['images'].append(prompt); return png((len(calls['images'])*30, 20, 50, 255))
    monkeypatch.setattr(module, 'generate_part_image', image)
    def transport(request):
        if request.method == 'POST':
            calls['posts'].append(json.loads(request.content))
            return httpx.Response(200, json={'result': f'fixture-task-{len(calls["posts"])}'})
        calls['gets'].append(request.url.path)
        return httpx.Response(200, json={'status': 'SUCCEEDED', 'progress': 100, 'model_urls': {'glb': 'https://fixture.invalid/model.glb'}})
    client_type = httpx.Client
    monkeypatch.setattr(module.httpx, 'Client', lambda **kwargs: client_type(**kwargs, transport=httpx.MockTransport(transport)))
    def download(directory, stage):
        path = directory/'generated.glb'; path.write_bytes(rigged_glb())
        result = {'generated': {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
        _write_json(directory/'generation-artifacts.json', result); return result
    monkeypatch.setattr(module.character_jobs, 'download', download)
    monkeypatch.setattr(factory, 'execute', lambda owner, jid: calls['compiled'].append(read_json(factory.directory(owner, jid)/'output/input.json')))
    return service, factory, payload, calls, transport, client_type


def test_distinct_part_images_tasks_and_common_rig_handoff(setup):
    service, factory, payload, calls, _, _ = setup
    job, created = service.create(1, 'complete-pipeline', payload)
    assert created and job['limits'] == {'image_tasks': 7, 'meshy_tasks': 7}
    assert job['input_kind'] == 'image'
    replay, created = service.create(1, 'complete-pipeline', payload)
    assert replay['id'] == job['id'] and not created
    service.execute(1, job['id'], poll_seconds=0)
    assert len(calls['images']) == len(calls['posts']) == 7
    assert len({p['image_url'] for p in calls['posts']}) == 7
    assert all(p['ai_model'] == 'meshy-7' and 'pose_mode' not in p for p in calls['posts'])
    compiled = calls['compiled'][0]
    assert {p['slot'] for p in compiled['part_models']} == set(PARTS)
    assert len({p['task_id'] for p in compiled['part_models']}) == 7
    assert compiled['rig'].endswith('rig-v1.json')
    assert (factory.directory(1, job['id'])/'source.png').read_bytes() == png()
    public = factory.get(1, job['id'])
    assert len(public['artifacts']) == 7 and str(factory.data) not in json.dumps(public)
    assert 'fixture-image-key' not in json.dumps(public) and 'image_base' not in json.dumps(public)
    service.execute(1, job['id'])
    assert len(calls['posts']) == 7
    journal_path = factory.directory(1, job['id'])/'job.json'
    journal = read_json(journal_path); journal['status'] = 'failed'; _write_json(journal_path, journal)
    service.resume(1, job['id']); service.execute(1, job['id'], poll_seconds=0)
    assert len(calls['posts']) == len(calls['images']) == 7 and len(calls['compiled']) == 2
    with pytest.raises(PipelineError): factory.get(2, job['id'])
    with pytest.raises(PipelineError): service.create(1, 'complete-pipeline', {**payload, 'slots': ['hat']})


def test_lost_meshy_response_recovers_existing_id_without_repost(setup, monkeypatch):
    service, factory, payload, calls, transport, client_type = setup
    attempted = []
    def lost(request):
        if request.method == 'POST':
            attempted.append(request)
            raise httpx.ReadTimeout('response lost')
        return transport(request)
    monkeypatch.setattr(module.httpx, 'Client', lambda **kwargs: client_type(**kwargs, transport=httpx.MockTransport(lost)))
    job, _ = service.create(1, 'lost-submission', {**payload, 'slots': ['hat']})
    service.execute(1, job['id'])
    paused = factory.get(1, job['id'])
    assert paused['status'] == 'pipeline_paused' and paused['parts'][0]['model_status'] == 'submission_uncertain'
    assert not paused['next_actions'][0]['enabled']
    with pytest.raises(PipelineError): service.resume(1, job['id'])
    recovered = service.recover_task(1, job['id'], 'hat', 'existing-fixture-task')
    assert recovered['next_actions'][0]['enabled']
    service.resume(1, job['id']); service.execute(1, job['id'], poll_seconds=0)
    assert len(attempted) == 1 and len(calls['images']) == 1
    assert calls['compiled'][0]['part_models'][0]['task_id'] == 'existing-fixture-task'


def test_image_timeout_never_retries_and_server_restart_is_recoverable(setup, monkeypatch):
    service, factory, payload, calls, _, _ = setup
    def fail(*args):
        calls['images'].append('attempt'); raise httpx.ReadTimeout('secret URL must not reach UI')
    monkeypatch.setattr(module, 'generate_part_image', fail)
    job, _ = service.create(1, 'image-timeout-key', payload)
    service.execute(1, job['id'])
    assert factory.get(1, job['id'])['status'] == 'pipeline_paused'
    with pytest.raises(PipelineError): service.resume(1, job['id'])
    assert len(calls['images']) == 1 and not calls['posts']
    assert 'secret URL' not in json.dumps(factory.get(1, job['id']))
    job2, _ = service.create(1, 'queued-restart-key', payload)
    restarted = AvatarFactory(factory.data)
    import src.services.avatar_factory as factory_module
    monkeypatch.setattr(factory_module, 'process_state', lambda value: 'exited')
    assert restarted.get(1, job2['id'])['status'] == 'pipeline_paused'
    assert AvatarImagePipeline(restarted).resume(1, job2['id'])['status'] == 'pipeline_queued'


def test_poll_resume_and_download_never_resubmit(setup, monkeypatch):
    service, factory, payload, calls, transport, client_type = setup
    pending = True
    def delayed(request):
        if request.method == 'GET' and pending:
            return httpx.Response(200, json={'status': 'IN_PROGRESS', 'progress': 40})
        return transport(request)
    monkeypatch.setattr(module.httpx, 'Client', lambda **kwargs: client_type(**kwargs, transport=httpx.MockTransport(delayed)))
    job, _ = service.create(1, 'poll-resume-key', {**payload, 'slots': ['top', 'shoes']})
    service.execute(1, job['id'], poll_seconds=0, deadline_seconds=0)
    assert factory.get(1, job['id'])['status'] == 'pipeline_paused'
    pending = False
    service.resume(1, job['id']); service.execute(1, job['id'], poll_seconds=0)
    assert len(calls['posts']) == len(calls['images']) == 2 and len(calls['compiled']) == 1


def test_prepared_images_skip_image_provider_and_invalid_input_is_atomic(setup, monkeypatch):
    service, factory, payload, calls, _, _ = setup
    prepared = {**payload, 'slots': ['top'], 'image_mode': 'prepared'}
    monkeypatch.delenv('GEMINI_API_KEY')
    with pytest.raises(PipelineError): service.create(1, 'prepared-version', prepared)
    blueprint = service.blueprints.read(1, payload['character_id'])
    asset = service.blueprints.upload(1, png('blue'))
    layers = [{**layer, 'asset': asset['id'], 'crop': [0, 0, 1, 1]} if layer['slot'] == 'top' else layer for layer in blueprint['layers']]
    saved = service.blueprints.save(1, payload['character_id'], layers, blueprint['revision'], 'save-parts-key')
    job, _ = service.create(1, 'prepared-version', {**prepared, 'blueprint_revision': saved['revision']})
    service.execute(1, job['id'], poll_seconds=0)
    assert not calls['images'] and len(calls['posts']) == 1 and job['limits']['image_tasks'] == 0
    bad = [{**layer, 'placement': [0, 0, -1, 3]} for layer in layers]
    with pytest.raises(PipelineError): service.blueprints.save(1, payload['character_id'], bad, saved['revision'], 'bad-parts-key')


def test_image_api_accepts_once_validates_and_is_owner_scoped(setup, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.avatar_factory import router, get_factory
    from src.api.characters import pipeline_error_handler
    from src.auth import UserContext, get_current_user
    _, factory, payload, calls, _, _ = setup
    app = FastAPI(); app.include_router(router, prefix='/api')
    app.add_exception_handler(PipelineError, pipeline_error_handler)
    app.dependency_overrides[get_current_user] = lambda: UserContext(1, 'fixture', [])
    app.dependency_overrides[get_factory] = lambda: factory
    executions = []
    monkeypatch.setattr(AvatarImagePipeline, 'execute', lambda self, owner, job: executions.append(job))
    with TestClient(app) as client:
        headers = {'Idempotency-Key': 'api-full-pipeline'}
        first = client.post('/api/avatar-factory/image-jobs', json=payload, headers=headers)
        assert first.status_code == 202
        assert client.post('/api/avatar-factory/image-jobs', json=payload, headers=headers).json()['id'] == first.json()['id']
        assert len(executions) == 1 and not calls['posts']
        assert client.post('/api/avatar-factory/image-jobs', json={**payload, 'slots': ['head']}, headers=headers).status_code == 422
        assert client.post('/api/avatar-factory/image-jobs', json={**payload, 'slots': ['top','top']}, headers={'Idempotency-Key': 'api-invalid-slots'}).status_code == 422
        app.dependency_overrides[get_current_user] = lambda: UserContext(2, 'other', [])
        assert client.get('/api/avatar-factory/jobs/'+first.json()['id']).status_code == 404
        assert client.get('/api/avatar-factory/jobs').json()['jobs'] == []


def test_corrupt_png_is_input_error_instead_of_internal_server_error(setup):
    service, factory, payload, _, _, _ = setup
    corrupted = bytearray(png()); corrupted[-5] ^= 1
    # Corrupt IDAT's checksum, which Pillow reports as SyntaxError.
    offset = corrupted.find(b'IDAT'); corrupted[offset+4] ^= 1
    with pytest.raises(PipelineError) as error:
        service.blueprints.upload(1, bytes(corrupted))
    assert error.value.code == 'invalid_image'
    character = factory.pipeline.detail(payload['character_id'], 1)
    with pytest.raises(PipelineError) as error:
        factory.pipeline.upload(character['id'], 1, bytes(corrupted), 'image', character['revision'])
    assert error.value.code == 'invalid_image'
