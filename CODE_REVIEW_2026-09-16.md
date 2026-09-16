# 코드 검토 및 실행 결과 — 2026-09-16

현재 작업 트리의 백엔드·프론트 변경, 기존 월드 생성 API, 로컬 실행 및 복구 검사를 검토했다. 기존 수정·미추적 파일·문서 삭제는 보존했다. 이번 변경은 이 보고서 추가뿐이며 아래 결함은 수정하지 않았다. 기존 `CODE_ANALYSIS.md`의 과거 테스트 수치는 이번 결과와 구분한다.

## 재현된 결함

### P1: 다른 사용자의 작업 ID로 기록을 덮어쓸 수 있음

- 위치: `backend/src/api/world.py:3679`, `backend/src/api/world.py:3429`.
- `world_generate()`는 클라이언트 작업 ID를 받아 기존 소유권 확인 없이 `_save_job()`을 호출한다. 메모리 저장소는 ID만 키로 사용한다.
- DB·공급자·에셋 저장을 대체한 독립 Python 프로세스에서 사용자 1이 생성한 ID로 사용자 2가 요청하자 기록 소유자가 2로 바뀌고 사용자 1의 조회가 404가 됐다.
- SQL의 `ON CONFLICT (id)`도 갱신 조건에 소유권 검사가 없다. PostgreSQL 경로는 정적 확인이며 실제 DB 재현은 하지 않았다.
- 수락 전에 소유권을 확인하고, 저장 계층에서도 다른 소유자의 충돌 갱신을 거부해야 한다.

### P1: 같은 생성 요청 재전송이 공급자 실행을 반복함

- 위치: `backend/src/api/world.py:3679-3699`.
- 기존 ID·입력의 처리 결과를 반환하는 분기 없이 매번 queued 기록을 쓰고 공급자에 진입한다.
- 같은 사용자·ID·입력으로 2회 호출했을 때 대체 공급자 호출 횟수가 2였다. 실제 유료 요청은 보내지 않았다.
- 응답 유실 후 재시도 시 설정된 공급자 경로에서 중복 생성·비용 발생 가능성이 있다.
- 소유자와 입력 fingerprint를 기준으로 원자적으로 수락하고, 동일 요청은 기존 결과를 반환하며 변경된 입력은 409로 거부해야 한다. 제출 전 의도와 공급자 task ID도 보존해야 한다.

### P2: 공급자 내부 예외가 공개 응답에 포함됨

- 위치: `backend/src/api/world.py:3700-3704`, `backend/src/api/world.py:3603`.
- 공급자 예외를 `str(e)`로 저장해 응답에 전달한다.
- 가상 문자열 `REVIEW_FAKE_INTERNAL_PATH`를 담은 예외를 주입했을 때 같은 문자열이 응답에서 확인됐다. 실제 비밀정보를 사용하거나 유출한 검사가 아니다.
- 공개 오류는 고정 코드·문구로 반환하고 상세 예외는 request ID와 함께 내부 로그에 남겨야 한다.

## 추가 정적 검토

- `frontend/src/factory/ImageWorkbench.tsx:68-73`: 파츠 업로드 완료 시 캐릭터 전환 세대를 확인하지 않고 현재 blueprint에 `update()`를 적용한다. 업로드 중 캐릭터 선택 버튼은 활성 상태다. A의 업로드 응답이 B를 불러온 뒤 도착하면 B의 레이어에 A의 업로드가 적용될 수 있다. 브라우저 지연 응답 재현은 하지 않았다. 요청 시작 시 대상·세대를 캡처하고 일치할 때만 적용해야 한다.
- 기존 보고서의 설계 저장 경쟁 조건은 현재 저장 코드에 세대·편집 검사가 추가됐다. 지연 저장 중 추가 편집 보존 E2E는 통과했다. 위 업로드 경로와는 별개다.
- 기존 보고서의 rebuild 경로 계약 실패는 현재 전체 pytest에서 재현되지 않았다.
- 삭제 상태인 운영 문서 7개는 그대로이며 AGENTS의 `docs/character-control-plane.md`, `docs/character-preparation.md` 참조 등은 현재 열 수 없다. 삭제 의도를 추정해 복원하지 않았다.

## 실행 및 검증

| 검사 | 결과 |
|---|---|
| 루트 `uv run pytest -q` | 155 통과, 의존성 deprecation 경고 2개 |
| frontend `npm run build` | 타입 검사·빌드 통과, 최대 청크 약 3.88 MB 경고 |
| 기본 E2E, API 포트 18012 | 12 통과 / fixture 필요 4개 생략 |
| `run_maple_equipment_check.py` | 실제 Blender, 23본·5파츠·원본 보존 통과 |
| Maple fixture 추가 E2E | 생략됐던 장비 테스트 1개 통과 |
| `run_avatar_standard_check.py` | 실제 Blender, 24본·원본 skin/BIN/동작 보존·두 의상 조합 통과 |
| 고정 몸 fixture 추가 E2E | 생략됐던 3개 통과, 두 의상 모두 `webgpu` 확인 |
| `start-local.ps1` | 기존 서버 재사용, UI·API·프록시 응답 확인 |

E2E 16개는 기본 실행과 fixture별 추가 실행을 합쳐 전부 통과했다. 고정 몸 브라우저 검사는 골격 공유, 동작에 따른 정점 이동, 시안 정렬, 저장·새로고침 복원을 포함한다. 테스트는 임시 데이터와 비어 있는 공급자 설정을 사용했다.

로컬 접속: <http://127.0.0.1:5273/avatar.html>

API: <http://127.0.0.1:8000/health>

실행 명령: 루트에서 `.\start-local.ps1`.

로컬 health는 PostgreSQL 연결 불가로 `degraded`다. 공장 capabilities의 `ready`는 true지만 실제 유료 공급자 성공이나 DB 정상 동작 증거가 아니다. DB 설정 변경·migration은 수행하지 않았다.

### 추가 E2E 재실행

다음 임시 fixture 경로는 이번 실행에서 생성했다. 임시 파일이 삭제되면 backend에서 해당 `run_*_check.py`를 실행하고 새 root로 교체한다.

```powershell
# frontend/에서 실행
$env:WORKSPACE_TEST_API_PORT = '18012'
$env:WORKSPACE_TEST_FACTORY_ROOT = Join-Path $env:TEMP 'maple-equipment-check-k_ksdrcd'
npx playwright test tests/maple-factory.spec.ts -g 'compiled Maple'
$env:WORKSPACE_TEST_STANDARD_ROOT = Join-Path $env:TEMP 'avatar-standard-check-0z6s0qj3'
npx playwright test tests/avatar-standard.spec.ts -g 'real Blender|canonical template|generated design'
```

## 검증 경계

유료 OpenAI·Meshy 생성, 운영 PostgreSQL, 실제 캐릭터의 외형·변형 승인, 공개 배포는 수행하지 않았다. Blender·브라우저 통과는 자체 제작 fixture의 기술 검증이다. 기존 `data/` 에셋에 승인 기록을 추가하거나 수정하지 않았다.
