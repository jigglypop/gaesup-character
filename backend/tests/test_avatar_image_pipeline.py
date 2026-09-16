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
    monkeypatch.setenv('OPENAI_API_KEY', 'fixture-image-key')
    monkeypatch.setenv('MESHY_API_KEY', 'fixture-mesh-key')
    monkeypatch.setattr(module, 'blender_executable', lambda: 'fixture-blender')
    factory = AvatarFactory(tmp_path); service = AvatarImagePipeline(factory)
    character = factory.pipeline.create('Image Fixture', None, 1)
    character = factory.pipeline.upload(character['id'], 1, png(), 'image', character['revision'])
    blueprint = service.blueprints.read(1, character['id'])
    payload = {'character_id': character['id'], 'source_sha256': blueprint['source_sha256'],
               'blueprint_revision': blueprint['revision'], 'slots': PARTS[:7], 'image_mode': 'generate'}
    calls = {'images': [], 'posts': [], 'gets': [], 'compiled': []}
    def image(source, prompt, model, base, **kwargs):
        calls['images'].append(prompt); return png((len(calls['images'])*20, 20, 50, 255))
    monkeypatch.setattr(module, 'generate_openai_part_image', image)
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
    assert {p['slot'] for p in compiled['part_models']} == set(payload['slots'])
    assert len({p['task_id'] for p in compiled['part_models']}) == 7
    assert compiled['rig'].endswith('rig-maple-v1.json')
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


def test_equipment_description_and_provider_are_snapshotted(setup, monkeypatch):
    service, factory, payload, calls, _, _ = setup
    monkeypatch.setenv('AVATAR_IMAGE_MODEL', 'gpt-image-2.5-sunburst')
    blueprint = service.blueprints.read(1, payload['character_id'])
    next(l for l in blueprint['layers'] if l['slot'] == 'weapon')['description'] = 'Blue crystal staff'
    saved = service.blueprints.save(1, payload['character_id'], blueprint['layers'], blueprint['revision'], 'equipment-design')
    slots = [slot for slot in PARTS if slot != 'body']
    job, _ = service.create(1, 'equipment-production', {**payload, 'blueprint_revision': saved['revision'], 'slots': slots})
    assert job['image_provider'] == 'openai' and job['image_model'] == 'gpt-image-2.5-sunburst'
    monkeypatch.setenv('AVATAR_IMAGE_MODEL', 'must-not-change-accepted-job')
    state = read_json(factory.directory(1, job['id'])/'pipeline.json')
    assert state['image_model'] == 'gpt-image-2.5-sunburst'
    service.execute(1, job['id'], poll_seconds=0)
    assert len(calls['images']) == len(calls['posts']) == len(slots)
    assert any('Blue crystal staff' in prompt for prompt in calls['images'])
    assert {p['slot'] for p in calls['compiled'][0]['part_models']} == set(slots)


def test_legacy_blueprint_save_keeps_new_equipment(setup):
    service, _, payload, _, _, _ = setup
    current = service.blueprints.read(1, payload['character_id'])
    next(l for l in current['layers'] if l['slot'] == 'weapon')['description'] = 'Keep this staff'
    current = service.blueprints.save(1, payload['character_id'], current['layers'], current['revision'], 'new-equipment-save')
    legacy = current['layers'][:8]
    current = service.blueprints.save(1, payload['character_id'], legacy, current['revision'], 'old-client-save')
    assert len(current['layers']) == 13
    assert next(l for l in current['layers'] if l['slot'] == 'weapon')['description'] == 'Keep this staff'


def test_legacy_image_job_uses_recorded_gemini_adapter(setup, monkeypatch):
    service, factory, payload, calls, _, _ = setup
    job, _ = service.create(1, 'legacy-provider-job', {**payload, 'slots': ['hat']})
    path = factory.directory(1, job['id'])/'pipeline.json'
    state = read_json(path); state.pop('image_provider')
    state.update(image_model='legacy-gemini-model', image_base='https://legacy.invalid')
    _write_json(path, state)
    seen = []
    def legacy(source, prompt, model, base):
        seen.append((model, base)); return png()
    monkeypatch.setattr(module, 'generate_part_image', legacy)
    service.execute(1, job['id'], poll_seconds=0)
    assert seen == [('legacy-gemini-model', 'https://legacy.invalid')]
    assert not calls['images'] and len(calls['posts']) == 1


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
    def fail(*args, **kwargs):
        calls['images'].append('attempt'); raise httpx.ReadTimeout('secret URL must not reach UI')
    monkeypatch.setattr(module, 'generate_openai_part_image', fail)
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


def test_openai_rejection_exposes_only_safe_category_and_diagnostic(setup, monkeypatch):
    service, factory, payload, calls, _, _ = setup
    diagnostic_id = 'safe123abc45'
    def reject(*args, **kwargs):
        calls['images'].append('attempt')
        raise module.OpenAIImageHTTPError(400, 'model', diagnostic_id,
                                          {'type': 'invalid_request_error', 'param': 'model'})
    monkeypatch.setattr(module, 'generate_openai_part_image', reject)
    job, _ = service.create(1, 'image-rejected-key', {**payload, 'slots': ['body']})
    service.execute(1, job['id'])
    public = factory.get(1, job['id'])
    assert public['parts'][0]['image_status'] == 'rejected'
    assert '이미지 모델' in public['error'] and diagnostic_id in public['error']
    assert 'invalid_request_error' not in public['error']
    with pytest.raises(PipelineError):
        service.resume(1, job['id'])
    assert calls['images'] == ['attempt'] and not calls['posts']


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
    monkeypatch.delenv('OPENAI_API_KEY')
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


def test_whole_character_is_one_image_and_one_nonisolated_model(setup):
    service, factory, payload, calls, _, _ = setup
    job, _ = service.create(1, 'whole-character-test', {**payload, 'slots': ['body']})
    assert job['limits'] == {'image_tasks': 1, 'meshy_tasks': 1}
    service.execute(1, job['id'], poll_seconds=0)
    assert len(calls['images']) == len(calls['posts']) == 1
    assert 'complete full-body' in calls['images'][0] and 'short-sleeved T-shirt' in calls['images'][0]
    assert 'No cast shadows, checkerboard, text, other body parts or full character' not in calls['images'][0]
    assert calls['posts'][0]['pose_mode'] == 'a-pose'
    assert calls['compiled'][0]['part_models'][0]['slot'] == 'body'
    assert job['profile']['body_origin'] == 'generated_whole_character'
    with pytest.raises(PipelineError):
        service.create(1, 'mixed-whole-parts', {**payload, 'slots': ['body', 'face']})


def test_received_image_survives_index_failure_without_second_paid_call(setup, monkeypatch):
    service, factory, payload, calls, _, _ = setup
    job, _ = service.create(1, 'received-image-test', {**payload, 'slots': ['body']})
    upload = service.blueprints.upload
    def fail(*args):
        raise OSError('private fixture path and credential must not be returned')
    monkeypatch.setattr(service.blueprints, 'upload', fail)
    service.execute(1, job['id'], poll_seconds=0)
    paused = factory.get(1, job['id'])
    assert paused['parts'][0]['image_status'] == 'received'
    assert paused['next_actions'][0]['enabled']
    assert 'private fixture' not in json.dumps(paused)
    assert read_json(factory.directory(1, job['id'])/'failure.json')['type'] == 'OSError'
    monkeypatch.setattr(service.blueprints, 'upload', upload)
    service.resume(1, job['id']); service.execute(1, job['id'], poll_seconds=0)
    assert len(calls['images']) == len(calls['posts']) == 1


def test_native_meshy_path_skips_local_rebind_and_freezes_selected_actions(setup, monkeypatch):
    from src.services import avatar_meshy
    service, factory, payload, calls, _, _ = setup
    received = []
    class Provider:
        def __init__(self, factory): pass
        def library(self, owner): return [{'action_id': 77}]
        def start(self, owner, job): received.append(('rig', job))
        def execute(self, owner, job): received.append(('execute', job))
        def get(self, owner, job): return {'status': 'ready'}
    monkeypatch.setattr(avatar_meshy, 'AvatarMeshy', Provider)
    actions = {'walk': 77}
    job, _ = service.create(1, 'native-meshy-body', {**payload, 'slots': ['body'], 'rig_with_meshy': True, 'motion_actions': actions})
    actions['walk'] = 999  # Accepted action IDs are stored independently from caller state.
    assert job['limits'] == {'image_tasks': 1, 'meshy_tasks': 1, 'meshy_rig_tasks': 1, 'meshy_animation_tasks': 1}
    service.execute(1, job['id'], poll_seconds=0)
    assert not calls['compiled'] and received == [('rig', job['id']), ('execute', job['id'])]
    assert read_json(factory.directory(1, job['id'])/'pipeline.json')['motion_actions'] == {'walk': 77}
    assert len(calls['posts']) == len(calls['images']) == 1
    current = factory.get(1, job['id'])
    assert current['profile']['rig'] == 'meshy-native' and not current.get('outfit')
    assert any(a['name'] == 'generated-body.glb' for a in current['artifacts'])
    with pytest.raises(PipelineError): service.rebuild(1, job['id'])


def test_wardrobe_body_prompt_is_frozen_and_keeps_face_and_limbs_without_outer_clothes(setup, monkeypatch):
    from src.services import avatar_meshy
    service, factory, payload, calls, _, _ = setup
    monkeypatch.setattr(avatar_meshy.AvatarMeshy, 'start', lambda *a: None)
    monkeypatch.setattr(avatar_meshy.AvatarMeshy, 'execute', lambda *a: None)
    monkeypatch.setattr(avatar_meshy.AvatarMeshy, 'get', lambda *a: {'status': 'pending'})
    submitted = {**payload, 'slots': ['body'], 'body_purpose': 'wardrobe_base', 'rig_with_meshy': True}
    job, _ = service.create(1, 'wardrobe-body-fixture', submitted)
    frozen = read_json(factory.directory(1, job['id'])/'pipeline.json')
    assert frozen['body_height_m'] == 1.2
    assert job['profile']['height'] == frozen['body_height_m']
    assert job['profile']['base_outfit'] == 'opaque_training_bodysuit'
    assert job['profile']['head_height'] is None
    monkeypatch.setattr(module, 'WARDROBE_BODY_PROMPT', 'Changed after acceptance')
    service.execute(1, job['id'], poll_seconds=0)
    assert calls['images'] == [frozen['body_prompt']]
    assert 'entire bald head' in calls['images'][0] and 'fully clothed neutral fitted opaque training bodysuit' in calls['images'][0]
    assert 'from neck to wrists and ankles' in calls['images'][0] and 'hands and bare feet visible' in calls['images'][0]
    assert 'modesty underlayer' not in calls['images'][0] and 'No nudity' not in calls['images'][0]
    assert 'short-sleeved T-shirt' not in calls['images'][0]
    assert calls['posts'][0]['pose_mode'] == 'a-pose' and not calls['compiled']
    assert job['profile']['body_purpose'] == 'wardrobe_base'
    with pytest.raises(PipelineError):
        service.create(1, 'invalid-wardrobe-body', {**submitted, 'slots': ['top']})


def test_character_parts_produces_exact_source_set_and_native_body_handoff(setup, monkeypatch):
    from src.services import avatar_meshy
    service, factory, payload, calls, _, _ = setup
    handed_off = []
    monkeypatch.setattr(avatar_meshy.AvatarMeshy, 'start', lambda self, owner, job: handed_off.append(('start', job)))
    monkeypatch.setattr(avatar_meshy.AvatarMeshy, 'execute', lambda self, owner, job: handed_off.append(('execute', job)))
    submitted = {**payload, 'production_mode': 'character_parts', 'slots': []}
    job, _ = service.create(1, 'character-parts-set', submitted)
    assert [p['slot'] for p in job['parts']] == module.CHARACTER_PART_SLOTS
    assert job['limits']['image_tasks'] == job['limits']['meshy_tasks'] == 7
    service.execute(1, job['id'], poll_seconds=0)
    assert len(calls['images']) == len(calls['posts']) == 7
    nonbody_prompts = calls['images'][1:]
    assert all('exact design, colors, materials' in prompt and 'Do not invent' in prompt for prompt in nonbody_prompts)
    assert not calls['compiled'] and handed_off == [('start', job['id']), ('execute', job['id'])]
    current = factory.get(1, job['id'])
    names = {artifact['name'] for artifact in current['artifacts']}
    assert {f'generated-{slot}.glb' for slot in module.CHARACTER_PART_SLOTS} <= names
    assert all(part['provenance']['review'] == 'pending' for part in current['parts'])


def test_character_parts_image_rejection_continues_all_parts_and_blocks_meshy(setup, monkeypatch):
    service, factory, payload, calls, _, _ = setup
    attempts = []
    def image(source, prompt, model, base, **kwargs):
        attempts.append(prompt)
        if 'top alone' in prompt:
            raise module.OpenAIImageHTTPError(400, 'policy', 'rejecttop123')
        return png()
    monkeypatch.setattr(module, 'generate_openai_part_image', image)
    job, _ = service.create(1, 'character-parts-one-reject',
                            {**payload, 'production_mode': 'character_parts', 'slots': module.CHARACTER_PART_SLOTS})
    service.execute(1, job['id'], poll_seconds=0)
    current = factory.get(1, job['id'])
    assert len(attempts) == 7 and not calls['posts']
    top = next(part for part in current['parts'] if part['slot'] == 'top')
    assert top['image_status'] == 'rejected'
    assert top['image_failure']['category'] == 'policy' and top['image_failure']['id'] == 'rejecttop123'
    assert sum(part['image_status'] == 'succeeded' for part in current['parts']) == 6
    assert current['status'] == 'pipeline_paused' and 'Meshy 단계는 시작하지 않았습니다' in current['error']


def test_character_parts_uncertain_image_is_never_reposted(setup, monkeypatch):
    service, factory, payload, calls, _, _ = setup
    attempts = []
    def image(source, prompt, model, base, **kwargs):
        attempts.append(prompt)
        if 'back hair shell' in prompt:
            raise httpx.ReadTimeout('lost response')
        return png()
    monkeypatch.setattr(module, 'generate_openai_part_image', image)
    job, _ = service.create(1, 'character-parts-uncertain',
                            {**payload, 'production_mode': 'character_parts', 'slots': module.CHARACTER_PART_SLOTS})
    service.execute(1, job['id'], poll_seconds=0)
    current = factory.get(1, job['id'])
    hair = next(part for part in current['parts'] if part['slot'] == 'hairBack')
    assert hair['image_status'] == 'submission_uncertain' and len(attempts) == 7
    with pytest.raises(PipelineError):
        service.resume(1, job['id'])
    service.execute(1, job['id'], poll_seconds=0)
    assert len(attempts) == 7 and not calls['posts']


def test_character_parts_local_image_failure_continues_and_resumes_without_repost(setup, monkeypatch):
    service, factory, payload, calls, _, _ = setup
    original_upload = service.blueprints.upload
    uploads = 0
    def upload(owner, raw):
        nonlocal uploads
        uploads += 1
        if uploads == 3:
            raise OSError('local index unavailable')
        return original_upload(owner, raw)
    monkeypatch.setattr(service.blueprints, 'upload', upload)
    job, _ = service.create(1, 'character-parts-local-failure',
                            {**payload, 'production_mode': 'character_parts', 'slots': module.CHARACTER_PART_SLOTS})
    service.execute(1, job['id'], poll_seconds=0)
    paused = factory.get(1, job['id'])
    assert len(calls['images']) == 7 and not calls['posts']
    assert sum(part['image_status'] == 'succeeded' for part in paused['parts']) == 6
    local = next(part for part in paused['parts'] if part['image_status'] == 'received')
    assert local['image_failure']['category'] == 'local_processing'
    monkeypatch.setattr(service.blueprints, 'upload', original_upload)
    service.resume(1, job['id']); service.execute(1, job['id'], poll_seconds=0)
    assert len(calls['images']) == 7
    assert sum(post.get('ai_model') == 'meshy-7' for post in calls['posts']) == 7


def test_character_parts_reuses_verified_six_parts_but_never_body(setup, monkeypatch):
    from src.services import avatar_meshy
    service, factory, payload, calls, _, _ = setup
    reusable_slots = ['hairBack', 'hairFront', 'hat', 'top', 'bottom', 'shoes']
    prior, _ = service.create(1, 'reusable-six-parts', {**payload, 'slots': reusable_slots})
    service.execute(1, prior['id'], poll_seconds=0)
    calls['images'].clear(); calls['posts'].clear(); calls['compiled'].clear()
    monkeypatch.setattr(avatar_meshy.AvatarMeshy, 'start', lambda *args: None)
    monkeypatch.setattr(avatar_meshy.AvatarMeshy, 'execute', lambda *args: None)
    current, _ = service.create(1, 'reuse-six-plus-body', {**payload,
        'production_mode': 'character_parts', 'slots': module.CHARACTER_PART_SLOTS,
        'reuse_job_id': prior['id']})
    assert current['limits']['image_tasks'] == current['limits']['meshy_tasks'] == 1
    assert all(next(p for p in current['parts'] if p['slot'] == slot)['model_status'] == 'ready'
               for slot in reusable_slots)
    assert next(p for p in current['parts'] if p['slot'] == 'body')['model_status'] == 'pending'
    service.execute(1, current['id'], poll_seconds=0)
    assert len(calls['images']) == len(calls['posts']) == 1
    assert calls['posts'][0]['pose_mode'] == 'a-pose'
    names = {artifact['name'] for artifact in factory.get(1, current['id'])['artifacts']}
    assert {f'generated-{slot}.glb' for slot in module.CHARACTER_PART_SLOTS} <= names
