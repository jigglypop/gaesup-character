"""Progress is derived from durable receipts, never elapsed-time animation."""
from src.services.character_pipeline import read_json


def production_progress(directory, job):
    parts = job.get('parts', [])
    images = [image for part in parts for image in (list(part.get('views', {}).values()) or [{'status': part.get('image_status')}])]
    image_done = sum(i.get('status') == 'succeeded' for i in images)
    image_received = sum(i.get('status') in ('received', 'succeeded', 'qc_failed') for i in images)
    image_failed = any(i.get('status') in ('not_sent', 'rejected', 'failed', 'submission_uncertain') for i in images)
    models_done = sum(p.get('model_status') == 'ready' for p in parts)
    # Provider 100% means generation finished; local download still has to succeed.
    model_fraction = sum(1 if p.get('model_status') == 'ready' else max(0, min(99, p.get('progress') or 0))/100 for p in parts)
    model_failed = any(p.get('model_status') in ('FAILED', 'CANCELED', 'submission_uncertain', 'submission_rejected') for p in parts)
    flow = job.get('character_flow', {})
    worker = read_json(directory/'meshy/worker.json'); rig = read_json(directory/'meshy/character.json')
    delivery = read_json(directory/'meshy/delivery.json')
    pointer = read_json(directory/'native-parts/current.json')
    native_dir = directory/'native-parts'/pointer['version'] if pointer else None
    native = read_json(native_dir/'record.json') if native_dir else {}
    native_ready = native.get('status') == 'review_required'
    frozen = bool(job.get('production_spec'))
    steps = []
    fractions = []
    def add(key, label, done, total, fraction=None, active=False, failed=False):
        state = 'complete' if total and done == total else 'running' if active else 'blocked' if failed else 'pending'
        amount = done if fraction is None else fraction
        fractions.append(max(0, min(total, amount)))
        steps.append({'id': key, 'label': label, 'state': state, 'completed': done, 'total': total,
                      'percent': min(99 if done != total else 100, round(100*amount/total)) if total else None})
    if frozen:
        add('spec', '공통 규격', 1, 1)
    add('images', '정면·측면' if frozen else '이미지', image_done, len(images),
        active=flow.get('busy') and flow.get('stage') in ('images', 'queued'), failed=image_failed)
    add('models', '3D 파츠', models_done, len(parts), fraction=model_fraction,
        active=flow.get('busy') and flow.get('stage') == 'models', failed=model_failed)
    rig_done = bool(delivery) and worker.get('status') == 'complete'
    add('rig', '리깅·동작', int(rig_done), 1, fraction=1 if rig_done else max(0, min(99, rig.get('progress') or 0))/100,
        active=flow.get('busy') and flow.get('stage') == 'rig', failed=not flow.get('busy') and bool(worker.get('error')))
    add('assemble', '피팅·조립', int(native_ready), 1,
        active=flow.get('busy') and flow.get('stage') == 'assemble',
        failed=native.get('status') in ('failed', 'qc_failed'))
    # A stopped worker must not look like it is still generating a pending part.
    if not flow.get('busy') and flow.get('status') in ('paused', 'blocked'):
        stopped = next((s for s in steps if s['id'] == flow.get('stage') and s['state'] != 'complete'), None)
        if stopped and not any(s['state'] == 'blocked' for s in steps):
            stopped['state'] = 'blocked'
    active = next((s for s in steps if s['state'] == 'blocked'), None) or next((s for s in steps if s['state'] == 'running'), None)
    if not active:
        active = next((s for s in steps if s['state'] != 'complete'), steps[-1])
    total = sum(s['total'] for s in steps)
    completed = sum(s['completed'] for s in steps)
    return {'steps': steps, 'completed': completed, 'total': total,
            'percent': min(100 if native_ready and all(s['state'] == 'complete' for s in steps) else 99,
                           round(100*sum(fractions)/total)) if total else 0, 'current': active['id'],
            'images_received': image_received, 'images_total': len(images),
            'status': flow.get('status', job['status']), 'message': flow.get('message', job['progress']['message']),
            'updated_at': job.get('updated_at', job.get('created_at')), 'spec_id': job.get('production_spec', {}).get('id')}
