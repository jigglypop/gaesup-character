"""Batch ownership, exactly bounded provider calls, and interrupted row recovery."""
import base64
import io
import json

import httpx
import pytest
from PIL import Image

from test_avatar_standard import setup, prepared_base, approve
from src.services.asset_editor import _write_json
from src.services.avatar_standard import sha
from src.services.avatar_standard_batch import WardrobeBatch
from src.services.avatar_standard_models import BatchInput, AlignDesignInput
from src.services import avatar_standard_design as design, avatar_standard_provider as shape
from src.services.character_pipeline import PipelineError, read_json


def order(client, service, monkeypatch):
    base = approve(service, prepared_base(client, service))
    directory = service.directory(1, base['id'])
    Image.new('RGBA', (2048, 2048), '#999999').save(directory/'front.png')
    base = service.raw(1, base['id']); base['files']['front.png'] = sha(directory/'front.png')
    _write_json(directory/'record.json', base)
    monkeypatch.setenv('OPENAI_API_KEY', 'fixture-only')
    monkeypatch.setenv('MESHY_API_KEY', 'fixture-only')
    return BatchInput(name='Two tops', base_id=base['id'], base_sha256=base['model_sha256'], rows=[
        {'key': k, 'name': k, 'slot': 'top', 'garment_type': 'top', 'description': k+' cotton shirt'}
        for k in ('cream', 'blue')]).model_dump()


def reference(service, owner=1, color='#c05080'):
    output = io.BytesIO()
    Image.new('RGBA', (320, 480), color).save(output, format='PNG')
    return service.upload(owner, output.getvalue(), 'png')['id']


def test_batch_freezes_contract_and_continues_independent_rows(setup, monkeypatch):
    client, service, app = setup
    payload = order(client, service, monkeypatch)
    batch = WardrobeBatch(service)
    item, created = batch.create(1, 'batch-test-123', payload)
    assert created and item['limits']['images'] == 2 and item['limits']['meshy_rigging'] == 0
    assert batch.create(1, 'batch-test-123', payload)[1] is False
    with pytest.raises(PipelineError, match='변경'):
        batch.create(1, 'batch-test-123', {**payload, 'name': 'changed'})
    with pytest.raises(PipelineError):
        batch.public(2, item['id'])
    assert all(r['image_id'] is None for r in item['rows'])
    calls = []
    output = io.BytesIO(); Image.new('RGBA', (2048,2048), 'blue').save(output, format='PNG')
    real_client = httpx.Client
    def handle(request):
        data = json.loads(request.content); calls.append(data['prompt'])
        assert data['model'] == 'gpt-image-2.5-sunburst'
        if 'cream cotton' in data['prompt']:
            raise httpx.ReadError('uncertain request')
        return httpx.Response(200, json={'data':[{'b64_json':base64.b64encode(output.getvalue()).decode()}]})
    monkeypatch.setattr(design.httpx, 'Client', lambda **kw: real_client(**kw, transport=httpx.MockTransport(handle)))
    monkeypatch.setenv('OPENAI_API_BASE', 'https://changed.invalid')
    batch.execute(1, item['id'])
    batch.execute(1, item['id'])
    current = batch.public(1, item['id'])
    assert len(calls) == 2
    assert current['rows'][0]['design']['status'] == 'image_paused'
    assert current['rows'][1]['stage'] == 'image_review'
    assert current['ready_count'] == 0 and not current['busy']
    private = batch.raw(1, item['id'])
    for row in current['rows']:
        saved = read_json(service.directory(1,row['design']['id'])/'design.json')
        assert saved['base_url'] == private['providers']['image']['base_url']
    public = json.dumps(current)
    assert 'fixture-only' not in public and 'https://changed.invalid' not in public


def test_batch_freezes_owned_reference_and_passes_it_after_base_view(setup, monkeypatch):
    client, service, _ = setup
    payload = {**order(client, service, monkeypatch), 'reference_asset': reference(service)}
    batch = WardrobeBatch(service)
    item, created = batch.create(1, 'batch-reference-test', payload)
    assert created and item['contract']['reference_asset'] == payload['reference_asset']
    assert item['reference_image_url'] == f'/api/avatar-standard/batches/{item["id"]}/reference'
    assert batch.create(1, 'batch-reference-test', payload)[1] is False
    frozen = batch.directory(1, item['id'])/'reference.png'
    private = batch.raw(1, item['id'])
    assert private['reference'] == {
        'asset_id': payload['reference_asset'], 'file': 'reference.png', 'sha256': payload['reference_asset'],
    }
    assert sha(frozen) == payload['reference_asset']
    response = client.get(item['reference_image_url'])
    assert response.status_code == 200 and sha(batch.reference(1, item['id'])) == payload['reference_asset']
    with pytest.raises(PipelineError) as hidden:
        batch.reference(2, item['id'])
    assert hidden.value.code == 'not_found'
    with pytest.raises(PipelineError, match='변경'):
        batch.create(1, 'batch-reference-test', {**payload, 'reference_asset': reference(service, color='#305090')})

    output = io.BytesIO(); Image.new('RGBA', (2048, 2048), 'blue').save(output, format='PNG')
    monkeypatch.setattr(design, 'generate_standard_part_image', lambda *args, **kwargs: output.getvalue())
    batch.execute(1, item['id'])
    for row in batch.public(1, item['id'])['rows']:
        assert row['design']['contract']['reference_asset'] == payload['reference_asset']
        settings = read_json(service.directory(1, row['design']['id'])/'design.json')
        assert len(settings['references']) == 2
        assert settings['references'][0]['sha256'] == service.raw(1, payload['base_id'])['files']['front.png']
        assert settings['references'][1]['sha256'] == payload['reference_asset']
    frozen.write_bytes(b'changed')
    changed = client.get(item['reference_image_url'])
    assert changed.status_code == 409 and changed.json()['error']['code'] == 'reference_changed'


def test_batch_rejects_other_owner_reference_and_blocks_changed_source(setup, monkeypatch):
    client, service, _ = setup
    payload = order(client, service, monkeypatch)
    other = reference(service, owner=2)
    with pytest.raises(PipelineError) as error:
        WardrobeBatch(service).create(1, 'batch-other-owner', {**payload, 'reference_asset': other})
    assert error.value.code == 'asset_changed'

    owned = reference(service)
    batch = WardrobeBatch(service)
    item, _ = batch.create(1, 'batch-changed-reference', {**payload, 'reference_asset': owned})
    source = service.root/'1'/'uploads'/f'{owned}.png'
    source.write_bytes(b'changed')
    calls = []
    monkeypatch.setattr(design, 'create', lambda *args, **kwargs: calls.append((args, kwargs)))
    batch.execute(1, item['id'])
    assert calls == []
    assert read_json(batch.directory(1, item['id'])/'execution.json')['status'] == 'paused'
    assert sha(batch.directory(1, item['id'])/'reference.png') == owned


def test_batch_shapes_once_after_alignment_then_reuses_existing_job(setup, monkeypatch):
    client, service, app = setup
    payload = order(client, service, monkeypatch)
    batch = WardrobeBatch(service)
    item, _ = batch.create(1, 'batch-shape-test', payload)
    output = io.BytesIO(); Image.new('RGBA',(2048,2048),'blue').save(output,format='PNG')
    monkeypatch.setattr(design, 'generate_standard_part_image', lambda *a, **kw: output.getvalue())
    batch.execute(1,item['id'])
    anchors = [{'name':str(i),'source':p,'target':p} for i,p in enumerate([[200,200],[800,200],[200,800]])]
    for row in batch.public(1,item['id'])['rows']:
        designed = row['design']
        design.align(service,1,designed['id'],AlignDesignInput(source_sha256=designed['result']['image_asset'],
            anchors=anchors,isolated_part_checked=True,same_object_checked=True).model_dump())
    calls=[]
    def execute(service, owner, shape_id, **kw):
        calls.append((shape_id,kw)); value=service.raw(owner,shape_id)
        value.update(status='model_ready',result={'model_asset':'a'*64})
        _write_json(service.directory(owner,shape_id)/'record.json',value)
        return service.public(owner,shape_id)
    monkeypatch.setattr(shape,'execute',execute)
    batch.execute(1,item['id']); batch.execute(1,item['id'])
    assert len(calls)==2 and len({i for i,_ in calls})==2
    current=batch.public(1,item['id'])
    assert all(r['stage']=='fit_required' for r in current['rows'])
    assert current['ready_count']==0  # shapes are not interchangeable fitted clothes
    assert all(r['shape']['contract']['base_sha256']==payload['base_sha256'] for r in current['rows'])


def test_batch_api_rejects_changed_body_and_duplicate_rows(setup,monkeypatch):
    client,service,app=setup
    payload=order(client,service,monkeypatch)
    monkeypatch.setattr(WardrobeBatch,'execute',lambda *a: None)
    headers={'Idempotency-Key':'batch-api-test'}
    response=client.post('/api/avatar-standard/batches',json=payload,headers=headers)
    assert response.status_code==202,response.text
    item=response.json()
    assert client.post('/api/avatar-standard/batches',json=payload,headers=headers).json()['id']==item['id']
    assert len(client.get('/api/avatar-standard/batches').json()['items'])==1
    bad={**payload,'rows':[payload['rows'][0],payload['rows'][0]]}
    assert client.post('/api/avatar-standard/batches',json=bad,headers=headers).status_code==422
    assert client.post('/api/avatar-standard/batches',json={**payload,'base_sha256':'0'*64},headers={'Idempotency-Key':'batch-api-other'}).status_code==409
    assert client.post(f'/api/avatar-standard/batches/{item["id"]}/resume').status_code==202


def test_standard_image_recovers_saved_response_without_repost(setup,monkeypatch):
    client,service,app=setup
    payload=order(client,service,monkeypatch)
    batch=WardrobeBatch(service); item,_=batch.create(1,'saved-image-test',payload)
    output=io.BytesIO(); Image.new('RGBA',(2048,2048),'blue').save(output,format='PNG')
    def saved_response(*args,receipt=None,**kwargs):
        receipt.with_suffix('.response.json').write_text(json.dumps({'data':[{'b64_json':base64.b64encode(output.getvalue()).decode()}]}))
        raise ValueError('process stopped after saving response')
    original=design.generate_standard_part_image
    monkeypatch.setattr(design,'generate_standard_part_image',saved_response)
    batch.execute(1,item['id'])
    monkeypatch.setattr(design,'generate_standard_part_image',original)
    real_client=httpx.Client
    def forbid(request):
        raise AssertionError('A cached response must not send any request')
    monkeypatch.setattr(design.httpx,'Client',lambda **kw:real_client(**kw,transport=httpx.MockTransport(forbid)))
    batch.execute(1,item['id'])
    assert all(r['stage']=='image_review' for r in batch.public(1,item['id'])['rows'])
