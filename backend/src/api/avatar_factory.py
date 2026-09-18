from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from src.services.object_storage import artifact_response as FileResponse
from pydantic import BaseModel, ConfigDict, Field

from src.auth import UserContext, get_current_user
from src.paths import data_root
from src.services.avatar_factory import AvatarFactory, PROFILE, _LOCK
from src.services.avatar_image_pipeline import AvatarImagePipeline, capabilities
from src.services.avatar_equipment import ImageSlot
from src.services.avatar_meshy import AvatarMeshy
from src.services.avatar_native_parts import AvatarNativeParts
from src.services.avatar_native_outfits import AvatarNativeOutfits
from src.services.avatar_stage_resume import AvatarStageResume, ensure_stage_idle

router = APIRouter(prefix='/avatar-factory', tags=['avatar-factory'])


@lru_cache
def get_factory():
    return AvatarFactory(data_root())


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    node_index: int = Field(ge=0)
    primitive_index: int = Field(ge=0)
    role: Literal['body', 'head', 'hair', 'hat', 'top', 'pants', 'skirt', 'dress', 'shoes', 'outfit_base', 'accessory', 'eyes', 'other']
    faces: list[int] = Field(min_length=1, max_length=500000)


class ProductionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    character_id: str = Field(min_length=1, max_length=100)
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    selections: list[Selection] = Field(default_factory=list, max_length=100)


class ImageProductionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    character_id: str = Field(min_length=1, max_length=100)
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    blueprint_revision: str = Field(min_length=1, max_length=100)
    production_mode: Literal['legacy', 'character_parts'] = 'legacy'
    view_mode: Literal['single', 'front_side'] = 'single'
    hair_length: Literal['source', 'short', 'long'] | None = None
    image_mode: Literal['generate', 'prepared'] = 'generate'
    slots: list[ImageSlot] = Field(default_factory=list, max_length=13)
    rig_with_meshy: bool = False
    body_purpose: Literal['whole_character', 'wardrobe_base'] = 'whole_character'
    motion_actions: dict[str, int] = Field(default_factory=dict, max_length=8)
    reuse_job_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{24}$')


class RecoverPartInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slot: ImageSlot
    task_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')


class RetryImageInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slot: ImageSlot
    view: Literal['front', 'side']
    failure_id: str = Field(pattern=r'^[a-f0-9]{12}$')


class RetryImagesInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    images: list[RetryImageInput] = Field(min_length=1, max_length=14)


class MotionDefaultsInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    selections: dict[str, int] = Field(max_length=8)


class MeshyMotionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slot: Literal['idle', 'walk', 'run', 'jump', 'fall', 'sit', 'armsUp', 'crouch']
    action_id: int = Field(ge=0, strict=True)


class MeshyRecoverInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    action_id: int | None = Field(default=None, ge=0, strict=True)


class NativeOutfitInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    slots: list[str] = Field(max_length=32)


@router.get('/motion-library')
def motion_library(user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return {'items': AvatarMeshy(factory).library(user.user_id)}


@router.get('/motion-defaults')
def motion_defaults(user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarMeshy(factory).defaults(user.user_id)


@router.put('/motion-defaults')
def save_motion_defaults(body: MotionDefaultsInput, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarMeshy(factory).defaults(user.user_id, body.selections)


@router.get('/jobs/{job_id}/meshy')
def meshy_state(job_id: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarMeshy(factory).get(user.user_id, job_id)


@router.get('/jobs/{job_id}/native-parts')
def native_parts(job_id: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarNativeParts(factory).get(user.user_id, job_id)


@router.post('/jobs/{job_id}/native-parts', status_code=202)
def fit_native_parts(job_id: str, background: BackgroundTasks, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarNativeParts(factory)
    with _LOCK:
        ensure_stage_idle(factory, user.user_id, job_id)
        state, created = service.start(user.user_id, job_id)
    if created:
        background.add_task(service.execute, user.user_id, job_id)
    return state


@router.get('/jobs/{job_id}/native-parts/{version}/{name}')
def native_parts_artifact(job_id: str, version: str, name: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return FileResponse(AvatarNativeParts(factory).artifact(user.user_id, job_id, version, name))


@router.get('/jobs/{job_id}/native-outfits/{version}')
def native_outfit(job_id: str, version: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarNativeOutfits(AvatarNativeParts(factory)).get(user.user_id, job_id, version)


@router.put('/jobs/{job_id}/native-outfits/{version}')
def save_native_outfit(job_id: str, version: str, body: NativeOutfitInput,
                      if_match: str = Header(alias='If-Match'), idempotency_key: str = Header(alias='Idempotency-Key'),
                      user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarNativeOutfits(AvatarNativeParts(factory)).put(
        user.user_id, job_id, version, body.model_dump(), if_match, idempotency_key)


@router.post('/jobs/{job_id}/meshy/rig', status_code=202)
def meshy_rig(job_id: str, background: BackgroundTasks, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarMeshy(factory)
    with _LOCK:
        ensure_stage_idle(factory, user.user_id, job_id)
        state = service.start(user.user_id, job_id)
    background.add_task(service.execute, user.user_id, job_id)
    return state


@router.post('/jobs/{job_id}/meshy/actions', status_code=202)
def meshy_action(job_id: str, body: MeshyMotionInput, background: BackgroundTasks,
                 user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarMeshy(factory)
    with _LOCK:
        ensure_stage_idle(factory, user.user_id, job_id)
        state = service.request_action(user.user_id, job_id, body.slot, body.action_id)
    background.add_task(service.execute, user.user_id, job_id)
    return state


@router.get('/jobs/{job_id}/meshy/artifacts/{version}/{name}')
def meshy_artifact(job_id: str, version: str, name: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return FileResponse(AvatarMeshy(factory).artifact(user.user_id, job_id, version, name))


@router.get('/jobs/{job_id}/meshy/provider/{name}')
def meshy_provider_artifact(job_id: str, name: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return FileResponse(AvatarMeshy(factory).provider_artifact(user.user_id, job_id, name))


@router.post('/jobs/{job_id}/meshy/recover')
def meshy_recover(job_id: str, body: MeshyRecoverInput, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarMeshy(factory).recover(user.user_id, job_id, body.task_id, body.action_id)


@router.post('/jobs/{job_id}/recover-task')
def recover_part(job_id: str, body: RecoverPartInput, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarImagePipeline(factory).recover_task(user.user_id, job_id, body.slot, body.task_id)


@router.get('/capabilities')
def provider_capabilities(user: UserContext = Depends(get_current_user)):
    return capabilities()


@router.post('/image-jobs', status_code=202)
def create_images(body: ImageProductionInput, background: BackgroundTasks, idempotency_key: str = Header(),
                  user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarImagePipeline(factory)
    job, created = service.create(user.user_id, idempotency_key, body.model_dump())
    if created:
        background.add_task(service.execute, user.user_id, job['id'])
    return job


@router.post('/jobs/{job_id}/resume', status_code=202)
def resume_images(job_id: str, background: BackgroundTasks, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    ensure_stage_idle(factory, user.user_id, job_id)
    current = factory.get(user.user_id, job_id)
    if current.get('production_mode') == 'character_parts' and current['status'] == 'review_required':
        from src.services.avatar_character_flow import continue_character
        background.add_task(continue_character, factory, user.user_id, job_id)
        return current
    service = AvatarImagePipeline(factory)
    job = service.resume(user.user_id, job_id)
    background.add_task(service.execute, user.user_id, job_id)
    return job


@router.get('/jobs/{job_id}/stages')
def factory_stages(job_id: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarStageResume(factory).get(user.user_id, job_id)


@router.post('/jobs/{job_id}/stages/{stage}/resume', status_code=202)
def resume_factory_stage(job_id: str, stage: Literal['images', 'models', 'rig', 'assemble'],
                         background: BackgroundTasks, idempotency_key: str = Header(alias='Idempotency-Key'),
                         user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarStageResume(factory)
    state, request_id = service.start(user.user_id, job_id, stage, idempotency_key)
    if request_id:
        background.add_task(service.execute, user.user_id, job_id, request_id)
    return state


@router.post('/jobs/{job_id}/retry-image', status_code=202)
def retry_image(job_id: str, body: RetryImageInput, background: BackgroundTasks,
                user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    ensure_stage_idle(factory, user.user_id, job_id)
    from src.services.avatar_image_recovery import retry_view
    service = AvatarImagePipeline(factory)
    job, created = retry_view(service, user.user_id, job_id, body.slot, body.view, body.failure_id)
    if created:
        background.add_task(service.execute, user.user_id, job_id)
    return job


@router.post('/jobs/{job_id}/retry-images', status_code=202)
def retry_images(job_id: str, body: RetryImagesInput, background: BackgroundTasks,
                 user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    ensure_stage_idle(factory, user.user_id, job_id)
    from src.services.avatar_image_recovery import retry_views
    service = AvatarImagePipeline(factory)
    job, created = retry_views(service, user.user_id, job_id, [image.model_dump() for image in body.images])
    if created:
        background.add_task(service.execute, user.user_id, job_id)
    return job


@router.get('/profiles')
def profiles(user: UserContext = Depends(get_current_user)):
    return {'profiles': [PROFILE]}


@router.post('/jobs/{job_id}/rebuild', status_code=202)
def rebuild_images(job_id: str, background: BackgroundTasks, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    ensure_stage_idle(factory, user.user_id, job_id)
    service = AvatarImagePipeline(factory)
    job = service.rebuild(user.user_id, job_id)
    background.add_task(service.execute, user.user_id, job['id'])
    return job


@router.get('/jobs')
def jobs(user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return {'jobs': factory.listing(user.user_id)}


@router.post('/jobs', status_code=202)
def create(body: ProductionInput, background: BackgroundTasks, idempotency_key: str = Header(),
           user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    job, created = factory.create(user.user_id, idempotency_key, body.model_dump())
    if created:
        background.add_task(factory.execute, user.user_id, job['id'])
    return job


@router.get('/jobs/{job_id}')
def job(job_id: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return factory.get(user.user_id, job_id)


@router.get('/jobs/{job_id}/artifacts/{filename}')
def artifact(job_id: str, filename: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return FileResponse(factory.artifact(user.user_id, job_id, filename))
