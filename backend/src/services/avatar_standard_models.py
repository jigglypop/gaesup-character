"""Versioned contracts for one reviewed body and its interchangeable parts.

Coordinates are glTF metres: X right, Y up, Z front. Images retain their
production canvas independently of provider crop/resize coordinates.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class BaseInput(Strict):
    character_id: str | None = Field(default=None, min_length=1, max_length=100)
    factory_job_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{24}$')
    factory_version: str | None = Field(default=None, pattern=r'^[a-f0-9]{24}$')
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    name: str = Field(min_length=1, max_length=80)
    height_m: float = Field(default=1.2, ge=.3, le=3)

    @model_validator(mode='after')
    def source_selection(self):
        if bool(self.character_id) == bool(self.factory_job_id) or bool(self.factory_job_id) != bool(self.factory_version):
            raise ValueError('등록한 캐릭터 또는 Meshy 공장 버전 하나를 선택하세요.')
        return self


class ReviewInput(Strict):
    model_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    decision: Literal['approved', 'changes_requested']
    bald_complete_body: bool = False
    neutral_apose: bool = False
    motion_checked: bool = False
    notes: str = Field(min_length=5, max_length=2000)


Vec3 = tuple[float, float, float]


class Anchor(Strict):
    name: str = Field(min_length=1, max_length=80)
    source: Vec3
    target: Vec3


class PartInput(Strict):
    name: str = Field(min_length=1, max_length=80)
    base_id: str = Field(pattern=r'^[a-f0-9]{24}$')
    base_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    model_asset: str = Field(pattern=r'^[a-f0-9]{64}$')
    shape_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{24}$')
    slot: Literal['hair', 'hat', 'top', 'bottom', 'shoeLeft', 'shoeRight', 'accessory']
    binding: Literal['rigid', 'transfer']
    bone: str | None = Field(default=None, max_length=120)
    garment_type: Literal['hair', 'hat', 'top', 'pants', 'skirt', 'shoe', 'boot', 'accessory']
    anchors: list[Anchor] = Field(min_length=3, max_length=24)
    max_anchor_error_m: float = Field(default=.02, gt=0, le=.1)
    max_transfer_distance_m: float = Field(default=.12, gt=0, le=.5)
    image_ids: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode='after')
    def binding_contract(self):
        if self.binding == 'rigid' and not self.bone:
            raise ValueError('단단한 파츠는 연결 본이 필요합니다.')
        if self.garment_type in ('pants', 'top', 'boot') and self.binding != 'transfer':
            raise ValueError('상의·바지·부츠는 공통 몸의 가중치를 전달해야 합니다.')
        if len({a.name for a in self.anchors}) != len(self.anchors):
            raise ValueError('착용 기준점 이름은 중복할 수 없습니다.')
        expected = {'hair': 'hair', 'hat': 'hat', 'top': 'top', 'pants': 'bottom',
                    'skirt': 'bottom', 'shoe': self.slot, 'boot': self.slot, 'accessory': 'accessory'}
        if self.slot != expected[self.garment_type] or (self.garment_type in ('shoe', 'boot') and self.slot not in ('shoeLeft', 'shoeRight')):
            raise ValueError('파츠 슬롯과 의상 유형이 일치하지 않습니다.')
        return self


class ImageInput(Strict):
    base_id: str = Field(pattern=r'^[a-f0-9]{24}$')
    base_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    image_asset: str = Field(pattern=r'^[a-f0-9]{64}$')
    object_key: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    view: Literal['front', 'side', 'back', 'other']
    # Left/top/width/height in the original 2048px canvas; no inferred landmarks.
    crop: tuple[int, int, int, int]
    export_size: int = Field(default=1024, ge=256, le=2048)

    @model_validator(mode='after')
    def crop_inside_canvas(self):
        x, y, w, h = self.crop
        if min(x, y) < 0 or min(w, h) < 1 or x+w > 2048 or y+h > 2048:
            raise ValueError('잘라내기 영역은 2048px 제작 캔버스 안이어야 합니다.')
        return self


class TextureSwap(Strict):
    material_index: int = Field(ge=0)
    part_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{24}$')
    image_asset: str = Field(pattern=r'^[a-f0-9]{64}$')
    uv_layout_confirmed: Literal[True]


class ShapeInput(Strict):
    name: str = Field(min_length=1, max_length=80)
    base_id: str = Field(pattern=r'^[a-f0-9]{24}$')
    base_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    image_ids: list[str] = Field(min_length=1, max_length=4)
    max_new_tasks: Literal[1] = 1


class TaskRecovery(Strict):
    task_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')


class DesignInput(Strict):
    name: str = Field(min_length=1, max_length=80)
    base_id: str = Field(pattern=r'^[a-f0-9]{24}$')
    base_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    object_key: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    view: Literal['front', 'side', 'back']
    description: str = Field(min_length=5, max_length=3000)
    reference_asset: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    identity_image_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{24}$')
    max_new_images: Literal[1] = 1


class ImageAnchor(Strict):
    name: str = Field(min_length=1, max_length=80)
    source: tuple[float, float]
    target: tuple[float, float]

    @model_validator(mode='after')
    def canvas_bounds(self):
        if any(v < 0 or v >= 2048 for v in (*self.source, *self.target)):
            raise ValueError('기준점은 2048px 캔버스 안이어야 합니다.')
        return self


class AlignDesignInput(Strict):
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    anchors: list[ImageAnchor] = Field(min_length=3, max_length=20)
    max_error_px: float = Field(default=8, gt=0, le=32)
    isolated_part_checked: Literal[True]
    same_object_checked: Literal[True]


class AssemblyInput(Strict):
    base_id: str = Field(pattern=r'^[a-f0-9]{24}$')
    base_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    part_ids: list[str] = Field(min_length=1, max_length=12)
    name: str = Field(min_length=1, max_length=80)
    textures: list[TextureSwap] = Field(default_factory=list, max_length=8)


class OutfitInput(Strict):
    base_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    part_ids: list[Annotated[str, Field(pattern=r'^[a-f0-9]{24}$')]] = Field(default_factory=list, max_length=12)


class BatchRow(Strict):
    key: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,60}$')
    name: str = Field(min_length=1, max_length=80)
    slot: Literal['hair', 'hat', 'top', 'bottom', 'shoeLeft', 'shoeRight', 'accessory']
    garment_type: Literal['hair', 'hat', 'top', 'pants', 'skirt', 'shoe', 'boot', 'accessory']
    description: str = Field(min_length=5, max_length=3000)

    @model_validator(mode='after')
    def slot_matches(self):
        allowed = {'hair': ['hair'], 'hat': ['hat'], 'top': ['top'], 'pants': ['bottom'],
                   'skirt': ['bottom'], 'shoe': ['shoeLeft', 'shoeRight'], 'boot': ['shoeLeft', 'shoeRight'], 'accessory': ['accessory']}
        if self.slot not in allowed[self.garment_type]:
            raise ValueError('의상 유형과 교체 슬롯이 일치하지 않습니다.')
        return self


class BatchInput(Strict):
    name: str = Field(min_length=1, max_length=80)
    base_id: str = Field(pattern=r'^[a-f0-9]{24}$')
    base_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    reference_asset: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    rows: list[BatchRow] = Field(min_length=1, max_length=16)
    max_images_per_row: Literal[1] = 1
    max_meshy_tasks_per_row: Literal[1] = 1

    @model_validator(mode='after')
    def unique_rows(self):
        if len({r.key for r in self.rows}) != len(self.rows):
            raise ValueError('배치 의상 식별자는 중복할 수 없습니다.')
        return self


def image_spec(height):
    return {'width': 2048, 'height': 2048, 'body_top_px': 300, 'sole_px': 1800,
            'center_x_px': 1024, 'body_height_m': height, 'pixels_per_meter': 1500/height,
            'orthographic_scale_m': 2048*height/1500, 'pose': 'source_rest_pose',
            'axes': 'glTF: X right, Y up, Z front', 'views': ['front', 'side', 'back']}
