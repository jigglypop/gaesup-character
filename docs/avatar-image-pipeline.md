# 이미지에서 모듈형 아바타 생산

현재 루트의 `backend/`와 `frontend/` 구현이다. `/avatar.html`에서 캐릭터 이미지를 올리고 **전체 자동 생산**을 누른다. 기본 선택은 얼굴·뒷머리·앞머리·모자·상의·하의·신발 7개다. 없는 의상은 선택에서 해제한다. 공통 몸은 새로 작성한 SD 템플릿이며 원본에서 보이지 않던 몸을 복원했다고 표시하지 않는다.

## 실행

루트 `uv run asset-dev`, `frontend/`에서 `npm run dev`를 실행한다. API를 다른 포트로 실행하면 프론트의 `BACKEND_URL`을 해당 주소로 지정한다. 현재 확인한 개발 주소는 `http://127.0.0.1:5273/avatar.html?character=A`, API는 `http://127.0.0.1:62122`다.

서버는 루트 `.env`의 `GEMINI_API_KEY`, `GEMINI_IMAGE_MODEL`, `GEMINI_API_BASE`, `MESHY_API_KEY`, `MESHY_API_BASE_URL`과 로컬 Blender를 사용한다. 키를 프론트에 전달하지 않는다. Windows에서 실행 정책이 uv 관리 Python을 차단하면 설치된 Python으로 `.venv/Lib/site-packages`와 `backend`를 `PYTHONPATH`에 지정해 실행할 수 있다.

## 생산 경로

1. 원본 이미지와 SHA-256, 선택 파츠, 설계 revision, 호출 한도를 새 작업 폴더에 고정한다.
2. Gemini에 파츠별 원본 참조를 전달해 하나씩 완성형 이미지를 만든다. 숨겨진 모자 테두리·머리 두피·옷 연결부 보완을 요청한다. 요청 프롬프트와 시도 시각을 제출 전에 저장한다. 이미지 모델 자동 대체나 POST 재시도는 하지 않는다.
3. 각 이미지마다 별도의 Meshy 7 Image-to-3D task를 보낸다. 파츠당 목표 10,000 polygon을 요청한다. `character_jobs`의 기존 Meshy 계약과 제출 의도 기록을 재사용한다. 모자·옷에 humanoid auto-rig를 보내지 않는다.
4. 성공한 GLB를 해시 검증해 내려받고 공통 몸의 파츠별 공간에 맞춘다. 원본 재질·UV를 유지하고 모든 파츠를 동일한 23본 계층·rest pose·inverse bind에 연결한다. 가중치는 최대 4개 뼈로 정규화한다. 앞·뒷머리는 출력 시 runtime의 hair 슬롯으로 합친다.
5. 공통 body, 각 슬롯 GLB, 조립 `character.glb`, 몸 영역을 보존한 `workspace.glb`, 편집용 `master.blend`, 정면·측면·변형 렌더와 품질 JSON을 새 버전으로 저장한다. canonical 카탈로그로 등록해 R3F 옷장에서 장착·해제·동작을 확인한다.

**현재 편집한 파츠 PNG 사용**은 이미지 모델 호출 없이 편집기의 개별 PNG를 고정해 Meshy에 전달한다. 원본 bitmap과 편집 설계는 유지한다. 이 옵션에서 사용자가 조정한 2D 배치는 겹침 검수용이며, 3D 위치는 canonical 몸의 공통 공간에 맞춘다. 자동 모드의 배경 흰색과 atlas의 회색 배경 마스크는 후보 처리다. 잘못 포함된 손·다른 의상, 구멍·테두리·뒷면은 검수가 필요하다.

7개 선택 기준 유료 상한은 이미지 7회 + Meshy 7회다. 준비한 PNG 모드는 이미지 0회 + Meshy 7회다. 공통 몸 생성·리깅·조립·렌더는 로컬 처리한다. 공급자 과금액은 모델·계정에 따라 달라지므로 횟수를 비용 확정치로 표시하지 않는다.

## 저장과 복구

`data/avatar-blueprints/{owner}/`는 파츠 이미지와 설계 revision·저장 영수증을 보관한다. `data/avatar-factory/{owner}/{job}/`의 `job.json`이 작업 상태, `pipeline.json`이 고정 입력과 파츠별 진행 상태, `parts/{slot}/character.json`이 Meshy 제출·task ID의 기준이다. `output/`에는 산출물과 Blender runner·완료 seal이 있다. DB schema는 변경하지 않는다.

새로고침·재접속 시 작업 목록과 설계를 조회한다. 생산 POST의 응답이 유실되면 브라우저에 저장한 동일한 key·입력으로 복구한다. Meshy가 task ID를 반환했다면 조회·다운로드를 재개한다. POST 응답이 불확실하고 ID가 없으면 멈추며, 화면에서 기존 Meshy ID를 입력해 GET으로 조회·복구할 수 있다. 이미지 요청은 비동기 task ID가 없으므로 응답 유실 시 자동 재생성하지 않는다. 새 버전 생산은 별도의 유료 시도다.

단일 API worker 계약이다. 서버 재시작 시 기존 process identity, Blender runner, 완료 seal을 검사한다. 완료된 Blender 출력은 검증 후 복구하고, 결과가 불확실하면 파일을 보존한다. 사용자별 API 권한과 SHA-256을 검사하며 절대 경로·키·공급자 다운로드 URL을 공개 응답에 내보내지 않는다.

## 검증과 남은 품질 경계

- `uv run pytest -q`: 상태 전이, 7개의 서로 다른 이미지·Meshy task, 응답 유실 후 중복 POST 방지, 기존 ID 복구, 다운로드·조회 재개, 원본/owner 검증.
- `frontend/npm run build`, `npm run test:e2e`: 실제 임시 API의 이미지 등록, 편집·저장, 저장 응답 유실, 새로고침·오류 표시, 기존 R3F 옷장과 라이브러리 회귀. 브라우저 테스트는 provider 키를 비운다.
- `python backend/tests/run_avatar_factory_check.py`: 폐기 가능한 파츠 fixture를 실제 Blender로 컴파일해 단일 23본 skin, 공통 동작 7종, 6개 출력 슬롯, 원본 보존, GLB·Blender·렌더를 확인한다. 두 hair 이미지가 한 슬롯으로 합쳐진다.
- `backend/uv run python tests/run_blender_parts_check.py`: 기존 원본 면 분리의 rig/weights 보존 회귀.

2026-09-15 검증: backend 130개, browser 10개, 프론트 빌드 통과. 로컬 공통 리그 컴파일과 기존 분리 Blender 검사를 통과했다. 실제 A 작업의 이미지 7개·Meshy 모델 7개가 저장된 상태에서 로컬 조립을 복구했고, 브라우저 WebGPU에서 공통 몸·6개 장비 슬롯·걷기·전체 장착 해제·새로고침 복원을 확인했다. 최종 외형 승인은 `pending`이다. 공통 동작 7종은 변형 검사 클립이며 상용 동작 팩의 품질 증명이 아니다. 파츠별 방향·실루엣·겹침·클리핑과 자동 weight 품질은 생성된 캐릭터마다 검수해야 한다.

## 용량 검사와 기본복 몸체 수정

공장 출력에서 파일 크기·텍스처·폴리곤·재질 수의 권장 예산 초과는 경고로 기록한다. 25 MiB를 넘었다는 이유로 정상 조립물을 실패시키지 않는다. GLB 구조 오류, 잘못된 joint 참조, 공통 리그·동작 누락, 해시 불일치는 계속 실패 처리한다. 일반 업로드·에셋 검사 호출의 기존 엄격한 정책은 유지한다.

`maple-sd-v2`는 대머리 머리와 눈·눈썹·입, 팔·손, 불투명 기본 티셔츠·반바지·기본 신발을 포함하는 새 공통 몸체다. 기본복과 얼굴은 `body.glb`에 포함하며 같은 23본 리그를 쓴다. 장비를 입으면 해당 몸 영역과 기본복이 함께 가려지고, 벗으면 기본복 몸체가 다시 나타난다. 원본 캐릭터의 숨겨진 몸을 복원한 결과가 아니다.

실제 A 작업 `ca8fafe8d3b1b09937a16666`의 36.83 MiB 출력에서 용량 차단을 재현했다. 기존 파츠만으로 재조립한 기본복 버전은 37.12 MiB이며 21개의 2048×2048 텍스처를 유지한다. 입력·공급자 파일 36개의 SHA-256이 복구 전과 같음을 확인했다. 추가 이미지·Meshy 제출 없이 `review_required`로 복구했다.

실패 작업을 재개할 때 기존 `output/`과 작업 일지를 `attempts/{id}/`로 보존한다. `body.png`·정면·측면·변형 렌더 4개를 출력하며, 투명하게 비어 있는 검수 이미지도 검사한다. 기본 몸을 먼저 렌더한 뒤 정면 카메라 위치·회전을 명시적으로 복원한다. 현재 결과는 [기본 몸](http://127.0.0.1:5273/avatar.html?stage=glb&character=A&job=ca8fafe8d3b1b09937a16666&tab=body)과 [파츠 교체](http://127.0.0.1:5273/avatar.html?stage=glb&character=A&job=ca8fafe8d3b1b09937a16666&tab=result)에서 확인할 수 있다.

기본 A 이미지 atlas는 `backend/assets/avatars/image-design/A-atlas-v1.png`에 있다. 원본·도구·프롬프트·해시는 같은 폴더의 `provenance.json`에 기록했다. 이 atlas는 디자인 시안이며 실제 투명 알파, 의미 분리, 3D 생산을 승인한 파일이 아니다. 모든 신규 생산 버전의 외형 승인은 `pending`으로 남긴다.

이 Windows 환경의 브라우저 검사는 `WORKSPACE_TEST_SYSTEM_PYTHON=1`, `WORKSPACE_TEST_BROWSER=chrome`, `WORKSPACE_TEST_API_PORT=62125`와 위 `PYTHONPATH` 설정으로 실행했다. 기본 테스트 포트 8012는 바인딩이 거부되어 별도 테스트 포트를 사용했다. 실제 개발 서버와 provider 데이터는 테스트 서버에서 사용하지 않는다.

공식 API 계약: [Meshy Image-to-3D](https://docs.meshy.ai/en/api/image-to-3d), [Gemini 이미지 생성](https://ai.google.dev/gemini-api/docs/generate-content/image-generation).
