"""One recorded OpenAI image edit per part. No retries or model fallback."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
import uuid

import httpx
from PIL import Image

from src.services.character_pipeline import PipelineError
from src.services.asset_editor import _write_json

DEFAULT_MODEL = 'gpt-image-2.5-sunburst'
DEFAULT_BASE = 'https://api.openai.com/v1'
ERROR_RESPONSE_LIMIT = 64 * 1024


class OpenAIImageHTTPError(httpx.HTTPStatusError):
    """HTTP rejection stripped of the provider request payload and credentials."""

    def __init__(self, status_code, category, diagnostic_id, provider_error=None):
        self.category = category
        self.diagnostic_id = diagnostic_id
        self.provider_error = provider_error or {}
        request = httpx.Request('POST', DEFAULT_BASE + '/images/edits')
        response = httpx.Response(status_code, request=request)
        super().__init__(f'OpenAI image request rejected; diagnostic {diagnostic_id}',
                         request=request, response=response)


def _safe_token(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.\-\[\]]{1,128}', value):
        return None
    return value


def _error_category(status_code, error):
    tokens = ' '.join(str(error.get(key) or '').lower() for key in ('code', 'type', 'param'))
    param = str(error.get('param') or '').lower()
    if status_code in (401, 403) or any(word in tokens for word in ('auth', 'api_key', 'permission')):
        return 'auth'
    if any(word in tokens for word in ('policy', 'safety', 'moderation')):
        return 'policy'
    if param == 'model' or 'model' in tokens:
        return 'model'
    if param == 'size' or any(word in tokens for word in ('size', 'dimension', 'resolution')):
        return 'size'
    if status_code in (400, 404, 422) or 'invalid_request' in tokens:
        return 'invalid_request'
    return 'unknown'


def _read_error_response(response):
    digest = hashlib.sha256()
    prefix = bytearray()
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        digest.update(chunk)
        if len(prefix) < ERROR_RESPONSE_LIMIT:
            prefix.extend(chunk[:ERROR_RESPONSE_LIMIT - len(prefix)])
    parsed = {}
    try:
        document = json.loads(prefix)
        parsed = document.get('error', {}) if isinstance(document, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    if not isinstance(parsed, dict):
        parsed = {}
    provider_error = {key: token for key in ('code', 'type', 'param')
                      if (token := _safe_token(parsed.get(key))) is not None}
    return provider_error, {
        'body_bytes': total,
        'body_sha256': digest.hexdigest(),
        'body_truncated': total > ERROR_RESPONSE_LIMIT,
    }


def edit_response(client, base, key, payload, receipt=None):
    """Keep response bytes before decoding; a cached response never re-enters POST."""
    receipt = Path(receipt) if receipt else None
    response_path = receipt.with_suffix('.response.json') if receipt else None
    error_path = receipt.with_suffix('.error.json') if receipt else None
    if response_path and response_path.is_file():
        return json.loads(response_path.read_bytes())
    if error_path and error_path.is_file():
        saved = json.loads(error_path.read_bytes())
        raise OpenAIImageHTTPError(saved['http_status'], saved.get('category', 'unknown'),
                                   saved['diagnostic_id'], saved.get('provider_error'))
    started = time.monotonic()
    metadata = {'transport': 'json-data-url-v2', 'model': payload['model'], 'n': payload['n'],
                'request_bytes': len(json.dumps(payload).encode()), 'phase': 'sending'}
    def record():
        if receipt:
            _write_json(receipt.with_suffix('.request.json'), metadata)
    record()
    try:
        with client.stream('POST', base.rstrip('/')+'/images/edits',
                           headers={'Authorization': 'Bearer '+key}, json=payload) as response:
            metadata.update(phase='response_headers', http_status=response.status_code,
                            request_id=response.headers.get('x-request-id'))
            record()
            if response.is_error:
                provider_error, body = _read_error_response(response)
                diagnostic_id = uuid.uuid4().hex[:12]
                category = _error_category(response.status_code, provider_error)
                error_record = {
                    'diagnostic_id': diagnostic_id,
                    'http_status': response.status_code,
                    'request_id': response.headers.get('x-request-id'),
                    'category': category,
                    'provider_error': provider_error,
                    **body,
                }
                metadata.update(phase='response_rejected', diagnostic_id=diagnostic_id,
                                provider_error=provider_error, provider_error_category=category,
                                response_bytes=body['body_bytes'], response_sha256=body['body_sha256'])
                if error_path:
                    _write_json(error_path, error_record)
                record()
                raise OpenAIImageHTTPError(response.status_code, category, diagnostic_id,
                                           provider_error)
            if response_path:
                partial = receipt.with_suffix('.response.partial')
                with partial.open('wb') as output:
                    for chunk in response.iter_bytes():
                        output.write(chunk)
                partial.replace(response_path)
                raw = response_path.read_bytes()
            else:
                raw = response.read()
            metadata.update(phase='response_saved', response_bytes=len(raw), elapsed_seconds=round(time.monotonic()-started, 3))
            record()
            return json.loads(raw)
    except Exception as exc:
        metadata.update(error_type=type(exc).__name__, elapsed_seconds=round(time.monotonic()-started, 3))
        record()
        raise


def reference_data_url(source):
    """Keep the source untouched; bound the full-character request upload."""
    with Image.open(source) as reference:
        image = reference.convert('RGBA')
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        normalized = io.BytesIO(); image.save(normalized, format='PNG')
        mime = 'image/png'
        if len(normalized.getvalue()) > 512_000:
            # The production prompt uses a plain white background. Flatten alpha
            # on white only in the transmitted reference, never in the source.
            background = Image.new('RGBA', image.size, 'white')
            background.alpha_composite(image)
            normalized = io.BytesIO()
            background.convert('RGB').save(normalized, format='JPEG', quality=90)
            mime = 'image/jpeg'
    return 'data:'+mime+';base64,'+base64.b64encode(normalized.getvalue()).decode('ascii')


def generate_standard_part_image(references, prompt, model, base, *, receipt=None):
    """One 2048px edit using the frozen body view plus optional art reference."""
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        raise PipelineError('image_provider_unavailable', 'OpenAI 이미지 생성 키가 필요합니다.', 422)
    images = []
    for index, path in enumerate(references):
        with Image.open(path) as image:
            normalized = io.BytesIO(); image.convert('RGBA').save(normalized, format='PNG')
        images.append({'image_url': 'data:image/png;base64,'+base64.b64encode(normalized.getvalue()).decode('ascii')})
    with httpx.Client(timeout=240) as client:
        response = edit_response(client, base, key,
            {'model': model, 'prompt': prompt, 'n': 1, 'size': '2048x2048', 'quality': 'high',
             'background': 'transparent', 'output_format': 'png', 'images': images}, receipt)
        items = response.get('data', [])
    if len(items) != 1 or not items[0].get('b64_json'):
        raise PipelineError('image_missing', '이미지 한 장이 반환되지 않았습니다. 자동 재요청하지 않습니다.', 422)
    raw = base64.b64decode(items[0]['b64_json'], validate=True)
    with Image.open(io.BytesIO(raw)) as image:
        if max(image.size) > 4096 or image.width * image.height > 16_777_216:
            raise PipelineError('canvas_mismatch', '응답 이미지가 허용한 크기를 초과했습니다. 자동 재생성하지 않습니다.', 422)
        image.verify()
    return raw


def generate_part_image(source, prompt, model, base, *, receipt=None):
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        raise PipelineError('image_provider_unavailable', 'OpenAI 이미지 생성 키가 필요합니다.', 422)
    reference = reference_data_url(source)
    with httpx.Client(timeout=180) as client:
        result = edit_response(client, base, key,
            {'model': model, 'prompt': prompt, 'n': 1, 'size': '1024x1024',
                  'quality': 'high', 'output_format': 'png',
                  'images': [{'image_url': reference}]}, receipt)
        items = result.get('data', [])
    if len(items) != 1 or not items[0].get('b64_json'):
        raise PipelineError('image_missing', 'OpenAI가 파츠 이미지 한 장을 반환하지 않았습니다. 자동 재요청하지 않습니다.', 422)
    raw = base64.b64decode(items[0]['b64_json'], validate=True)
    with Image.open(io.BytesIO(raw)) as generated:
        if generated.width * generated.height > 32_000_000:
            raise ValueError('Image size limit')
        output = io.BytesIO()
        generated.convert('RGBA').save(output, format='PNG')
        return output.getvalue()
