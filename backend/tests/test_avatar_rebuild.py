import pytest

from test_avatar_image_pipeline import setup
from src.services.asset_editor import _write_json
from src.services.character_pipeline import PipelineError, read_json


def completed(setup):
    service, factory, payload, calls, _, _ = setup
    job, _ = service.create(1, 'local-rebuild-fixture', {**payload, 'slots': ['hat']})
    service.execute(1, job['id'], poll_seconds=0)
    path = factory.directory(1, job['id']) / 'job.json'
    value = read_json(path)
    value['status'] = 'review_required'
    _write_json(path, value)
    return service, factory, calls, job, path


def test_rebuild_uses_completed_parts_without_credentials_or_provider_calls(setup, monkeypatch):
    service, factory, calls, job, path = completed(setup)
    original = path.read_bytes()
    monkeypatch.delenv('MESHY_API_KEY')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    rebuilt = service.rebuild(1, job['id'])
    assert rebuilt['id'] != job['id']
    assert rebuilt['limits'] == {'image_tasks': 0, 'meshy_tasks': 0}
    service.execute(1, rebuilt['id'], poll_seconds=0)
    assert len(calls['posts']) == len(calls['images']) == 1
    assert len(calls['compiled']) == 2
    assert path.read_bytes() == original
    with pytest.raises(PipelineError):
        service.rebuild(2, job['id'])


def test_rebuild_refuses_missing_model_receipt_before_creating_version(setup):
    service, factory, _, job, path = completed(setup)
    before = set(path.parent.parent.iterdir())
    (path.parent / 'parts/hat/generation-artifacts.json').unlink()
    with pytest.raises(PipelineError, match='영수증'):
        service.rebuild(1, job['id'])
    assert set(path.parent.parent.iterdir()) == before


def test_zero_submission_limits_are_enforced_by_executor(setup):
    service, factory, payload, calls, _, _ = setup
    job, _ = service.create(1, 'zero-budget-fixture', {**payload, 'slots': ['hat']})
    path = factory.directory(1, job['id']) / 'job.json'
    value = read_json(path)
    value['limits']['image_tasks'] = 0
    _write_json(path, value)
    service.execute(1, job['id'], poll_seconds=0)
    assert not calls['images'] and not calls['posts']
    assert factory.get(1, job['id'])['status'] == 'pipeline_paused'


def test_zero_cost_rebuild_never_replaces_missing_task_with_paid_generation(setup):
    service, factory, calls, job, _ = completed(setup)
    rebuilt = service.rebuild(1, job['id'])
    run = factory.directory(1, rebuilt['id']) / 'parts/hat'
    (run / 'generation-artifacts.json').unlink()
    (run / 'character.json').unlink()
    service.execute(1, rebuilt['id'], poll_seconds=0)
    assert len(calls['posts']) == len(calls['images']) == 1
    assert len(calls['compiled']) == 1
    assert factory.get(1, rebuilt['id'])['status'] == 'pipeline_paused'
