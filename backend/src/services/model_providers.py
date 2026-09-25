"""3D provider selection and the Tripo multiview contract beside Meshy.

The provider is frozen per accepted request. Both providers receive the same
ordered views as short-lived URLs of the stored inputs; task receipts record the
provider so refresh, download and recovery never mix endpoints.
"""
import os

import httpx

from src.services.character_pipeline import PipelineError

PROVIDERS = ('meshy', 'tripo')
TRIPO_BASE = 'https://api.tripo3d.ai/v2/openapi'
TRIPO_MODEL = 'v3.1-20260211'
# Tripo task states -> the Meshy-style states the pipeline already understands.
TRIPO_STATUS = {'queued': 'PENDING', 'running': 'IN_PROGRESS', 'success': 'SUCCEEDED', 'failed': 'FAILED',
                'cancelled': 'CANCELED', 'banned': 'FAILED', 'expired': 'FAILED', 'unknown': 'IN_PROGRESS'}
TRIPO_ORDER = ('front', 'side', 'back', 'opposite')  # Tripo: [front, left, back, right]


def configured():
    return {'meshy': bool(os.getenv('MESHY_API_KEY', '').strip()),
            'tripo': bool(os.getenv('TRIPO_API_KEY', '').strip())}


def resolve_provider(requested=None):
    name = requested or os.getenv('AVATAR_3D_PROVIDER', 'meshy').strip().lower() or 'meshy'
    if name not in PROVIDERS:
        raise PipelineError('invalid_provider', '3D 생성 제공자를 다시 선택하세요.', 422)
    return name


def base_url(provider, state=None):
    if provider == 'tripo':
        return os.getenv('TRIPO_API_BASE_URL', TRIPO_BASE).rstrip('/')
    return ((state or {}).get('meshy_base') or os.getenv('MESHY_API_BASE_URL', 'https://api.meshy.ai')).rstrip('/')


def client(provider, state=None, *, timeout=120):
    key = os.getenv('TRIPO_API_KEY' if provider == 'tripo' else 'MESHY_API_KEY', '').strip()
    if not key:
        raise PipelineError('provider_unavailable', f'{provider} API 설정이 필요합니다.', 422)
    return httpx.Client(base_url=base_url(provider, state), headers={'Authorization': 'Bearer '+key}, timeout=timeout)


def tripo_payload(urls_by_view, *, face_limit=None, texture=True, pbr=True):
    """multiview_to_model body: four file slots [front, left, back, right]; front is required."""
    if 'front' not in urls_by_view:
        raise ValueError('Tripo multiview requires a front view')
    files = [({'type': 'png', 'url': urls_by_view[view]} if view in urls_by_view else {}) for view in TRIPO_ORDER]
    payload = {'type': 'multiview_to_model', 'model_version': os.getenv('TRIPO_MODEL_VERSION', TRIPO_MODEL),
               'files': files, 'texture': bool(texture), 'pbr': bool(pbr), 'texture_quality': 'standard',
               'geometry_quality': 'standard', 'orientation': 'default', 'auto_size': False}
    if face_limit:
        payload['face_limit'] = int(face_limit)
    return payload


def tripo_task_id(response_json):
    data = response_json.get('data') or {}
    if response_json.get('code') not in (0, None):
        return None
    return data.get('task_id')


def tripo_state(response_json):
    data = response_json.get('data') or {}
    return TRIPO_STATUS.get(str(data.get('status', 'unknown')).lower(), 'IN_PROGRESS'), data.get('progress')


def tripo_model_url(result_json):
    output = (result_json.get('data') or {}).get('output') or {}
    return output.get('pbr_model') or output.get('model') or output.get('base_model')
