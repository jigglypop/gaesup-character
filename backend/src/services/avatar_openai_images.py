"""One recorded OpenAI image edit per part. No retries or model fallback."""
import base64
from contextlib import closing
import hashlib
import io
import json
import os
from src.services.object_storage import StoredPath as Path
import re
import ssl
import time
import uuid

import httpx
from PIL import Image

from src.services.character_pipeline import PipelineError
from src.services.asset_editor import _write_json
from src.services.object_storage import provider_image

DEFAULT_MODEL = 'gpt-image-2.5-sunburst'
DEFAULT_BASE = 'https://api.openai.com/v1'
ERROR_RESPONSE_LIMIT = 64 * 1024


def image_transport():
    # Allow a verified TLS 1.2 connection on hosts with failing TLS 1.3 uploads.
    # Never retry an image POST or disable certificate/hostname verification.
    context = httpx.create_ssl_context()
    maximum = os.getenv('AVATAR_IMAGE_TLS_MAX_VERSION', 'auto').strip()
    if maximum == '1.2':
        context.maximum_version = ssl.TLSVersion.TLSv1_2
    elif maximum != 'auto':
        raise PipelineError('image_transport_config', '이미지 전송 설정 오류', 422)
    return httpx.HTTPTransport(verify=context, retries=2)


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
    if any(word in tokens for word in ('policy', 'safety', 'moderation')):
        return 'policy'
    if any(word in tokens for word in ('quota', 'billing', 'credit', 'budget')):
        return 'quota'
    if status_code in (401, 403) or any(word in tokens for word in ('auth', 'api_key', 'permission')):
        return 'auth'
    if status_code == 429 or 'rate_limit' in tokens:
        return 'rate_limit'
    if status_code >= 500:
        return 'provider_unavailable'
    if param == 'model' or 'model' in tokens:
        return 'model'
    if param == 'size' or any(word in tokens for word in ('size', 'dimension', 'resolution')):
        return 'size'
    if param in ('url', 'image_url') or param.endswith('.image_url') or any(
            word in tokens for word in ('invalid_image_url', 'image_download', 'image_fetch')):
        return 'reference_url'
    if status_code in (400, 404, 422) or 'invalid_request' in tokens:
        return 'invalid_request'
    return 'unknown'


def image_error_message(category, status_code=None):
    """User-facing reason from classified tokens, never provider prose or input URLs."""
    messages = {
        'policy': '이미지 안전 필터로 생성 중단',
        'auth': '이미지 서비스 인증·권한 오류',
        'quota': '이미지 생성 사용 한도 초과',
        'rate_limit': '이미지 요청이 많아 일시 중단',
        'provider_unavailable': '이미지 서비스 일시 오류',
        'model': '이미지 모델 사용 불가',
        'size': '지원하지 않는 이미지 크기',
        'reference_url': '참조 이미지 URL을 불러오지 못함',
        'invalid_request': '이미지 요청 형식 오류',
    }
    return messages.get(category, f'이미지 요청 실패 (HTTP {status_code})' if status_code else '이미지 요청 실패')


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
    details = parsed.get('moderation_details')
    if provider_error.get('code') == 'moderation_blocked' and isinstance(details, dict):
        # Keep only documented coarse labels, not raw provider text or classifier data.
        public_categories = {'harassment', 'harassment/threatening', 'hate', 'hate/threatening',
                             'sexual', 'sexual/minors', 'violence', 'violence/graphic',
                             'self-harm', 'self-harm/intent', 'self-harm/instructions', 'illicit', 'illicit/violent'}
        stage = details.get('moderation_stage')
        categories = details.get('categories')
        provider_error['moderation_details'] = {
            'moderation_stage': stage if stage in ('input', 'output', 'unknown') else 'unknown',
            'categories': [c for c in categories if isinstance(c, str) and c in public_categories][:16]
                          if isinstance(categories, list) else [],
        }
    return provider_error, {
        'body_bytes': total,
        'body_sha256': digest.hexdigest(),
        'body_truncated': total > ERROR_RESPONSE_LIMIT,
    }


def edit_response(client, base, key, payload, receipt=None, *, multipart=False, input_sha256=None, endpoint='/images/edits'):
    """Keep response bytes before decoding; a cached response never re-enters POST."""
    if endpoint not in ('/images/edits', '/images/generations') or (multipart and endpoint != '/images/edits'):
        raise ValueError('Unsupported image endpoint')
    receipt = Path(receipt) if receipt else None
    response_path = receipt.with_suffix('.response.json') if receipt else None
    error_path = receipt.with_suffix('.error.json') if receipt else None
    request_path = receipt.with_suffix('.request.json') if receipt else None
    if response_path and response_path.is_file():
        return json.loads(response_path.read_bytes())
    if error_path and error_path.is_file():
        saved = json.loads(error_path.read_bytes())
        raise OpenAIImageHTTPError(saved['http_status'], _error_category(saved['http_status'], saved.get('provider_error', {})),
                                   saved['diagnostic_id'], saved.get('provider_error'))
    previous = json.loads(request_path.read_bytes()) if request_path and request_path.is_file() else {}
    if previous and previous.get('submission') != 'not_sent':
        raise PipelineError('image_response_uncertain', '기존 이미지 요청의 접수 여부 확인 필요', 409)
    if multipart:
        fields = {k: str(v) for k, v in payload.items() if k != 'images'}
        uploads = []
        for index, item in enumerate(payload['images']):
            prefix, encoded = item['image_url'].split(';base64,', 1)
            mime = prefix.removeprefix('data:')
            content = base64.b64decode(encoded, validate=True)
            extension = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}[mime]
            uploads.append(('image[]', (f'reference-{index+1}.{extension}', content, mime)))
        request_args = {'data': fields, 'files': uploads}
    else:
        request_args = {'json': payload}
    started = time.monotonic()
    metadata = {'transport': 's3-regional-image-urls-v2' if input_sha256 else 'buffered-multipart-v4' if multipart else 'buffered-json-v3', 'endpoint': endpoint, 'model': payload['model'], 'n': payload['n'],
                'phase': 'prepared', 'events': [],
                'client_request_id': previous.get('client_request_id') or uuid.uuid4().hex, 'request_started': False}
    if input_sha256:
        metadata['input_sha256'] = input_sha256
    def record():
        if receipt:
            _write_json(receipt.with_suffix('.request.json'), metadata)
    def trace(event, info):
        # Persist event names only: trace payloads can contain credentials.
        metadata['transport_event'] = event
        metadata['events'].append({'event': event, 'at_seconds': round(time.monotonic()-started, 3)})
        if event == 'connection.start_tls.complete':
            stream = info.get('return_value')
            tls = stream.get_extra_info('ssl_object') if stream else None
            if tls:
                metadata['tls_version'] = tls.version()
                metadata['tls_cipher'] = tls.cipher()[0]
        if event.endswith('.failed'):
            metadata.setdefault('first_failed_event', event)
            metadata['failed_event'] = event
            failure = info.get('exception')
            metadata['transport_error_type'] = type(failure).__name__
            cause = failure
            for _ in range(5):
                if cause is None:
                    break
                if isinstance(getattr(cause, 'errno', None), int):
                    metadata['socket_errno'] = cause.errno
                reason = _safe_token(getattr(cause, 'reason', None))
                if reason:
                    metadata['tls_reason'] = reason
                cause = cause.__cause__ or cause.__context__
        if event.endswith('send_request_headers.started'):
            metadata.update(request_started=True, phase='sending')
        elif event.endswith('send_request_body.complete'):
            metadata['phase'] = 'awaiting_response'
            metadata['request_body_complete'] = True
        metadata['elapsed_seconds'] = round(time.monotonic()-started, 3)
        record()
    headers = {'Authorization': 'Bearer '+key, 'X-Client-Request-Id': metadata['client_request_id']}
    if multipart:
        headers['Content-Type'] = 'multipart/form-data; boundary=factory-'+metadata['client_request_id']
    request = client.build_request('POST', base.rstrip('/')+endpoint, headers=headers,
                                   extensions={'trace': trace}, **request_args)
    # Finish encoding before opening the connection. Send a single replayable byte
    # stream, rather than interleaving multipart encoding with network writes.
    content = request.read()
    request.headers['Content-Length'] = str(len(content))
    request.headers.pop('Transfer-Encoding', None)
    metadata.update(request_bytes=len(content), request_sha256=hashlib.sha256(content).hexdigest())
    # Expiring S3 signatures may change only for a definitely unsent request with
    # identical content-addressed images, prompt and generation settings.
    refreshed_urls = input_sha256 and input_sha256 == previous.get('input_sha256') and previous.get('submission') == 'not_sent'
    if previous.get('request_sha256') and previous['request_sha256'] != metadata['request_sha256'] and not refreshed_urls:
        raise PipelineError('image_request_changed', '저장된 이미지 요청 입력이 변경되었습니다.', 409)
    if previous:
        metadata['previous_connections'] = previous.get('previous_connections', []) + [
            {k: previous.get(k) for k in ('client_request_id', 'phase', 'submission', 'elapsed_seconds', 'socket_errno')}]
    record()
    try:
        with closing(client.send(request, stream=True)) as response:
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
        event = metadata.get('failed_event', '')
        not_sent = not metadata['request_started'] and (
            isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)) or
            event in ('connection.connect_tcp.failed', 'connection.start_tls.failed'))
        metadata['submission'] = 'not_sent' if not_sent else 'rejected' if isinstance(exc, OpenAIImageHTTPError) else 'unknown'
        cause = exc.__cause__
        if cause is not None:
            metadata['cause_type'] = type(cause).__name__
        record()
        raise


def reference_data_url(source):
    """Keep the source untouched; bound the full-character request upload."""
    with Image.open(io.BytesIO(Path(source).read_bytes())) as reference:
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


def generate_standard_part_image(references, prompt, model, base, *, receipt=None, canvas_size=(2048, 2048)):
    """One 2048px edit using the frozen body view plus optional art reference."""
    saved = Path(receipt).with_suffix('.response.json') if receipt else None
    if saved and saved.is_file():
        return standard_image_bytes(json.loads(saved.read_bytes()))
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        raise PipelineError('image_provider_unavailable', 'OpenAI 이미지 생성 키가 필요합니다.', 422)
    images = []; remote = []
    for path in references:
        if Path(path).name == 'source.png':
            # Appearance reference only; measured guides and accepted views retain full resolution.
            data_url = reference_data_url(path)
            images.append({'image_url': data_url})
            prefix, encoded = data_url.split(';base64,', 1)
            remote.append(provider_image(path, base64.b64decode(encoded), prefix.removeprefix('data:')))
            continue
        with Image.open(io.BytesIO(Path(path).read_bytes())) as image:
            normalized = io.BytesIO(); image.convert('RGBA').save(normalized, format='WEBP', lossless=True)
        images.append({'image_url': 'data:image/webp;base64,'+base64.b64encode(normalized.getvalue()).decode('ascii')})
        remote.append(provider_image(path, normalized.getvalue(), 'image/webp'))
    payload = {'model': model, 'prompt': prompt, 'n': 1, 'size': f'{canvas_size[0]}x{canvas_size[1]}', 'quality': 'high',
               'background': 'transparent', 'output_format': 'png', 'images': images}
    input_sha256 = None
    if remote and all(remote):
        contract = {**payload, 'images': [item['identity'] for item in remote]}
        input_sha256 = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
        payload['images'] = [{'image_url': item['url']} for item in remote]
    with httpx.Client(timeout=httpx.Timeout(600, connect=15, write=60, pool=15),
                      transport=image_transport()) as client:
        response = edit_response(client, base, key, payload, receipt,
                                 multipart=not bool(input_sha256), input_sha256=input_sha256)
    return standard_image_bytes(response)


def standard_image_bytes(response):
    items = response.get('data', [])
    if len(items) != 1 or not items[0].get('b64_json'):
        raise PipelineError('image_missing', '이미지 한 장이 반환되지 않았습니다. 자동 재요청하지 않습니다.', 422)
    raw = base64.b64decode(items[0]['b64_json'], validate=True)
    with Image.open(io.BytesIO(raw)) as image:
        if max(image.size) > 4096 or image.width * image.height > 16_777_216:
            raise PipelineError('canvas_mismatch', '응답 이미지가 허용한 크기를 초과했습니다. 자동 재생성하지 않습니다.', 422)
        image.verify()
    return raw


def generate_image(prompt, model, base, *, receipt, background='opaque'):
    """One prompt-only image request with the same durable response contract."""
    if background not in ('opaque', 'transparent'):
        raise ValueError('Unsupported image background')
    saved = Path(receipt).with_suffix('.response.json')
    if saved.is_file():
        return standard_image_bytes(json.loads(saved.read_bytes()))
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        raise PipelineError('image_provider_unavailable', 'OpenAI 이미지 생성 키가 필요합니다.', 422)
    payload = {'model': model, 'prompt': prompt, 'n': 1, 'size': '1024x1024',
               'quality': 'high', 'output_format': 'png', 'background': background}
    with httpx.Client(timeout=httpx.Timeout(600, connect=15, write=60, pool=15), transport=image_transport()) as client:
        response = edit_response(client, base, key, payload, receipt, endpoint='/images/generations')
    return standard_image_bytes(response)


def generate_part_image(source, prompt, model, base, *, receipt=None):
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        raise PipelineError('image_provider_unavailable', 'OpenAI 이미지 생성 키가 필요합니다.', 422)
    reference = reference_data_url(source)
    with httpx.Client(timeout=httpx.Timeout(600, connect=15, write=60, pool=15),
                      transport=image_transport()) as client:
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
