"""Authenticated, owner-scoped fixed-body production API."""
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from src.auth import UserContext, get_current_user
from src.paths import data_root
from src.services.avatar_standard import AvatarStandard
from src.services.avatar_standard_models import BaseInput, PartInput, AssemblyInput, ReviewInput, ImageInput, ShapeInput, TaskRecovery, DesignInput, AlignDesignInput, BatchInput, OutfitInput
from src.services.avatar_standard_batch import WardrobeBatch
from src.services.avatar_standard_outfits import AvatarStandardOutfits
from src.services import avatar_standard_provider, avatar_standard_design
from src.services.character_pipeline import PipelineError

router = APIRouter(prefix='/avatar-standard', tags=['avatar-standard'])


@lru_cache
def get_standard():
    return AvatarStandard(data_root())


@router.get('/batches')
def batches(user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return {'items': WardrobeBatch(service).listing(user.user_id)}


@router.post('/batches', status_code=202)
def create_batch(body: BatchInput, background: BackgroundTasks, idempotency_key: str = Header(),
                 user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    batches = WardrobeBatch(service)
    item, created = batches.create(user.user_id, idempotency_key, body.model_dump())
    if created:
        background.add_task(batches.execute, user.user_id, item['id'])
    return item


@router.get('/batches/{item}')
def batch_detail(item: str, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return WardrobeBatch(service).public(user.user_id, item)


@router.get('/batches/{item}/reference')
def batch_reference(item: str, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return FileResponse(WardrobeBatch(service).reference(user.user_id, item), media_type='image/png')


@router.post('/batches/{item}/resume', status_code=202)
def batch_resume(item: str, background: BackgroundTasks, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    batches = WardrobeBatch(service)
    value = batches.public(user.user_id, item)
    if not value['can_resume']:
        raise PipelineError('worker_active', '배치 실행이 진행 중입니다.', 409)
    background.add_task(batches.execute, user.user_id, item)
    return value


@router.get('/items')
def items(user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return {'items': service.listing(user.user_id)}


@router.get('/outfits/{base_id}')
def outfit(base_id: str, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return AvatarStandardOutfits(service).get(user.user_id, base_id)


@router.put('/outfits/{base_id}')
def save_outfit(base_id: str, body: OutfitInput, if_match: str = Header(), idempotency_key: str = Header(),
                user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return AvatarStandardOutfits(service).put(
        user.user_id, base_id, body.model_dump(), if_match, idempotency_key
    )


@router.post('/uploads/{kind}', status_code=201)
async def upload(kind: Literal['glb', 'png'], request: Request,
                 user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 25*1024*1024:
            raise PipelineError('upload_too_large', '파일은 25MB 이하로 준비해 주세요.', 413)
    return await run_in_threadpool(service.upload, user.user_id, bytes(content), kind)


def accept(kind, body, background, key, user, service):
    item, created = service.create(user.user_id, kind, key, body.model_dump())
    if created:
        background.add_task(service.execute, user.user_id, item['id'])
    return item


@router.post('/bases', status_code=202)
def base(body: BaseInput, background: BackgroundTasks, idempotency_key: str = Header(),
         user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return accept('base', body, background, idempotency_key, user, service)


@router.post('/parts', status_code=202)
def part(body: PartInput, background: BackgroundTasks, idempotency_key: str = Header(),
         user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return accept('part', body, background, idempotency_key, user, service)


@router.post('/assemblies', status_code=202)
def assembly(body: AssemblyInput, background: BackgroundTasks, idempotency_key: str = Header(),
             user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return accept('assembly', body, background, idempotency_key, user, service)


@router.post('/images', status_code=201)
def image(body: ImageInput, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return service.image(user.user_id, body.model_dump())


@router.post('/shapes', status_code=202)
def shape(body: ShapeInput, background: BackgroundTasks, idempotency_key: str = Header(),
          user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    item, created = avatar_standard_provider.create(service, user.user_id, idempotency_key, body.model_dump())
    if created:
        background.add_task(avatar_standard_provider.execute, service, user.user_id, item['id'])
    return item


@router.post('/designs', status_code=202)
def design(body: DesignInput, background: BackgroundTasks, idempotency_key: str = Header(),
           user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    item, created = avatar_standard_design.create(service, user.user_id, idempotency_key, body.model_dump())
    if created:
        background.add_task(avatar_standard_design.execute, service, user.user_id, item['id'])
    return item


@router.post('/items/{item}/resume-design', status_code=202)
def resume_design(item: str, background: BackgroundTasks, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    value = service.public(user.user_id, item)
    if value['kind'] != 'design' or 'resume_design' not in value['next_actions']:
        raise PipelineError('action_unavailable', '현재 시안 생성 기록을 이어갈 수 없습니다.', 409)
    background.add_task(avatar_standard_design.execute, service, user.user_id, item)
    return value


@router.post('/items/{item}/align-design', status_code=201)
def align_design(item: str, body: AlignDesignInput, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return avatar_standard_design.align(service, user.user_id, item, body.model_dump())


@router.post('/items/{item}/poll')
def poll(item: str, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return avatar_standard_provider.execute(service, user.user_id, item, poll=True)


@router.post('/items/{item}/resume-submission', status_code=202)
def resume_submission(item: str, background: BackgroundTasks, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    value = service.public(user.user_id, item)
    if value['kind'] != 'shape' or 'resume_submission' not in value['next_actions']:
        raise PipelineError('action_unavailable', '새 제출을 실행할 수 없는 상태입니다.', 409)
    background.add_task(avatar_standard_provider.execute, service, user.user_id, item)
    return value


@router.post('/items/{item}/recover-task')
def recover_task(item: str, body: TaskRecovery, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return avatar_standard_provider.execute(service, user.user_id, item, poll=True, task_id=body.task_id)


@router.post('/items/{item}/review')
def review(item: str, body: ReviewInput, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return service.review(user.user_id, item, body.model_dump())


@router.post('/items/{item}/recover')
def recover(item: str, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return service.recover(user.user_id, item)


@router.get('/items/{item}')
def detail(item: str, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return service.public(user.user_id, item)


@router.get('/items/{item}/artifacts/{filename}')
def artifact(item: str, filename: str, user: UserContext = Depends(get_current_user), service=Depends(get_standard)):
    return FileResponse(service.artifact(user.user_id, item, filename))
