# 캐릭터 제어 API와 화면 설계

## 현재 상태와 목표

현재 구현과 후속 확장의 공통 계약이다. 백엔드 이전, 캐릭터 제어 API와 브라우저 앱이 구현되어 있다.

FastAPI는 `backend/src/api/server.py`, UI는 `frontend/src/`에 있다. 기존 `/api/world/*`와 캐릭터·의상 CLI를 유지한다. `audit_batch.py`는 `src.services.character_audit`를 호출하는 호환 진입점이며 계획 도구다. 실행과 검증은 별도 서비스가 담당한다.

목표는 Meshy에서 기본 리깅을 마친 약 5종의 캐릭터를 등록하고, 프론트엔드에서 가져오기·생성·리깅·의상/파츠 분리·미리보기·검수를 제어하는 것이다. 이미 받은 rigged GLB를 등록하는 경로와 이미지에서 생성하는 경로를 모두 지원한다. 등록만으로 유료 작업을 다시 만들지 않는다.

```text
frontend/                       브라우저 UI와 API 클라이언트
    ↓ HTTP 요청 / 작업 조회
backend/src/api/                인증, 입력 검증, 공개 응답
    ↓
backend/src/services/           상태 전이, 실행, 복구, 산출물 검증
    ├─ Meshy / 전용 Blender MCP
    └─ data/                    등록·작업·버전·검수 증거
```

`src.*`는 Python 패키지 이름으로 유지한다. Meshy CLI와 API는 `character_jobs` 서비스를 공유한다. 제어 API는 `.codex/` 스크립트나 CLI stdout에 의존하지 않는다. 데이터는 위 백엔드 하위 폴더가 아닌 저장소 루트 `data/` 또는 `ASSET_DATA_ROOT`에 저장한다.

## 책임과 저장

- 서버가 manifest·작업 기록·실제 파일을 근거로 상태와 가능한 action을 계산한다. 프론트는 서버 상태를 표시하고 검증된 입력을 제출한다.
- 파일 기반 상태·에셋을 보존하고 PostgreSQL에 등록·버전·작업·파츠·동작·검수 인덱스를 동기화한다. `CHARACTER_DATABASE_URL`, migration 002와 재색인·rollback 절차는 [캐릭터 준비 계약](character-preparation.md)을 따른다. DB는 다중 worker 큐가 아니다.
- 데이터 루트는 설정으로 고정한다. `backend/`에서 시작해도 동일한 이미지·manifest·작업 기록을 읽어야 한다. 원본 GLB와 승인 버전은 보존한다.
- 새 제어 API는 기존 인증 경계와 사용자 접근 범위를 따른다. 기존 `/api/world/*` 포맷과 인증을 바꾸지 않는다.
- ID로 서버가 파일을 찾는다. 업로드는 파일 데이터로 받고 클라이언트의 서버 경로·실행 코드·provider payload를 실행하지 않는다. 다운로드와 미리보기는 인증된 산출물 URL을 사용한다.

## 초기 API 계약

아래 API가 구현되어 있다. 아직 없는 action은 `next_actions`에 실행 가능으로 노출하지 않는다.

| 요청 | 역할 |
|---|---|
| `GET /api/characters` | 등록된 캐릭터와 진행·검수 요약 |
| `POST /api/characters` | 이미지 또는 리깅 모델 기반 캐릭터 등록; provider 제출 없음 |
| `GET /api/characters/{id}` | 입력·진행·산출물·파츠·검수·다음 작업 |
| `PATCH /api/characters/{id}` | 이름·키 등 허용된 설정; revision 충돌 검사 |
| `POST /api/characters/{id}/sources` | 이미지/GLB 업로드·검증·출처 등록; 사용 중인 원본 교체는 새 버전 |
| `POST /api/characters/{id}/actions/{action_id}` | 서버에 구현된 단계 실행; 긴 작업은 `202`와 operation ID 반환 |
| `GET /api/characters/{id}/operations/{operation_id}` | 로컬 실행과 provider 작업을 구별한 상태·복구 정보 |
| `GET /api/characters/{id}/artifacts/{artifact_id}` | 해당 사용자가 접근 가능한 이미지·GLB·검증 결과 |

첫 구현은 작업 조회 polling으로 복구까지 연결한다. SSE가 필요해지면 같은 operation ID와 상태 버전을 재사용한다. UI 기능 때문에 SSE를 먼저 필수 구현으로 만들지 않는다.

등록과 입력 변경은 생성·리깅 제출을 암묵적으로 시작하지 않는다. height 누락은 입력 수정 action으로 해결한다. 실행 중 설정 변경은 해당 실행의 입력 snapshot을 변경하지 않는다.

## 상태 표현

캐릭터 응답에는 `id`, `revision`, `height_meters`, `provider`, `operation`, `pipeline_status`, `rig_origin`, `problems`, `artifacts`, `inspection`, `parts`, `review`, `next_actions`를 둔다. 원본 이미지와 가져온 GLB는 `artifacts`의 ID로 제공한다. 목록은 큰 파츠·증거 내용을 제외할 수 있다.

- `provider`: task ID, 단계, **실제 기록된 상태**, 진행률. `submission_rejected`와 실행 후 `FAILED`를 섞지 않는다. 외부에서 받은 GLB는 확인하지 못한 task ID나 성공 기록을 만들지 않는다.
- `operation`: 우리 서버의 작업 ID, 단계, 수락·실행·실패·복구 상태. provider 성공은 Blender 처리·제품 승인과 별개다.
- `pipeline_status`: `ready`, `blocked`, `in_progress`, `review_required`, `approved`. 연결 오류만으로 서버 상태를 덮어쓰지 않는다.
- `rig_origin`: `meshy`, `local_fallback`, `unknown` 등 출처 증거에 따른 값. GLB에 뼈가 있다는 사실만으로 Meshy 성공을 추정하지 않는다.
- `next_actions`: `id`, `enabled`, `reason`, `external_mutation`, 필요한 입력. `review_local_fallback`처럼 감사기의 제안은 작업 목록에 매핑하고 실행 가능한 API command라고 가정하지 않는다.
- `review`: 기술·동작·시각 판정과 대상 산출물 버전·해시, 검사 증거, 검토자·시각. 새 산출물에 이전 승인을 승계하지 않는다.

사용자에게 필요한 문제는 안정적인 오류 코드와 복구 행동으로 변환한다. `command`, `local_setup`, 절대 경로 또는 raw provider 예외를 감사기에서 그대로 브라우저로 전달하지 않는다.

## 중복 요청과 복구

- 변경 action은 `Idempotency-Key`와 기대 revision을 받는다. 키의 범위는 사용자·캐릭터·action이며 입력 fingerprint와 operation ID를 기록한다.
- 같은 키·같은 입력은 같은 operation을 반환한다. 같은 키·다른 입력 또는 허용되지 않은 현재 상태는 `409`다. 키가 달라도 동일 단계 중복 실행은 캐릭터/run 잠금과 상태 검사로 막는다.
- 수락·idempotency 기록은 응답 전에 영속화한다. provider POST 전에 `submission_uncertain`을 기록한다. CLI와 API는 같은 run 잠금 규약을 사용하고 하나의 Blender 인스턴스에 변경 작업을 동시에 보내지 않는다.
- 브라우저는 중복 클릭을 막고 응답 유실 후 같은 operation을 조회한다. operation ID도 받지 못했다면 동일 키로 기존 수락을 복구한다. UI의 재요청이 새 provider POST를 의미하지 않게 한다.
- 서버가 재시작하면 기록된 작업을 확인한다. provider 작업은 저장한 ID를 조회하고, Blender 작업은 실제 실행 핸들·완료 기록을 조사한다. 기록만 `running`이라는 이유로 재시작하거나 완료 처리하지 않는다.
- 응답 불확실성은 유료 자동 재시도의 근거가 아니다. task ID 복구 또는 입력을 바꾼 별도 시도 여부를 명시적으로 결정한다.

## 파츠와 검수

기본 흐름은 rigged source 검증 → 동일 rig를 보존한 의상/파츠 분리 → 버전별 GLB/Blender 파일 → 미리보기·동작 검사 → 시각 검수다.

파츠 분리 입력은 source hash에 연결된 검증된 선택 영역/recipe ID를 사용한다. 서로 붙은 메시를 무조건 연결 요소별로 나눈 결과를 의미 있는 의상 분리라고 판단하지 않는다. 파츠 오브젝트·armature 계약과 숨겨진 몸의 coverage를 기록한다.

UI는 캐릭터별 상태, 입력 편집, 허용 action, 파츠 표시/숨기기, 애니메이션 미리보기와 검수 결과를 제공한다. 서버에서 지원되지 않는 파츠 분리 방식이나 애니메이션을 버튼만 만들어 제공하지 않는다. 검수 완료는 현재 버전의 증거를 열어 확인한 결과여야 한다.

## 구현 순서와 통과 증거

현재 지원하는 action은 모델 검사, Meshy 제출·조회·ID 복구·다운로드, `prepare_character`/`resume_character`/`recover_motion_task`, `separate_materials`/`separate_parts`, 파츠 역할 저장, 버전별 검수다. 유료 Meshy 실작업은 이 구현 검증에서 새로 제출하지 않았다.

`separate_materials`는 한 armature에 연결된 메시의 재질 경계를 Blender에서 분리한다. `separate_parts`는 같은 재질에서도 source hash와 node/primitive/face 선택으로 나눈다. 원본을 유지하고 operation별 `blender/character.glb`, `source.blend`, `rest.png`, `selection.json`, `quality.json`을 만든다. 임의 코드·경로를 입력받지 않는다. 면 분리는 accessor와 morph/animation 연결을 보존한다. 재질 분리의 shape key 대상 및 여러 armature는 지원하지 않는다. 기본 자세 렌더는 동작 검증을 대체하지 않는다.

서버는 단일 worker로 실행한다. 재접속과 응답 유실은 동일 idempotency key로 복구하며 provider 작업은 task ID로 조회한다. 서버가 강제 종료된 로컬 작업의 자동 재개는 아직 없다. `operations/<id>/blender/runner.json`의 PID와 로그·완료 파일을 확인한 뒤 운영자가 해당 실행과 잠금을 복구해야 한다. 프로세스가 살아 있는지 확인하지 않고 lock을 삭제하거나 새 작업을 제출하지 않는다.

각 행은 완료 후 다음으로 진행할 수 있는 구현 단위다. 전체 프론트 제어 완료는 마지막 행까지 충족해야 한다.

| 순서 | 구현 | 필요한 증거 |
|---|---|---|
| 1 | Python 프로젝트를 `backend/`로 이전, `frontend/` 실행 기반 마련 | `src.*` import·CLI·API 호환; 빌드·테스트 경로·Docker·`.env`·데이터 루트 확인 |
| 2 | 백엔드 공통 상태 서비스와 캐릭터 목록/상세 UI | 실제 manifest 표시; 내부 경로 비노출; 새로고침 후 동일 상태 |
| 3 | 소스/height 등록·수정, 비유료 action 하나를 끝까지 연결 | 입력 검증·동시 수정 충돌·작업 수락·결과 표시를 실제 API와 브라우저로 확인 |
| 4 | Meshy 생성·리깅·다운로드, Blender 분리·렌더를 서비스에 연결 | 중복·응답 유실·재접속·재시작 복구 테스트; 실제 작업은 허용된 범위에서 확인 |
| 5 | GLB 파츠/모션 미리보기·버전별 검수 | 승인 증거와 해시 연결; 모델 교체 자원 해제; 캐릭터별 외형·동작 확인 |

1단계에서 `pyproject.toml`, `uv.lock`, `main.py`, `src/`, `tests/`, `Dockerfile`의 실행 관계와 `migrations/`, 데이터 루트 참조를 함께 점검한다. 기존 root CLI가 필요하면 호환 진입점만 유지한다. 이전을 이유로 서비스를 다시 작성하지 않는다.

하네스·앱 검증과 캐릭터 제품 완성은 별도다. 실제 5종의 Meshy 리깅·의상 의미 분리·폭넓은 동작·외형 검수는 각 캐릭터의 산출물과 검수 증거로 판단한다.
