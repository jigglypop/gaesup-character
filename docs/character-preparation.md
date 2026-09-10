# 캐릭터 리깅·동작·의미 파츠

## 실행 흐름

브라우저 `http://127.0.0.1:5273`에서 캐릭터를 등록하고 이미지 또는 GLB를 가져온다. 리깅되지 않은 GLB도 등록할 수 있다. 이미지는 생성 방식 선택 → 생성 → 상태 조회·다운로드 후 `리깅 + 기본 동작 5종 가져오기`로 진행한다. 기존에 리깅된 Meshy 작업은 재사용한다. 출처를 확인할 수 없는 외부 GLB는 Meshy에 GLB data URI로 제출해 새 리깅을 얻는다.

2026-09-10 공식 API 확인:

- [Image to 3D](https://docs.meshy.ai/en/api/image-to-3d): `meshy-7` + `standard` 또는 `meshy-t2` + `smart-topology`. 후자는 native separated parts를 제공하며 최대 15,000면이다. 파츠의 의미나 리깅 이후 메시 유지까지 보증하지 않는다. T2에서는 지원이 명시되지 않은 `image_enhancement`를 보내지 않는다.
- [Rigging](https://docs.meshy.ai/en/api/rigging): `POST /openapi/v1/rigging`, `input_task_id` 또는 `model_url`, `height_meters`. 텍스처를 가진 휴머노이드 GLB가 대상이다. GLB 입력은 +Z 전면이 필요하다. walking/running은 결과의 optional basic animations다.
- [Animation](https://docs.meshy.ai/en/api/animation): `POST /openapi/v1/animations`에 `rig_task_id`와 `action_id`. 무료 `GET /openapi/v1/animations/library`를 제출 전에 조회해 ID의 현재 유효성을 확인한다. 실제 계정 조회에서 678개를 확인했으며 갯수는 고정 계약이 아니다.
- [Auto Split](https://docs.meshy.ai/en/api/auto-split)은 무텍스처 프린팅용이며 컷의 얇은 부분을 보강한다. 텍스처·원본 weights 보존이 필요한 의상 분절에는 사용하지 않는다.

기본 슬롯은 idle=0, walk=1, run=14, jump=466(Regular Jump), fall=502(Fall 1 / FallingFreely)다. ID 86은 key가 Basic_Jump여도 실제 이름은 Jump Attack이므로 기본 점프로 사용하지 않는다. API `prepare_character` 입력의 `actions`로 각 ID를 바꿀 수 있다. 기본 walk/run이 제공되면 이를 사용하며 별도 library action ID를 사용했다고 기록하지 않는다. 물리 낙하 상태와 클립 동작은 별도로 게임 안에서 검수한다.

## 한 번 실행과 복구

`prepare_character`는 한 UI operation 안에서 리깅 → 최대 동작 5개 → 다운로드 → 동일 리그의 GLB 병합까지 실행한다. 기본 제출 한도는 6개(리깅 1개 + 동작 5개)이고 walk/run 재사용 시 새 요청 수는 줄어든다. 요청 수 한도는 크레딧 금액 견적이 아니다. 기존 실패/거절된 시도는 자동 재제출하지 않는다.

각 POST 전에 `motion-pack.json`에 `submission_uncertain`을 저장한다. 응답의 ID를 받은 뒤부터는 해당 ID를 조회한다. 동작별 상태·ID·사용 크레딧·출처와 파일 해시를 보관한다. 다운로드 클라이언트에는 API Bearer token을 전달하지 않는다. 정상 처리 중 브라우저를 닫아도 실행은 계속된다. 단일 서버 worker를 사용하며 처리 시간 20분 초과 시 `awaiting_provider`, 서버 중단 시 기존 operation의 복구 필요 상태를 표시한다. `resume_character`는 처음 수락한 원본·한도·작업 ID를 사용한다. ID를 받지 못한 단계는 `recover_motion_task`로 먼저 복구해야 한다.

수동 복구는 Meshy 계정에서 확인한 해당 단계의 task ID를 입력한다. task GET 응답이 입력 rig/action ID를 생략할 수 있으므로, 이 경우 자동으로 출처 확인을 완료했다고 주장하지 않고 `operator_task_id`로 기록한다. 응답에 입력 ID가 있으면 기존 단계와 대조하고 불일치 시 거절한다.

`motions/character.glb`에 idle/walk/run/jump/fall을 명명해 병합한다. 관절 이름의 완전한 집합이 일치해야 하며 임의의 노드 인덱스 fallback을 사용하지 않는다. 원래 기본 모델과 개별 동작 GLB도 보존한다. gaesup-world에서 실제 속도와 수직 속도에 따라 클립을 선택한다. 라이브러리 클립이 있다는 사실은 보행 접지·낙하 동작 품질의 승인을 뜻하지 않는다.

## 기존 모델의 의미 파츠 편집

모델 검사 → `파츠 영역 편집` → 역할 선택 → 왼쪽 드래그로 면 칠하기 → `선택 영역 분리`. 오른쪽 드래그는 회전, 휠은 확대다. Alt 또는 지우기로 선택을 제거하고 되돌리기로 스트로크를 취소한다. 원본 URL/hash별 브라우저 세션 초안을 보관한다.

`separate_parts` 입력은 `source_sha256`과 `selections[{node_index,primitive_index,role,faces}]`다. 몸/머리/헤어/모자/상의/바지/치마/원피스/신발/기존 의상/액세서리/눈/기타를 지원한다. 겹치거나 범위를 벗어난 면, 다른 원본의 해시를 거절한다. 미선택 면은 `other`로 보존한다. 전체 모델의 의미 영역을 자동 판정하는 기능은 아니다.

GLB의 원본 vertex/UV/normal/JOINTS/WEIGHTS accessor와 binary를 보존하고, 파츠마다 삼각형 index만 만든다. 원래 transform node는 유지하며 child mesh가 동일 skin을 참조한다. 원본 면 수와 출력의 실제 렌더 면 수가 같아야 한다. Blender의 독립 background 프로세스가 editable `.blend`와 기본 자세 렌더를 만든다. GLB 원본은 덮어쓰지 않는다. 재질 분리는 별도의 후보 생성 기능이다.

가려진 두피·몸·의상 안쪽 면은 이 분리로 생성되지 않는다. `body_coverage`는 검토 전 `unknown`, 원본에 몸이 없으면 `partial`이다. body와 적어도 하나의 의상 역할, 현재 버전의 구조 검사, 외형·동작 검토가 있어야 승인할 수 있다.

## PostgreSQL

GLB/Blender/JSON 작업 일지는 파일 저장소가 보유하고 PostgreSQL은 트랜잭션 단위로 조회 인덱스를 갱신한다. 기존 `/api/world/*` DB와 별도 환경 변수·schema를 쓴다. 앱 시작 시 마이그레이션을 자동 적용하지 않는다.

```powershell
# .env에 CHARACTER_DATABASE_URL 설정 후 저장소 루트에서 실행
uv run python -m src.character_db migrate
uv run python -m src.character_db sync
uv run python -m src.character_db status
```

`gaesup_character` schema:

| 테이블 | 기록 |
|---|---|
| characters | 소유자, 키, 등록·활성 설정 |
| asset_versions | 해시, 상대 storage key, 크기, rig 출처 |
| operations | idempotency에서 파생된 작업 ID, 입력 fingerprint, 불변 입력·실행 상태 |
| provider_tasks | 단계, Meshy task ID, animation action ID, rig ID, 상태·크레딧 |
| parts | 모델 버전 + node ID, 의미 역할, body coverage |
| animation_clips | 병합 모델 버전 + 슬롯, 원본 클립 해시·Meshy task ID |
| reviews | operation + 모델 버전, 검토자·결정·검수 증거 |

Migration 002는 기존 테이블을 변경하지 않는다. rollback은 먼저 앱에서 `CHARACTER_DATABASE_URL`을 제거하고, 필요하면 down SQL로 schema를 `gaesup_character_002_archive`로 바꿔 보관한다. DROP이나 데이터 삭제는 하지 않는다. 재적용 시 보관 schema에서 복원하거나 파일 일지를 다시 색인한다.

변경 수락/완료 후 DB를 동기화한다. 실패하면 해당 run에 `postgres-sync.pending`을 남기며 `sync` 명령으로 재생한다. DB 장애 때문에 성공한 유료 동작을 재실행하지 않는다. 이 단계는 DB를 큐나 다중 worker 스케줄러로 사용하지 않는다. 파일·DB를 함께 백업해야 한다. 현재 개발용 DB는 별도의 로컬 PostgreSQL 18 인스턴스 `127.0.0.1:55432/gaesup_character`다.

## 검증

- `uv run pytest -q`: 요청 유실·재개·제출 한도, 기본 클립 재사용, 원본 face/weights/animation 보존.
- `backend/`에서 `uv run python tests/run_blender_parts_check.py`: 실제 Blender로 재질 및 면 선택 분리, GLB/Blend/렌더 확인.
- `frontend/`에서 `npm run build`, `npm run test:e2e`: 실제 격리 API, 재접속·검수·업로드.
- 실행 중인 앱에 `node scripts/check-world.mjs`, `node scripts/check-parts.mjs`: 실제 WebGPU/gaesup-world의 A 모델 이동과 면 선택·되돌리기·월드 복귀 확인.

현재 A의 출처는 기존 Meshy 생성 + 15-bone local fallback이다. 과거 rigging 422를 성공으로 덮어쓰지 않는다. A의 `pose_check`는 Meshy 기본 동작 5종을 대신하지 않는다. 새 유료 생성/리깅/애니메이션 작업 없이 구현과 검증을 진행했다.

실제 A는 원본을 유지한 7개 파츠 후보(모자·헤어·머리·몸·상의·치마·신발)를 만들었다. 30,894면과 15관절을 보존하고 WebGPU 월드 이동과 pose_check를 확인했다. 모자/헤어 경계의 혼입과 열린 절단면은 남아 있으며 `changes_requested`, `body_coverage=partial`로 기록했다. 이 후보를 완성된 의미 분절이나 승인된 교체 의상 세트로 취급하지 않는다.
