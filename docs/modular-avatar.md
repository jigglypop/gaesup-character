# 모듈형 아바타

이 구현은 현재 저장소의 `backend/`와 `frontend/`에 있습니다. 설치된 `gaesup-world@1.0.30`, R3F 9.7, Three 0.178의 공개 API를 사용하며 다른 checkout의 소스에 의존하지 않습니다.

## 실행과 화면

루트에서 `uv run asset-dev`, 별도 터미널의 `frontend/`에서 `npm run dev`를 실행합니다. `http://127.0.0.1:5273/avatar.html` 또는 라이브러리의 **모듈형 아바타** 링크로 이동합니다.

기본 화면은 이미지 파츠 편집·생산입니다. `avatar.html?character=A`처럼 선택을 URL에 남깁니다. 얼굴, 앞·뒷머리, 모자, 상의, 하의, 신발을 각각 생성하고 공통 몸과 리그로 조립하는 [이미지 생산 파이프라인](avatar-image-pipeline.md)을 제공합니다. 기존 GLB 변환은 `?stage=glb`, 기존 스튜디오와 옷장은 `?view=wardrobe`에서 사용합니다.

옷장은 수동 테스트 카탈로그와 현재 사용자의 검증된 생산 버전을 함께 읽습니다. 기술 검사를 통과한 생산물도 외형 승인은 pending입니다. Tripo 어댑터와 외부 게임 배포는 연결하지 않았습니다.

API를 기본 8000 외의 포트에서 실행했다면 프론트 실행 전에 `$env:BACKEND_URL = 'http://127.0.0.1:62122'`처럼 지정합니다. 실행된 앱의 읽기 전용 검증은 `frontend/`에서 `npm run check:studio`로 수행합니다. 설치된 Chrome으로 실제 API·WebGPU 또는 호환 렌더러·캐릭터 GLB·모바일 너비를 확인하고 `test-results/studio-live/`에 화면과 결과를 남깁니다. 저장이나 생성 요청은 보내지 않습니다.

옷장에서 파츠를 선택하고 7개 동작으로 확인한 다음 **장착 저장**을 누릅니다. 새로고침하면 서버 상태를 복구합니다. 저장 응답이 유실되면 **저장 재시도**가 동일한 요청 키와 내용을 재전송합니다. **서버에서 불러오기**는 서버의 현재 조합으로 돌아갑니다. 실패한 파츠 로드는 기존 조합을 유지하고 화면에 오류를 표시합니다.

WebGPURenderer 초기화 후 R3F를 마운트합니다. 화면의 렌더러 표시는 실제 backend 값이며 WebGL fallback이면 호환 모드로 표시합니다.

## 코드와 계약

- `frontend/src/avatar/core/rig.json`: `gaesup-humanoid-v1`, `SD_NEUTRAL_V1`, A-pose, 23개 bone의 기준 위치와 계층.
- `frontend/src/avatar/core/types.ts`, `manifest.ts`: 14개 슬롯, 16개 몸 영역, node/primitive 인덱스, bone 매핑, attachment, LOD의 검증.
- `frontend/src/avatar/runtime/`: 하나의 master skeleton과 mixer, 원자적 파츠 교체, 소켓 결합, 애니메이션 매핑.
- `frontend/src/assets/GLTFAssetCache.ts`: 카탈로그 URL별 GLB 공유와 참조 수에 따른 해제. 인스턴스가 공유 geometry/material을 임의 해제하지 않습니다.
- `frontend/src/avatar/api.ts`: 기존 gaesup-world `SaveSystem`의 `avatar` 도메인과 HTTP adapter.
- `backend/src/services/avatar_catalog.py`: 번들 카탈로그, 파일 SHA-256 검증, 사용자별 장착 상태와 저장 요청 일지.

가져온 메시 이름으로 의상 역할을 추측하지 않습니다. `metadata.avatar`의 명시적 glTF node/primitive와 bone 인덱스를 사용합니다. source skin의 joint 순서를 기준 rig 순서로 매핑하고, rest pose와 inverse bind matrix, 정규화된 4개 weight를 검사합니다. 재매핑이 필요하면 인스턴스 geometry를 복제합니다. 검증 실패 시 새 리소스를 해제하고 이전 조합을 유지합니다.

모든 skinned part는 인스턴스의 동일한 skeleton을 참조합니다. hair/hat은 head bone, bag/hand는 back/handR socket에 연결합니다. 파츠 교체나 LOD 변경은 mixer를 재생성하지 않습니다. 원피스는 상하의를 해제하며, 몸 영역 숨김은 현재 장착된 모든 파츠의 mask 합집합입니다.

카탈로그는 기존 `useAssetStore`에 `kind: characterPart`로 등록합니다. 아바타의 구체적 종류와 확장 슬롯은 `metadata.avatar`에 둡니다. 설치된 라이브러리의 `AssetKind`/`AssetSlot`을 변경하지 않습니다.

```tsx
import { Avatar } from './avatar';

// 기존 useAssetStore에 검증한 카탈로그를 등록한 후, R3F/GaesupWorld 안에서:
<Avatar body="body-sd-neutral-v1"
  equipment={{ hair: 'hair-001', top: 'top-001' }}
  animation="idle"
  onReady={avatar => { /* await avatar.equip('top', 'top-002') */ }} />;
```

`AvatarProvider`, `useAvatar`, `useAvatarEquipment`, imperative `equip`, `unequip`, `restore`, `setLOD`도 공개합니다. `getState()`는 `{ body, equipment }`의 ID만 반환하므로 네트워크 payload로 직렬화할 수 있습니다. `getSnapshot()`은 읽기 전용 snapshot이며 실제 multiplayer transport는 아직 연결하지 않았습니다.

## API와 저장

| API | 내용 |
| --- | --- |
| `GET /api/avatars/catalog` | 수동 에셋 17종과 현재 사용자 생산 버전의 canonical manifest |
| `GET /api/avatars/assets/{id}/model?lod=0` | 해시 검증한 GLB, ETag, 인증된 파일 제공 |
| `GET /api/avatars/me` | 현재 인증 사용자의 revision과 ID-only 장착 상태 |
| `PUT /api/avatars/me` | `If-Match`, `Idempotency-Key`를 사용한 충돌 방지 저장 |

기존 인증 dependency와 오류 envelope를 사용합니다. 원자적 JSON 교체로 `ASSET_DATA_ROOT/avatars/{user_id}/equipment.json`에 현재 상태와 최근 128개 요청의 결과를 함께 저장합니다. 재시작 후 같은 파일을 읽습니다. 만료된 요청 키라도 이전 revision으로 새 상태를 덮어쓸 수 없습니다. 단일 API worker 운영 계약을 따릅니다. DB schema와 기존 `/api/world/*`는 변경하지 않습니다.

## fixture와 검증

`frontend/`에서 `npm run assets:avatar`로 재생성합니다. 개발 도구 `@gltf-transform/core`와 Khronos `gltf-validator`를 사용합니다. 원본 캐릭터 데이터는 읽거나 수정하지 않습니다.

`backend/assets/avatars/manual-v1/`의 17종, LOD 0/1 GLB 총 34개는 직접 작성한 단순 테스트 geometry입니다. `evidence.json`에 파일 크기·SHA-256·검증 결과를 기록합니다. Idle, Walk, Run, Jump, Sit, Arms Up, Crouch를 포함합니다. 이 파일은 Tripo/Meshy 출력이나 실제 의상 분리의 증거가 아니며 시각 승인은 pending입니다.

일반 검증은 루트 `uv run pytest -q`, `frontend/`의 `npm run build`, `npm run test:e2e`입니다. API 테스트는 소유자 분리·재시작 복원·충돌·변조 파일을 검사합니다. E2E는 실제 임시 API에 연결해 파츠 교체·rollback·skeleton 유지·공유 리소스·서로 독립된 애니메이션·mask 합집합·LOD·7개 동작·저장 응답 유실·새로고침·재접속을 검사합니다.

이 Windows 환경에서는 관리형 Python 실행 파일과 Playwright 번들 Chromium이 앱 제어에 막혀, 실행이 허용된 시스템 Python/Chrome으로 검증했습니다. 잠긴 바이너리나 보안 정책을 변경하지 않았습니다. 기존 uv 의존성은 다음과 같이 사용할 수 있습니다.

```powershell
# 저장소 루트
$env:PYTHONPATH = "$(Get-Location)/.venv/Lib/site-packages;$(Get-Location)/backend"
python -m pytest -q
# 시스템 Python으로 개발 API를 실행할 때:
python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000
```

```powershell
# 위 환경을 유지한 별도 테스트 터미널
$env:WORKSPACE_TEST_SYSTEM_PYTHON = '1'
$env:WORKSPACE_TEST_BROWSER = 'chrome'
$env:WORKSPACE_TEST_API_PORT = '62123' # 실행 중인 개발 API와 다른 포트
cd frontend
npm run test:e2e
```

## 후속 단계

이미지별 Meshy 생성과 Blender canonical compiler가 추가되었습니다. Tripo 자동 제출, VRM 일반 변환, 실제 multiplayer 전송, spring bone, KTX2, LOD 자동 거리 정책과 inventory 연결은 후속 단계입니다. 자동 fitting과 weight는 검수 후보이며 출처/해시·기술 검증과 외형 승인을 따로 기록합니다.
