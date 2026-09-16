# 메이플풍 3D SD 캐릭터 생산

## 실행 흐름

기본 선택은 **통짜 전신 · 반팔·반바지**다. `slots: ["body"]`로 머리·얼굴·머리카락·팔·손·다리·발까지 포함한 전신 이미지 한 장과 Meshy 7 모델 한 개를 생성한다. 전신과 개별 파츠를 동시에 요청할 수 없다. 기존 파츠 작업의 설정·시도 기록은 바꾸지 않는다.

전신 경로는 생성된 메시의 면·재질·비율을 유지하고 위치와 전체 크기만 맞춘다. 로컬 기본 몸으로 대체하거나 목을 잘라내지 않는다. `generated-body.glb`는 공급자 원본이며, `body.glb`·`character.glb`와 Blender 파일은 별도 로컬 리그 검수 후보다. 로컬 23본 리그는 Meshy 자동 리깅 결과가 아니며, 동작·관절 위치의 시각 검수가 필요하다.

이미지 응답은 파츠별 `*-provider.response.json`에 먼저 보존한다. 파싱·이미지 저장 도중 중단되면 완전히 받은 응답을 재사용하며 POST를 다시 보내지 않는다. 이미지 수신 뒤 로컬 색인 처리에 실패하면 `received` 상태의 파일과 해시로 이어간다. 부분 응답만 있거나 연결 응답이 끊긴 `submitting` 상태는 자동 재제출하지 않는다. 응답 상태·request ID·소요 시간은 `*-provider.request.json`, 민감한 값을 제외한 스택 위치는 작업 폴더의 `failure.json`에 남긴다.

HTTP 거절은 `*-provider.error.json`에 상태 코드·request ID·진단 ID와 제한된 `code/type/param`, 응답 크기·해시를 남긴다. 오류 메시지 원문·인증정보·참고 URL은 저장하지 않는다. 동일 오류 영수증을 다시 읽을 때 POST하지 않는다. HTTP 400만으로 정책 거절이나 특정 파라미터 오류라고 단정하지 않는다. 이 기록 추가 전에 거절된 작업은 없던 상세 응답을 복원할 수 없다.

아래는 개별 파츠 선택 시의 기존 흐름이다.

`/avatar.html`에서 캐릭터 이미지를 등록하고 파츠별 제작 요청을 입력한다. 생산할 파츠를 선택하면 다음 단계를 하나의 작업으로 실행한다.

1. OpenAI GPT Image 2.5로 원본을 참고한 독립 파츠 이미지 제작.
2. 파츠별 Meshy 7 생성, task ID 저장·조회·다운로드.
3. 기존 `gaesup-maple-v1`의 약 1.6등신 공통 몸에 의상·장비 조립.
4. 공통 리그 연결, GLB·BLEND·정면/측면/변형 렌더 출력.
5. 버전별 파츠·동작 확인. 기술 통과 결과는 `review_required`로 남는다.

개별 선택 슬롯은 얼굴, 앞머리, 뒷머리, 모자, 상의, 하의, 신발, 무기, 방패, 등 장비, 얼굴 장식, 목 장식이다. 이 개별 파츠 경로에서만 로컬 공통 템플릿 몸을 사용한다. 추가 장비는 선택한 것만 생산한다.

## 이미지 제공자

```dotenv
OPENAI_API_KEY=...
AVATAR_IMAGE_MODEL=gpt-image-2.5-sunburst
OPENAI_API_BASE=https://api.openai.com/v1
MESHY_API_KEY=...
```

GPT Image 2.5의 공식 모델 ID는 `gpt-image-2.5-sunburst`와 `gpt-image-2.5-flare`다. 이 파이프라인은 참고 이미지의 편집 정밀도를 위해 Sunburst를 기본으로 사용한다. [OpenAI 이미지 생성 문서](https://developers.openai.com/api/docs/guides/image-generation), [Sunburst 모델](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst).

공장 어댑터는 `POST /v1/images/edits`, JSON의 `images[].image_url`에 참고 PNG 또는 JPEG data URL 한 장, `n=1`, 1024×1024, high 품질, PNG 출력을 사용한다. [공식 JSON 편집 계약](https://developers.openai.com/api/reference/resources/images/methods/edit)을 따른다. white background 시안이며 알파/배경 마스크와 실루엣은 편집 화면에서 검토한다. 제작 요청은 예를 들어 “파란 수정 지팡이, 작은 별 장식”처럼 파츠별로 입력할 수 있다. 요청 설명과 모델·제공자는 수락 시점에 저장한다.

공장 원본 참고 이미지는 파일을 변경하지 않고 전송용 사본만 최대 1024px로 축소한다. 전송용 PNG가 512KB보다 크면 흰 배경의 JPEG 품질 90으로 변환한다. 고정 몸의 2048px 측정 템플릿 경로에는 이 축소를 적용하지 않는다. 2026-09-17 로컬 진단에서 원본 크기 이미지 요청은 `ReadError`, 작은 JPEG의 생성 불가능한 입력 검사는 정상 HTTP 400으로 응답했다. 이후 실제 전신 작업 `f8bf4ba9c5490ec81eb2d452`는 동일한 Sunburst 모델의 단일 요청으로 34.719초 만에 HTTP 200을 받았고, 머리부터 발까지 포함한 반팔·반바지 전신 PNG를 저장했다. 해당 작업의 요청·응답 영수증과 이미지 SHA-256이 작업 폴더에 보존된다.

기존 Gemini 공장 작업은 저장된 `pipeline.json`의 모델·base로 복구한다. 제공자 필드가 없는 이전 기록은 Gemini 기록으로 해석한다. 새 생산에 Gemini를 자동 대체 사용하지 않는다. 기존 월드 미디어 API의 제공자 선택은 별도 계약으로 유지한다.

2026-09-16 현재 로컬 설정 계정의 `GET /v1/models/gpt-image-2.5-sunburst` 응답은 200이었다. 이것은 모델 접근 조회이며 실제 유료 이미지 생성·화질·처리 시간의 검증은 아니다.

## 장비 장착

| 생산 슬롯 | 런타임 슬롯 | 연결 본 | 처리 |
|---|---|---|---|
| 무기 | hand | handR | 검·지팡이형 손잡이 기준, 비율 보존 크기 맞춤 |
| 방패 | offhand | handL | 중앙 뒤쪽 손잡이 기준 |
| 등 장비 | back | upperChest | 상단 등 접합점 기준 |
| 얼굴 장식 | faceAccessory | head | 얼굴 앞쪽 기준 |
| 목 장식 | neckAccessory | neck | 목 앞쪽 기준 |

장비는 단일 연결 본에 가중치 1을 주어 형태를 유지한다. 공통 skeleton을 공유하므로 무기·방패를 교체해도 현재 애니메이션은 유지된다. 의상에는 기존 변형 가중치 생성 방식을 사용한다.

장비 실루엣은 축별로 찌그러뜨리지 않고 균일하게 크기를 맞춘다. 현재 손잡이 위치는 슬롯 레시피의 정규화된 기준이다. 임의 무기의 정확한 손잡이 자동 인식, 양손 IK, 휘는 활, 총기 기믹, 망토/치마 물리는 구현하지 않았다. 등 장비는 현재 단단한 장식용이다. 실제 생성 모델의 축·손잡이·관통은 출력 검수가 필요하다.

설계 저장은 13개 레이어를 지원하고 기존 8개 레이어를 읽을 때 장비 레이어를 추가한다. 구형 클라이언트의 8개 저장은 기존 장비 편집을 삭제하지 않는다. `offhand` 슬롯을 추가했으며 기존 manifest v1 슬롯과 두 인간형 rig ID를 유지한다.

## 원본·비용·복구

- 새 작업은 원본 이미지 해시, blueprint revision, 파츠별 제작 설명, 모델을 고정한다.
- Meshy 전신 경로는 수락한 동작 ID와 고유 동작 요청 상한을 리깅 작업에도 고정한다. 리깅 조회가 지연되거나 서버가 재시작되어도 같은 작업을 이어가며, 기존 동작 제출 기록과 완료 파일을 재사용한다. 이후 사용자가 바꾼 슬롯 선택을 처음의 기본값으로 되돌리지 않는다.
- 파츠별 이미지/Meshy 최대 1회가 기본 제출 상한이다. 준비된 PNG를 사용하면 이미지 요청은 0회다.
- POST 전 시도 기록을 남긴다. 타임아웃·응답 유실에는 유료 자동 재시도나 다른 모델 재호출을 하지 않는다.
- Meshy 응답 유실은 기존 task ID로 복구한다. 이미지 응답이 불확실하면 그 작업은 중단 상태로 보존한다.
- 기존 파츠로 로컬 rebuild할 때는 저장된 출력 영수증을 재사용한다.
- 원본·기존 출력·검수 버전을 덮어쓰지 않는다. 제공자 성공과 사람의 시각 승인은 구분한다.
- 이미지 설계 저장 중 추가 편집이 발생하면 새 편집을 보존한다. 다른 캐릭터로 이동한 뒤 도착한 저장 응답은 현재 화면을 덮어쓰지 않는다.

## 로컬 실행

Windows에서는 루트에서 `./start-local.ps1`을 실행하면 됩니다. 기존 서버는 재사용하고, 없으면 loopback API와 UI를 실행한 뒤 실제 HTTP 응답과 공장 capability를 검사합니다. 다른 포트는 `-ApiPort 8001 -UiPort 5275`로 지정할 수 있습니다. 서버 로그 경로도 함께 출력합니다.

저장소 루트:

```powershell
uv run python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000
```

다른 터미널:

```powershell
cd frontend
npm run dev
```

UI 기본 주소는 `http://127.0.0.1:5273/avatar.html`이다. `GET /api/avatar-factory/capabilities`에서 현재 모델·키 설정 유무·Blender 가용 여부를 조회한다. 키 값과 제공자 base URL은 브라우저에 보내지 않는다.

## 검증

- 전체 pytest: 160개 통과. OpenAI JSON 요청, 모델 고정, 타임아웃·거절 시 요청 1회, 응답 보존·재사용, 전신 단일 생성, 장비 설명 snapshot, 구형 설계 저장 호환을 포함한다.
- 프론트 타입 검사·빌드 통과.
- 최종 E2E 12개 통과(57.4초). 기존 10개, 새 제작 설명/지연 저장, 실제 Blender 장비의 브라우저 장착·변형·저장·새로고침 검사를 포함한다. 최초 장비 검사에서 테스트가 런타임에 보존되지 않는 mesh 이름을 찾았고, 실제 장착으로 추가된 mesh를 추적하도록 고쳐 재실행했다.
- `run_blender_parts_check.py`: 기존 재질 분리 통과.
- `run_maple_equipment_check.py`: 실제 Blender, 최신 Maple 리그, 단일 본 장비 5종, 원본 보존, GLB/BLEND/렌더와 가중치 검사 통과.

추가 장비 통합 검사를 재실행하려면 다음과 같이 fixture 출력의 `root`를 사용한다. 이 경로의 데이터만 브라우저 테스트의 임시 데이터로 복사한다.

```powershell
# backend/
uv run python tests/run_maple_equipment_check.py
# frontend/ - 위 명령이 출력한 root 사용
$env:WORKSPACE_TEST_FACTORY_ROOT = '<출력된 임시 root>'
$env:WORKSPACE_TEST_API_PORT = '18012'
npm run test:e2e
```

장비 fixture는 직접 만든 단순 검·상자 모양이다. 해당 fixture 검사는 실제 GPT Image/Meshy 산출물이나 시각 승인 에셋의 증거가 아니다. 기존 앞/뒷머리 런타임 통합, 바지/치마 공통 가중치, 자동 의상 피팅의 한계는 [전체 설계 분석](character-factory-design.md)에 남아 있다.

로컬 실행 확인: UI 5273은 HTTP 200, 프록시를 통한 공장 capability는 OpenAI/Sunburst 및 전신을 포함한 13개 생산 슬롯, `ready: true`를 반환했다. 8000의 전체 health는 기존 PostgreSQL 연결 실패로 `degraded`다. DB 설정은 수정하지 않았다. 일반 E2E는 provider 설정을 비운 임시 파일 데이터에서 실행했다.

2026-09-17 실제 전신 생성 검증:

- 작업 `f8bf4ba9c5490ec81eb2d452`: Sunburst 이미지 1회, Meshy 7 생성 1회. Meshy task `01a0aac1-b314-7688-a785-ed23bb5d2519` 성공.
- 공급자 원본 `generated-body.glb`의 SHA-256 `c6de1a852039c799bacda413f039e9dc18a04646bc3670def6b91b5fd1b9646b` 보존. 원본과 로컬 전신 모델 모두 30,505개 삼각형. 머리·몸·의상 분리 없이 GLB와 `master.blend` 출력.
- `node scripts/check-factory.mjs f8bf4ba9c5490ec81eb2d452`: 실제 로컬 API와 WebGPU로 전신 표시, 전신 시안 탭, 7개 동작의 본 변화, 걷기, 새로고침 복원 확인. 브라우저 오류·쓰기 요청 0건. 전신 결과는 의상 분리 완료나 파츠 교체를 표시하지 않는다.
- 증거: `frontend/test-results/factory-f8bf4ba9c5490ec81eb2d452-1789571796670/{result.json,rest.png,walk.png}`. 최종 프론트 빌드 통과.
- 최종 상태는 `review_required`: 기술 검사 통과이며 로컬 23본 리그의 관절·변형에 대한 사용자 시각 승인은 남아 있다. Meshy 자동 리깅·실제 의상 분절·운영 배포는 수행하지 않았다.
