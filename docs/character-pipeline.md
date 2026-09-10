# 이미지 캐릭터 → 의상 GLB 교체 → 리깅 파이프라인

`data/image/A.png`의 분홍 토끼 캐릭터로 실제 실행한 로컬 파이프라인이다. Meshy가 생성한 캐릭터를 Blender MCP로 처리하며, 별도 의상 GLB를 가져와 기존 뼈대의 가중치를 이전한다. FastAPI와 DB는 변경하지 않았으며 새 dependency도 추가하지 않았다.

## 현재 결과

- Meshy 생성 원본: `data/characters/A/generated.glb`
- A 전용 관절·의상 분리 설정: `data/characters/A/landmarks.json`
- 15개 뼈대와 교체용 원래 옷을 분리한 베이스: `data/characters/A/local-v3/base.glb`, `base.blend`
- 별도로 만든 기본형 스웨트셔츠: `data/characters/A/local-v3/sweatshirt.glb`
- 최신 착용 결과: `data/wardrobe/A-sweatshirt/run.json`의 `latest_fit.model`, `latest_fit.source`
- 렌더: `data/wardrobe/A-sweatshirt/preview-v2/rest.png`, `posed.png`
- 변형 검사: `data/wardrobe/A-sweatshirt/preview-v2/deformation.json`

이 모델은 Meshy 자동 리깅 요청이 HTTP 422로 거절되었다. Meshy 문서에서 422는 포즈 추정 실패를 의미한다. 따라서 이 샘플은 **Meshy 3D 생성 + Blender에서 작성한 관절 위치 기반 리깅** 경로로 완성했다. Meshy 리깅 성공 사례로 기록하지 않는다.

현재 결과는 `review_required`다. GLB 구조, 15개 관절, `pose_check` 클립 보존, 의상 전체 정점의 가중치 연결과 표본 프레임에서의 유한한 변형을 확인했다. `pose_check`는 팔·다리·머리를 움직이는 검사 클립이며 걷기 애니메이션이 아니다.

## 구성

```text
data/image/A.png
    ↓ Meshy Image-to-3D (기존 완료 작업 재사용)
generated.glb
    ├─ Meshy Rigging 성공 → rigged.glb / 제공되는 기본 애니메이션
    └─ 자동 리깅 실패 → landmarks.json + Blender MCP local-rig
                          ↓
              base.glb (character_body + outfit_base + CharacterRig)
                          ↓ wardrobe prepare
별도 의상.glb → wardrobe dress → 기존 의상 제외 + 가중치 이전
                          ↓
                  model.glb + source.blend
                          ↓ GLB 재수입·포즈 샘플링·렌더
                  quality.json + deformation.json
```

## 설치와 실행

프로젝트 루트의 PowerShell에서 실행한다. Python 환경은 `uv sync --extra blender`로 준비한다. `.env`의 `MESHY_API_KEY`는 Meshy 작업에만 필요하고 로컬 리깅과 의상 교체에는 필요하지 않다.

전용 Blender MCP 인스턴스를 시작한다. 아래 포트가 이미 실행 중이면 시작 명령을 다시 실행하지 않는다.

```powershell
uv run python -m src.editor_cli --root data/character-runtime --port 9880 start --blender 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
```

이미 받은 A 모델과 설정으로 리깅부터 재실행한다. 출력 폴더는 매번 새 이름을 사용한다. 기존 결과를 덮어쓰지 않는다.

```powershell
uv run python -m src.character_cli --run data/characters/A local-rig --port 9880 --recipe data/characters/A/landmarks.json --output data/characters/A/local-next
uv run python -m src.wardrobe_cli --run data/wardrobe/A-outfit-next --port 9880 prepare --base data/characters/A/local-next/base.glb --reference data/image/A.png --source-object outfit_base
uv run python -m src.wardrobe_cli --run data/wardrobe/A-outfit-next --port 9880 dress --garment data/characters/A/local-next/sweatshirt.glb --fit none
```

다른 옷을 입히려면 마지막 명령의 `--garment`를 **의상만 포함한 GLB** 경로로 바꾼다. 미리 맞춘 옷은 `--fit none`, 같은 방향과 포즈지만 크기만 다른 옷은 `--fit bounds`를 사용한다. `bounds`는 기존 의상의 바운딩 박스에 맞추는 초기 피팅이며 재봉 패턴이나 충돌 기반 피팅이 아니다. 매 교체는 원래 베이스에서 시작하므로 이전 옷이 누적되지 않는다.

`prepare --reference`는 기존 Meshy Retexture 경로와 상태 형식을 유지하기 위한 입력이다. 위의 별도 GLB 교체 경로는 `submit`을 호출하지 않으므로 이 이미지를 Meshy에 전송하지 않는다.

내보낸 결과를 다시 검사하고 렌더한다.

```powershell
$wardrobeRun = Get-Content data/wardrobe/A-outfit-next/run.json -Raw | ConvertFrom-Json
& 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe' --background --factory-startup --python-exit-code 1 --python backend/src/wardrobe_verify.py -- $wardrobeRun.latest_fit.model data/wardrobe/A-outfit-next/preview
```

Blender 실행 기록은 `data/character-runtime/blender-9880.json`과 `.log`에 남는다. 전용 인스턴스만 사용하며, 개인 작업 파일을 열어 둔 Blender에 연결하지 않는다.

## 다른 이미지로 Meshy 작업 시작

생성과 자동 리깅은 각각 외부 작업을 생성한다. 기존 A 작업을 중복 생성할 필요는 없다. 새로운 입력에는 새 run 경로를 사용한다.

```powershell
uv run python -m src.character_cli --run data/characters/B generate --image data/image/B.png --height 1.7
uv run python -m src.character_cli --run data/characters/B status
# SUCCEEDED가 될 때까지 status로 조회한 후:
uv run python -m src.character_cli --run data/characters/B download --stage generation
uv run python -m src.character_cli --run data/characters/B rig
uv run python -m src.character_cli --run data/characters/B status
# 리깅도 SUCCEEDED인 경우:
uv run python -m src.character_cli --run data/characters/B download --stage rigging
```

리깅 다운로드는 `rigged.glb`와 제공되는 경우 `walking.glb`, `running.glb`를 저장한다. URL이 만료되면 `status`로 새 결과를 받고 다시 다운로드한다. CDN 다운로드에는 Meshy API 키를 보내지 않는다. 잘못된 GLB는 기존 파일을 교체하기 전에 거절한다.

전송 응답을 잃은 작업은 `submission_uncertain`으로 남으며 자동으로 POST를 반복하지 않는다. Meshy의 해당 **list tasks API**에서 ID를 찾고 `status --task-id ID`로 복구한다. API 작업은 웹 앱 My Assets에서 보이지 않을 수 있다. 400/401/402/403/404/422/429의 명시적 거절은 `submission_rejected`와 HTTP 코드를 남긴다. A의 422처럼 포즈 추정에 실패하면 이미지·모델 개선 또는 로컬 리깅이 필요하다.

## 관절·의상 설정 작성

`landmarks.json`은 Blender에 가져온 월드 좌표를 사용한다. A의 좌표는 바닥 기준 정규화 좌표나 미터 단위로 재스케일한 좌표가 아니다. `generate --height`는 Meshy 리깅에 전달할 키이며, 로컬 경로는 원본 GLB 좌표를 보존한다.

- `model_sha256`: 이 설정을 만든 원본 GLB의 해시. 다른 생성 결과에 실수로 적용하지 못하게 검사한다.
- `bones`: 부모가 먼저 나오는 관절 목록과 head/tail 위치.
- `weight_regions`: 순서대로 검사하는 영역과 사용할 뼈. 후보 뼈까지의 거리로 최대 4개 가중치를 정규화한다.
- `default_bone`: 다른 영역에 속하지 않는 정점의 뼈. A에서는 큰 머리와 긴 머리카락을 `head`에 연결한다.
- `garment_regions`: 면 중심이 영역 안에 있으면 원래 옷으로 분리한다. AI 의미 분할이 아니므로 경계와 머리카락 혼입을 Blender에서 확인해야 한다.
- `pose_check`: 검사 클립에서 움직일 관절과 회전 각도.
- `sweater_tubes`: 선택적인 기본 의상 생성용 단면들. 생략하고 직접 만든 별도 의상 GLB를 사용할 수 있다.

다른 캐릭터를 생성하면 해당 모델에서 관절과 분리 영역을 다시 작성해야 한다. A의 설정을 해시만 바꿔 재사용하면 안 된다. 이미 리깅된 GLB는 기존 뼈대 보존을 위해 `local-rig`에서 거절하며, Blender에서 옷 오브젝트를 준비한 뒤 `wardrobe prepare`에 연결한다.

## 품질 범위와 남은 작업

샘플 스웨트셔츠는 파이프라인 검증용 기본형이다. 실제 후드·지퍼·주머니·봉제선·재질 디테일을 가진 완성 의상은 별도 제작해 연결한다. 옷 아래의 몸을 복원하지 않았으므로 노출 범위가 큰 옷으로 바꾸면 원래 가려져 있던 부분에 구멍이 생길 수 있다. 긴 머리카락의 독립 물리, 표정 리깅, 천 시뮬레이션, 모든 동작의 관통 방지는 포함하지 않는다.

현재 샘플을 제품에 사용하려면 관절 경계의 가중치와 원래 옷 분리 경계를 다듬고, 사용할 실제 애니메이션에서 피팅을 확인해야 한다. 구조 검사 통과와 시각적 완성은 별개다.

검증 명령: `uv run pytest -q`, `uv run python -m compileall -q src`. 외부 전송 실패 시 중복 작업 차단, task ID 복구, CDN 인증 분리, 잘못된 다운로드의 기존 결과 보존, 관절 설정 오류를 테스트한다. 실제 Blender MCP 실행과 GLB 재수입 렌더도 수행했다.

## 공식 문서

- [Meshy Image-to-3D](https://docs.meshy.ai/en/api/image-to-3d)
- [Meshy Rigging: 지원 체형, 422, 작업 조회, 결과 형식](https://docs.meshy.ai/en/api/rigging)
- [Meshy Retexture](https://docs.meshy.ai/en/api/retexture): 기존 표면 스타일 변경용. 별도 의상 형상 생성과 구분한다.
