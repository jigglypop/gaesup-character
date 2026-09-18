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

router = APIRouter(prefix='/studio', tags=['studio'])


class MetadataInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    archived: bool = False


class TextureInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    surface: Literal['snow', 'sand', 'grass', 'soil', 'stone']
    size: Literal[256, 512, 1024] = 512
    seed: int = Field(ge=0, le=2147483647)


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
    name: Literal['smile', 'cry', 'angry', 'surprise', 'blink']
    layout: FaceLayout
    maps: list[ExpressionMap] = Field(min_length=1, max_length=32)


@router.get('/bodies/{job_id}/{version}/expressions')
def expressions(job_id: str, version: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarExpressions(factory, user.user_id, job_id, version).listing()


@router.post('/bodies/{job_id}/{version}/expressions')
def save_expression(job_id: str, version: str, body: ExpressionInput,
                    user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return AvatarExpressions(factory, user.user_id, job_id, version).save(body.model_dump())


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
    if created:background.add_task(service.execute,animal_id)
    return record


@router.get('/animals/{animal_id}/{name}')
def animal_artifact(animal_id: str, name: str, user: UserContext = Depends(get_current_user), factory=Depends(get_factory)):
    return artifact_response(AnimalRig(factory,user.user_id).artifact(animal_id,name))
