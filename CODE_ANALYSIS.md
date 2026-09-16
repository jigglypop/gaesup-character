# 코드 전체 분석

대상: `1908dbd` 기반 현재 작업 트리. 환경: Windows / PowerShell.

## 요약

캐릭터 제어와 아바타 편집은 실제 API·Blender·브라우저까지 연결돼 있다. 원본 해시, 중복 요청 식별자, 버전 충돌 검사, 작업 일지, 렌더 자원 해제도 구현돼 있다.

우선 해결할 문제는 기존 월드 API의 작업 ID 충돌 및 중복 실행이다. 이미지 편집에는 늦은 저장 응답이 현재 편집 상태를 덮어쓸 수 있는 경로가 있다. 전체 백엔드 검사는 경로 계약 테스트 1개가 실패한다.

이번 분석은 주요 실행 경로의 정적 검토와 실행 검증을 결합했다. 모든 코드 분기·외부 제공자 계약·실제 에셋 외형을 검증했다는 의미는 아니다.

## 1. 구조와 책임

| 영역 | 구현 | 역할 |
|---|---|---|
| 서버·인증 | `backend/main.py`, `src/api/server.py`, `src/auth.py` | 라우터, API key, JWT, loopback 개발 사용자 |
| 기존 월드 | `src/api/world.py`, `src/services/media.py` | 생성·리깅·동작·미디어·저장·프록시·SSE |
| 캐릭터 제어 | `character_pipeline.py`, `character_actions.py`, `character_recovery.py` | 소유권, revision, action, 수락 일지, 실행 및 복구 |
| 외부 작업 | `character_jobs.py`, `character_motion.py` | 제출 전 의도 저장, task ID 복구, 다운로드, 동작 팩 |
| 파츠 분리 | `character_segmentation.py`, `character_parts.py`, Blender worker | 원본 해시에 묶인 node/primitive/face 선택과 버전별 파일 |
| 이미지 설계·생산 | `avatar_blueprints.py`, `avatar_image_pipeline.py` | 8슬롯 설계, PNG, 파츠별 이미지 및 Meshy 작업 |
| 공통 아바타 생산 | `avatar_factory.py`, `avatar_factory_geometry.py`, `avatar_factory_blender.py` | 공통 몸·리그 변환, 출력 검증, 카탈로그 |
| 저장·인덱스 | `character_store.py`, `character_db.py`, `db.py` | 파일 일지와 PostgreSQL 조회 인덱스 |
| UI | `main.ts`, `factory/*`, `studio/*`, `avatar-page.tsx` | 캐릭터 제어, 이미지 레이어, 생산 버전, 옷장 |
| 3D 런타임 | `viewer.tsx`, `avatar/runtime/*`, `assets/GLTFAssetCache.ts` | R3F, WebGPU/호환 렌더러, skeleton, 장착·애니메이션·자원 해제 |

백엔드 Python 소스 51개 / 11,944줄, 프론트 TS·TSX 27개 / 2,723줄. 합계 78개 / 14,667줄이며 CSS·JSON·에셋·테스트는 제외했다. `world.py` 4,219줄과 `media.py` 1,365줄이 합계의 약 38%다. 일부 프론트 파일은 긴 한 줄 JSX를 사용하므로 줄 수만으로 복잡도를 비교하면 안 된다.

### 주요 데이터 흐름

1. 캐릭터: 등록·업로드 → revision/소유권 검사 → action 수락 일지 → 잠금 안에서 실행 → 산출물·control 저장 → 완료 기록 → DB 동기화.
2. 이미지 생산: 원본 해시·설계 revision 검사 → 파츠 이미지 → 개별 Meshy task → 다운로드 영수증 → 공통 리그 조립 → Blender·GLB 검사 → `review_required`.
3. 옷장: 카탈로그 → manifest/rig 검사 → 공통 skeleton 장착 → 애니메이션 유지 → 장착 상태 저장·복원.

## 2. 우선순위별 문제

P1: 데이터·비용·사용자 경계에 직접 영향. P2: 일반 사용·검증·유지보수에서 해결할 문제.

### P1-1. 다른 사용자의 같은 작업 ID가 월드 작업을 덮어쓴다 — 재현 확인

- 위치: `backend/src/api/world.py:3669`, `:3428`, `:3599`.
- `client_job_id`를 기존 소유자 조회 없이 사용하고 `_MEMORY_JOBS[job_id]`에 바로 대입한다.
- DB 없는 모드에서 사용자 1이 작업을 만든 다음 사용자 2가 같은 ID로 요청하면 메모리 기록의 소유자가 2가 되고 사용자 1의 조회는 404가 된다.
- DB 경로도 `ON CONFLICT (id)` 갱신 조건에 소유권 검사가 없다. 실제 PostgreSQL 실행은 이번에 검증하지 않았다.
- 수정 방향: 생성 입구에서 기존 작업 소유권·입력 fingerprint를 검사하고 저장 계층에서도 소유자 불일치 갱신을 거부한다. schema 변경 없이 가능한 방어부터 적용한다.

### P1-2. 같은 월드 생성 요청을 재전송하면 공급자 실행을 반복한다 — 재현 확인

- 위치: `backend/src/api/world.py:3679`, `:3693`.
- 같은 사용자·같은 작업 ID·같은 입력이어도 매번 queued 상태를 쓰고 `_call_provider`를 호출한다.
- 공급자를 대체한 재현에서 동일 요청 2회에 공급자 진입 2회를 확인했다. 실제 유료 제출은 하지 않았다.
- 응답 유실 후 같은 ID로 복구 요청을 보내면 구성된 생성 경로에서 추가 외부 작업으로 이어질 수 있다.
- 수정 방향: 같은 요청은 저장된 작업을 반환하고 입력이 다르면 409를 반환한다. 동시 요청도 막는 원자적 수락과 제출 영수증이 필요하다.

### P2-1. 늦은 설계 저장 응답이 새 편집 또는 다른 캐릭터 화면을 덮어쓸 수 있다 — 정적 확인

- 위치: `frontend/src/factory/ImageWorkbench.tsx:50-64`, `:69`, `:76`.
- `save()` 완료 시 조건 없이 `setBlueprint(result); setDirty(false)`를 호출한다.
- 저장 중에도 캐릭터 선택 버튼과 레이어 수정이 가능하다. 읽기에는 generation 검사가 있지만 저장 완료에는 없다.
- A 저장 응답을 지연시킨 뒤 B를 선택하면 B를 불러온 뒤 도착한 A 응답이 화면을 A 설계로 바꿀 수 있다. 같은 캐릭터에서도 저장 이후 추가 편집이 이전 응답에 덮일 수 있다.
- 수정 방향: 요청 시작 시 character ID와 편집 세대를 캡처하고 현재 대상·세대에 해당하는 응답만 적용한다. 저장 이후 편집은 dirty 상태를 유지한다.
- 이 경쟁 조건은 기본 E2E에 없으며 지연 응답을 주입한 별도 브라우저 재현은 하지 않았다.

### P2-2. 월드 API가 내부 예외 원문을 공개 응답에 전달한다 — 재현 확인

- 위치: `backend/src/api/world.py:3700-3704`, `:3603`, `:3808`.
- 공급자 예외를 `str(e)`로 저장해 응답의 `error`로 반환한다. SSE도 예외 문자열을 직접 보낸다.
- 가상의 내부 경로를 담은 RuntimeError를 주입했을 때 해당 문자열이 공개 응답에 그대로 나타났다. 실제 비밀값은 사용하지 않았다.
- 수정 방향: 공개 오류 코드·안내 문구와 내부 진단을 분리하고 request ID로 연결한다. 실제 키 유출을 확인했다는 의미는 아니다.

### P2-3. 실제 API와 경로 계약 테스트가 불일치한다 — 테스트 실패 확인

- 위치: `backend/tests/api/test_server.py:24`, `backend/src/api/avatar_factory.py`의 rebuild 라우트.
- 실제 스키마의 `POST /api/avatar-factory/jobs/{job_id}/rebuild`가 기대 경로 집합에는 없다.
- 결과: 129 passed / 1 failed.
- 수정 방향: 경로 목록을 갱신하고 rebuild의 소유권·입력 보존·새 버전·외부 재제출 없음도 검증한다. 목록 수정만으로 동작 검증이 끝나지는 않는다.

### P2-4. 핵심 운영 계약 문서 7개가 삭제된 상태다 — 작업 트리 확인

- 대상: `docs/avatar-image-pipeline.md`, `character-control-plane.md`, `character-pipeline.md`, `character-preparation.md`, `modular-avatar.md`, `postgresql-schema.md`, `wardrobe-pipeline.md`.
- README와 루트·백엔드·프론트 AGENTS가 이 중 여러 문서를 계속 참조한다.
- 복구·생성 비용·검수·DB 계약을 따라가려는 개발자가 현재 체크아웃에서 해당 문서를 열 수 없다.
- 삭제는 분석 시작 전부터 존재했다. 의도적인 재편 여부를 단정하지 않았고 복원하지 않았다. 삭제를 유지한다면 대체 문서와 참조 갱신이 필요하다.

## 3. 잘 구현된 부분

- 캐릭터 작업은 `If-Match`와 idempotency key를 사용하고 가능한 action을 서버에서도 검사한다.
- `character_jobs._submit()`은 POST 전에 의도를 저장한다. timeout 뒤에는 task ID 복구를 요구한다.
- 캐릭터 복구는 executor·Blender 종료 상태, 입력 해시, 완료 seal을 확인한다.
- 면 분리는 원본 accessor/skin을 재사용하고 index를 나누며 morph animation도 새 메시들에 연결한다.
- 공장 산출물은 해시·리그·애니메이션·검수 렌더를 검사하고 `review_required`로 공개한다.
- 런타임에는 장착 실패 복원, 공유 GLTF 참조 수, geometry/material/texture/skeleton 해제 구조가 있다.
- 캐릭터 PostgreSQL 동기화 실패가 공급자 재제출로 연결되지 않는다.

## 4. 설계 경계와 개선 후보

### 분리와 공통 리그 변환

`character_segmentation.split_faces()`는 기존 rig/weights를 유지하는 분리다. `avatar_factory_geometry.compile_part_models()`는 별도 생성 파츠를 고정된 연결 영역에 맞추고 새 weights를 계산하는 변환이다. 후자의 기술 통과를 원래 rig/weights 보존이나 외형 보존 증거로 사용할 수 없다. 파츠 비율 보정, 얼굴 목 절단, 의상 변형은 실제 출력 검수가 필요하다.

### 공장 검수 완료 흐름

공장은 `review_required`와 `pending` 검수 상태를 만든다. 현재 공장 API에는 해당 버전의 승인·수정 요청을 저장하는 라우트가 없다. 캐릭터의 `record_review`와 별도이므로 공장 버전 검수를 끝내는 제품 흐름은 추가 연결이 필요하다.

### 작업 실행 기반

캐릭터 제어, 아바타 공장, 기존 월드에 서로 다른 작업 저장·잠금·복구 구현이 존재한다. 공장의 `_LOCK`, `_QUEUE`, `_RUN_LOCKS`는 프로세스 내부 잠금이다. 현행 단일 worker 제약을 유지해야 한다. 공통화한다면 먼저 소유권·수락·실행 영수증 계약을 맞추는 것이 적절하다.

### 성능·유지보수

- 최대 공유 JS 청크는 3,884.30 kB, gzip 1,295.99 kB다. 실제 네트워크에서 초기 3D 로딩 비용을 측정할 가치가 있다.
- 캐릭터 상세는 모델 해시·파일 검사를 포함하고 화면은 주기적으로 조회한다. 대용량 GLB·다수 캐릭터에서 조회 비용을 측정한 뒤 캐시 또는 요약 응답을 검토한다. 이번에 성능 회귀를 계측한 것은 아니다.
- 큰 월드·미디어 파일은 오류·수락 계약을 고정한 뒤 공급자 어댑터와 저장 처리를 점진적으로 분리하는 것이 적절하다.
- loopback의 `X-User-Id`는 관리자 개발 사용자로 해석된다. README의 로컬 개발 프록시 용도에 맞춘 구현이며 공개 서비스 인증 검증으로 해석하면 안 된다.

## 5. 실행 검증

| 검사 | 결과 | 범위 |
|---|---|---|
| 루트 `uv run pytest -q` | 129 통과 / 1 실패 | rebuild 경로 계약 불일치 |
| frontend `npm run build` | 통과 | 타입 검사·프로덕션 빌드, 큰 청크 경고 |
| 기본 `npm run test:e2e` | 서버 시작 실패 | Windows가 127.0.0.1:8012 바인딩 거부 |
| API 포트 변경 후 E2E | 10 통과, 약 1분 | 아래 명령 |
| 월드 중복·소유권 재현 | 문제 확인 | 공급자·DB·에셋 저장을 대체해 메모리에서 수행 |
| 내부 예외 노출 재현 | 문제 확인 | 가상의 오류 문구만 사용 |

```powershell
# frontend/에서 실행
$env:WORKSPACE_TEST_API_PORT = '18012'
npm run test:e2e
```

포트 오류의 원인을 단순 점유로 단정하지 않았다. 브라우저 검사는 임시 데이터와 비어 있는 공급자 설정을 사용한다. 실제 로컬 API 저장·복원, 실패한 장착 복원, 이미지 설계, 원본 면 선택 → Blender 분리 → 새 GLB·Blender 산출물 → 새로고침 복원을 포함한다.

테스트는 WebGPU 또는 WebGL 호환 모드 중 하나를 허용하므로 이번 통과만으로 실제 WebGPU 실행을 확정하지 않는다.

유료 Meshy/Gemini 생성, 운영 PostgreSQL, 실제 캐릭터 5종 외형·변형 승인, 공개 배포 인증, 대용량 성능은 이번 검증 범위 밖이다.

## 6. 권장 처리 순서와 변경 범위

1. 월드 작업 소유권 충돌·중복 실행을 차단하고 동일/다른 사용자 및 동시 요청 회귀 검사를 추가한다.
2. 이미지 편집의 저장·캐릭터 전환 경쟁 조건과 지연 응답 검사를 추가한다.
3. 공개 오류를 정리하고 rebuild API 계약·동작 검사를 맞춘다.
4. 삭제 문서의 대체 경로를 정하고 공장 검수 완료 흐름을 연결한다.
5. 실제 측정에 따라 조회 비용과 3D 번들을 개선한다.

이번 작업은 분석 보고서 추가와 검증 실행이다. 기존 코드 수정 4개와 문서 삭제 7개는 유지했고 위 문제의 구현 수정은 하지 않았다. 빌드·브라우저 검증은 일반적인 dist/test-results 산출물을 생성한다.

