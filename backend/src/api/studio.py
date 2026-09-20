from typing import Literal
from fastapi import APIRouter, Depends, Header, Request, BackgroundTasks
from pydantic import BaseModel, ConfigDict, Field
from src.auth import UserContext, get_current_user
from src.api.avatar_factory import get_factory
from src.services.studio_library import StudioLibrary
from src.services.object_storage import artifact_response
from src.services.animal_rig import AnimalRig
from src.services.character_pipeline import PipelineError
from src.services.avatar_expressions import AvatarExpressions
from src.services.avatar_equipment import ImageSlot
from src.services.studio_generations import StudioGenerations
from src.services.avatar_expression_generation import AvatarExpressionGeneration
from src.services.avatar_expression_references import AvatarExpressionReferences
from src.services.avatar_expression_batches import AvatarExpressionBatches
from src.services.studio_prompts import StudioPrompts

router = APIRouter(prefix='/studio', tags=['studio'])


class PromptInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: str = Field(min_length=1, max_length=64)
    changes: dict[str, str | None] = Field(min_length=1, max_length=40)


@router.get('/prompts')
def prompts(user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioPrompts(factory, user.user_id).listing()


@router.put('/prompts')
def save_prompts(body: PromptInput, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioPrompts(factory, user.user_id).save(body.changes, body.revision)


class MetadataInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    archived: bool = False


class PartMetadataInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=80)
    deleted: bool | None = None


class VisibilityInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope: Literal['character', 'version']
    deleted: bool


class TextureInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    surface: Literal['snow', 'sand', 'grass', 'soil', 'stone', 'wood', 'bark', 'brick']
    size: Literal[256, 512, 1024] = 512
    seed: int = Field(ge=0, le=2147483647)


class GenerationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['prop', 'texture', 'illustration']
    category: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=8000)
    size: Literal[256, 512, 1024] = 512
    reference_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{24}$')


class IllustrationSelectionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    generation_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{24}$')
    revision: str = Field(min_length=1, max_length=64)


@router.get('/generations')
def generations(kind: Literal['prop', 'texture', 'illustration'], user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioGenerations(factory, user.user_id).listing(kind)


@router.get('/generations/{job_id}')
def generation(job_id: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioGenerations(factory, user.user_id).get(job_id)


@router.post('/generations', status_code=202)
def generate_asset(body: GenerationInput, background: BackgroundTasks, idempotency_key: str = Header(alias='Idempotency-Key'),
                   user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = StudioGenerations(factory, user.user_id)
    record, dispatch = service.create(idempotency_key, body.model_dump())
    if dispatch:
        background.add_task(service.execute, record['id'])
    return record


@router.post('/generations/{job_id}/resume', status_code=202)
def resume_asset(job_id: str, background: BackgroundTasks,
                 user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = StudioGenerations(factory, user.user_id)
    record, dispatch = service.resume(job_id)
    if dispatch:
        background.add_task(service.execute, job_id)
    return record


@router.get('/generations/{job_id}/artifacts/{name}')
def generation_artifact(job_id: str, name: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return artifact_response(StudioGenerations(factory, user.user_id).artifact(job_id, name))


@router.get('/illustration-selection')
def illustration_selection(user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioGenerations(factory, user.user_id).illustration_selection()


@router.put('/illustration-selection')
def select_illustration(body: IllustrationSelectionInput, user: UserContext = Depends(get_current_user),
                        factory=Depends(get_factory)):
    return StudioGenerations(factory, user.user_id).select_illustration(body.generation_id, body.revision)


class FaceLayout(BaseModel):
    model_config = ConfigDict(extra='forbid')
    eye: float = Field(ge=.3, le=.85)
    mouth: float = Field(ge=.5, le=.98)
    spacing: float = Field(ge=.1, le=.35)
    size: float = Field(ge=.5, le=1.5)


class ExpressionMap(BaseModel):
    model_config = ConfigDict(extra='forbid')
    material: int = Field(ge=0, le=255)
    png: str = Field(min_length=20, max_length=6000000)


class ExpressionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    name: Literal['neutral', 'smile', 'cry', 'angry', 'surprise', 'blink']
    layout: FaceLayout
    maps: list[ExpressionMap] = Field(min_length=1, max_length=32)


class ExpressionSelectionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expression_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{24}$')
    revision: str | None = Field(default=None, max_length=64)


class ExpressionGenerationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: Literal['neutral', 'smile', 'cry', 'angry', 'surprise', 'blink']
    prompt: str = Field(min_length=1, max_length=4000)
    reference_assets: list[str] | None = Field(default=None, min_length=1, max_length=3)


class ExpressionReferenceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: str = Field(min_length=1, max_length=64)
    assets: list[str] = Field(max_length=3)


class ExpressionBatchInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reference_assets: list[str] = Field(min_length=1, max_length=3)


class ExpressionOverlayInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    asset_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    name: Literal['neutral', 'smile', 'cry', 'angry', 'surprise', 'blink']


@router.get('/bodies/{job_id}/{version}/expressions')
def expressions(job_id: str, version: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarExpressions(factory, user.user_id, job_id, version).listing()


@router.post('/bodies/{job_id}/{version}/expressions/head-parts')
def derive_expression_heads(job_id: str, version: str, user: UserContext = Depends(get_current_user),
                            factory=Depends(get_factory)):
    AvatarExpressions(factory, user.user_id, job_id, version)
    raise PipelineError('head_replacement_removed', '머리 분리 대신 현재 몸에 표정 텍스처를 적용하세요.', 410)


@router.get('/bodies/{job_id}/{version}/expression-heads/{name}')
def expression_base_head_artifact(job_id: str, version: str, name: Literal['body-without-head.glb', 'base-head.glb'],
                                  user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    from src.services.avatar_expression_heads import AvatarExpressionHeads
    return artifact_response(AvatarExpressionHeads(factory, user.user_id, job_id, version).artifact(None, name))


@router.get('/bodies/{job_id}/{version}/expression-heads/{expression_id}/head.glb')
def expression_head_artifact(job_id: str, version: str, expression_id: str,
                             user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    from src.services.avatar_expression_heads import AvatarExpressionHeads
    return artifact_response(AvatarExpressionHeads(factory, user.user_id, job_id, version).artifact(expression_id, 'head.glb'))


@router.post('/bodies/{job_id}/{version}/expressions')
def save_expression(job_id: str, version: str, body: ExpressionInput,
                    user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarExpressions(factory, user.user_id, job_id, version).save(body.model_dump())


@router.put('/bodies/{job_id}/{version}/expressions/selection')
def select_expression(job_id: str, version: str, body: ExpressionSelectionInput,
                      user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarExpressions(factory, user.user_id, job_id, version).select(body.expression_id, body.revision)


@router.post('/bodies/{job_id}/{version}/expressions/overlay')
def apply_expression_overlay(job_id: str, version: str, body: ExpressionOverlayInput,
                             user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarExpressions(factory, user.user_id, job_id, version).save_overlay(body.asset_id, body.name)


@router.get('/bodies/{job_id}/{version}/expression-generations')
def expression_generations(job_id: str, version: str, user: UserContext = Depends(get_current_user),
                           factory=Depends(get_factory)):
    return AvatarExpressionGeneration(factory, user.user_id, job_id, version).listing()


@router.put('/bodies/{job_id}/{version}/expression-reference')
def save_expression_reference(job_id: str, version: str, body: ExpressionReferenceInput,
                              user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    AvatarExpressionGeneration(factory, user.user_id, job_id, version)
    return AvatarExpressionReferences(factory, user.user_id, job_id).save(body.assets, body.revision)


@router.post('/bodies/{job_id}/{version}/expression-generations/batch', status_code=202)
def generate_expression_batch(job_id: str, version: str, body: ExpressionBatchInput,
                              background: BackgroundTasks, idempotency_key: str = Header(alias='Idempotency-Key'),
                              user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarExpressionBatches(AvatarExpressionGeneration(factory, user.user_id, job_id, version))
    record, dispatch = service.create(idempotency_key, body.model_dump())
    if dispatch:
        background.add_task(service.execute, record['id'])
    return record


@router.post('/bodies/{job_id}/{version}/expression-generations/batch/{batch_id}/resume', status_code=202)
def resume_expression_batch(job_id: str, version: str, batch_id: str, background: BackgroundTasks,
                            user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarExpressionBatches(AvatarExpressionGeneration(factory, user.user_id, job_id, version))
    record, dispatch = service.resume(batch_id)
    if dispatch:
        background.add_task(service.execute, record['id'])
    return record


@router.post('/bodies/{job_id}/{version}/expression-generations', status_code=202)
def generate_expression(job_id: str, version: str, body: ExpressionGenerationInput,
                        background: BackgroundTasks, idempotency_key: str = Header(alias='Idempotency-Key'),
                        user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarExpressionGeneration(factory, user.user_id, job_id, version)
    record, dispatch = service.create(idempotency_key, body.model_dump(), require_reference=True)
    if dispatch:
        background.add_task(service.execute, record['id'])
    return record


@router.get('/bodies/{job_id}/{version}/expression-generations/{generation_id}')
def expression_generation(job_id: str, version: str, generation_id: str,
                          user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarExpressionGeneration(factory, user.user_id, job_id, version).get(generation_id)


@router.post('/bodies/{job_id}/{version}/expression-generations/{generation_id}/resume', status_code=202)
def resume_expression_generation(job_id: str, version: str, generation_id: str, background: BackgroundTasks,
                                 user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarExpressionGeneration(factory, user.user_id, job_id, version)
    record, dispatch = service.resume(generation_id)
    if dispatch:
        background.add_task(service.execute, generation_id)
    return record


@router.get('/bodies/{job_id}/{version}/expression-generations/{generation_id}/artifacts/{name}')
def expression_generation_artifact(job_id: str, version: str, generation_id: str, name: str,
                                   user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarExpressionGeneration(factory, user.user_id, job_id, version)
    return artifact_response(service.artifact(generation_id, name))


@router.post('/bodies/{job_id}/{version}/expression-generations/{generation_id}/bake')
def bake_expression_generation(job_id: str, version: str, generation_id: str,
                               user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service = AvatarExpressionGeneration(factory, user.user_id, job_id, version)
    generation = service.get(generation_id)
    if generation['status'] != 'complete':
        raise PipelineError('expression_not_ready', '수신을 마친 표정 이미지가 필요합니다.', 409)
    return AvatarExpressions(factory, user.user_id, job_id, version).save_generated(
        service.artifact(generation_id, 'face.png'), generation['name'])


@router.get('/bodies/{job_id}/{version}/expressions/{expression_id}/{name}')
def expression_artifact(job_id: str, version: str, expression_id: str, name: str,
                        user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return artifact_response(AvatarExpressions(factory, user.user_id, job_id, version).artifact(expression_id, name))


@router.get('/catalog')
def catalog(user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioLibrary(factory, user.user_id).metadata()


@router.put('/catalog/{job_id}')
def save_metadata(job_id: str, body: MetadataInput, if_match: str = Header(),
                  user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioLibrary(factory, user.user_id).save(job_id, body.name, body.archived, if_match)


@router.patch('/catalog/{job_id}/parts/{slot}')
def save_part_metadata(job_id: str, slot: ImageSlot, body: PartMetadataInput, if_match: str = Header(),
                       user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioLibrary(factory, user.user_id).save_part(job_id, slot, body.model_dump(exclude_unset=True), if_match)


@router.patch('/catalog/{job_id}/visibility')
def save_visibility(job_id: str, body: VisibilityInput, if_match: str = Header(),
                    user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioLibrary(factory, user.user_id).save_visibility(job_id, body.scope, body.deleted, if_match)


@router.get('/textures')
def textures(user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioLibrary(factory, user.user_id).textures()


@router.post('/textures')
def generate_texture(body: TextureInput, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return StudioLibrary(factory, user.user_id).generate_texture(body.model_dump())


@router.get('/textures/{texture_id}/{name}')
def texture_artifact(texture_id: str, name: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return artifact_response(StudioLibrary(factory, user.user_id).artifact(texture_id, name))


@router.get('/animals')
def animals(user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AnimalRig(factory, user.user_id).listing()


@router.post('/animals')
async def upload_animal(request: Request, species: Literal['dog','cat','dragon'], name: str,
                        user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    if not name.strip() or len(name)>80:
        raise PipelineError('invalid_name','이름은 1~80자로 입력하세요.',422)
    content=bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content)>64*1024*1024:
            raise PipelineError('file_too_large','GLB는 64MB 이내로 올려 주세요.',413)
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(AnimalRig(factory,user.user_id).upload,bytes(content),species,name.strip())


@router.post('/animals/{animal_id}/rig', status_code=202)
def rig_animal(animal_id: str, background: BackgroundTasks,
               user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    service=AnimalRig(factory,user.user_id)
    record,created=service.start(animal_id)
    if created or record['status'] == 'accepted':
        background.add_task(service.execute,animal_id)
    return record


@router.get('/animals/{animal_id}/{name}')
def animal_artifact(animal_id: str, name: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return artifact_response(AnimalRig(factory,user.user_id).artifact(animal_id,name))
