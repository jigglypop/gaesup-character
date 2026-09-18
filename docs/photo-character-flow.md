# 사진 한 장 → 조립된 캐릭터

사용 화면은 `/` 하나다. `index.html`과 기존 `avatar.html` 북마크는 동일한 `character-app.tsx`를 실행하며 `stage`, `view`, `tab`은 제거한다. 예전 고정 몸·이미지 편집·GLB 변환·옷장 페이지로 이동하지 않는다.

사진 업로드 → **캐릭터 만들기** → 이미지 7개 → 파츠 3D 7개 → 몸의 Meshy 리깅 → 로컬 파츠 조립 → 같은 화면의 캐릭터 전체 동작으로 이어진다. 새 작업의 `auto_assemble=true`가 최종 조립을 서버에서 실행하므로 브라우저를 닫아도 별도 조립 버튼이 필요하지 않다. 현재 기본 파츠는 몸, 앞머리, 뒷머리, 모자, 상의, 하의, 신발이다. 세부 슬롯 확장과 얼굴 UV 공장은 이미지 명세의 후속 범위다.

기준 몸의 포즈는 제작 조건이다. 결과 화면은 기본적으로 걷는 조립 캐릭터를 표시하고, 파츠 켜기·끄기와 월드 이동을 제공한다. 파츠는 몸과 동일한 Bone 객체를 사용한다. 새 파츠 파일을 모두 검증한 뒤 함께 교체하고, 파일 로딩·골격·해시 오류 때 기존 조합을 유지한다. 파츠 변경으로 animation mixer를 다시 생성하지 않는다.

조합 저장은 작업·소유자·조립 버전별로 관리한다. `If-Match`로 저장 충돌을 막고 `Idempotency-Key`의 결과 영수증을 보존한다. 응답 유실 후에는 같은 요청을 복구하고 서버의 현재 조합을 다시 읽는다. 복구 사이에 다른 탭에서 저장했으면 그 최신 조합과 revision을 적용하며, 이전 영수증의 조합을 최신 저장 상태로 표시하지 않는다. 조합 저장은 외형 승인이 아니다. 다운로드하는 조립 GLB에는 전체 파츠가 들어 있고, 화면에서 저장한 선택은 별도로 복원된다.

## 실행과 서버 일치

```powershell
./start-local.ps1
```

기본 UI는 `http://127.0.0.1:5273/`, API는 `http://127.0.0.1:8013`이다. Vite의 기본 프록시도 8013이며 테스트·다른 실행에는 `BACKEND_URL`로 재지정한다. 기존 8000의 오래된 프로세스를 단순히 살아 있다는 이유만으로 새 API로 취급하지 않는다.

`GET /api/avatar-factory/capabilities`의 `character_pipeline=parts_to_character_v1`을 시작 스크립트와 화면이 확인한다. 이 값이 없으면 새 생성 제출을 막는다. `slots.0`에서 body를 거절하고 `production_mode`, `body_purpose`, `rig_with_meshy`, `motion_actions`를 extra input으로 거절하는 오류는 이 새 계약을 모르는 구형 서버에 연결됐다는 증거다.

## 복구

- 이미지·3D 생성 중 중단: 기존 이미지 작업 재개 경로를 사용하고 불확실한 유료 요청을 반복하지 않는다.
- 리깅·동작 중 중단: 같은 캐릭터 작업의 **계속 만들기**로 기존 Meshy 작업을 조회한다.
- Meshy 완료 후 로컬 조립 실패: Meshy worker의 완료 상태를 보존한다. **계속 만들기**는 로컬 조립만 재개한다.
- 새로고침: 사진, 작업, 조립 결과와 저장된 파츠 조합을 같은 화면에서 복원한다.

## 검증과 남은 경계

`uv run pytest -q`는 API 계약·권한·저장 충돌·응답 유실, 파츠 생성에서 리깅으로의 연결, 리깅 완료 후 자동 조립과 로컬 실패 재개를 검사한다. provider 호출은 테스트에서 대체한다.

`frontend/tests/character-factory.spec.ts`는 주소 통합과 실제 로컬 API 사진 업로드, 한 버튼의 파츠 세트 요청을 확인한다. 생성 POST만 가로채므로 실제 새 유료 생성 완료 증거는 아니다.

`frontend/tests/native-assembly.spec.ts`는 실제 API에서 몸·파츠 GLB를 받아 공통 본, 6개 파츠의 변형, 조합 저장 응답 유실·복구, 월드 이동을 확인한다. `WORKSPACE_TEST_NATIVE_SOURCE`에 기존 조립 버전 디렉터리를 지정하면 그 파일의 검증된 사본을 임시 데이터에 사용한다.

```powershell
cd frontend
node scripts/check-native-assembly.mjs http://127.0.0.1:5273 c6251dc143b9cb7628e94432
```

위 실제 작업 검사에서는 서버 데이터를 변경하거나 제공자를 호출하지 않고 걷기·달리기·점프·앉기와 월드 이동, 본 공유, 몸·파츠별 정점 변화를 측정하고 `data/verification/native-assembly-*/`에 보고서·캡처를 남긴다. 기존 24본 Meshy/Blender 산출물로 동작이 확인되었다. 새 레퍼런스의 전체 유료 생성과 자동 피팅의 외형 품질은 별도 실제 생산 증거가 필요하다. 현재 피팅 후보의 헤어 접합·옷 관통·변형은 시각 검수 대상으로 유지한다.

### 2026-09-18 재검증

- 실산출물: 작업 `c6251dc143b9cb7628e94432`, 조립 버전 `591f983fa924de0835243e7b`. 실행 중인 결과 화면은 `http://127.0.0.1:5275/?character=A&job=c6251dc143b9cb7628e94432`다.
- [동작 측정 보고서](../data/verification/native-assembly-1789728277085/report.json): 실제 WebGPU, 공통 본 24개, 파츠 6개. `walk`, `run`, `jump`, `sit` 각각에서 몸과 모든 파츠의 유한한 정점 좌표 변화가 기준을 넘었다. 모자 탈착과 W 이동을 통과했고, 브라우저 오류와 POST·PUT·PATCH·DELETE 요청은 없었다. 사용한 GLB들의 SHA-256을 보고서에 함께 고정했다.
- [걷기 캡처](../data/verification/native-assembly-1789728277085/walk.png), [달리기](../data/verification/native-assembly-1789728277085/run.png), [점프](../data/verification/native-assembly-1789728277085/jump.png), [앉기 클립](../data/verification/native-assembly-1789728277085/sit.png), [월드 이동](../data/verification/native-assembly-1789728277085/world.png).
- `uv run pytest -q`: 203개 통과. `npm run build`: 타입 검사·빌드 통과. 기존 번들 크기·정적/동적 import 중복 경고는 남아 있다.
- 관련 브라우저 검사 5개 통과: 단일 화면 이동 1개, 사진 업로드·생성 요청 계약 1개, 실산출물 사본의 조립·저장 복구·월드 이동 1개, 응답 유실 뒤 다른 탭의 최신 조합 복구 1개, Meshy 동작 컴포넌트의 기본값 저장·재접속 1개. Meshy 설정은 테스트용 진입점에서 컴포넌트를 직접 실행하며 제품 화면의 추가 페이지를 만들지 않는다. 이전 개별 페이지를 전제로 한 전체 E2E 모음의 통과를 의미하지 않는다.

동작 판정은 공통 골격과 샘플 정점의 움직임 증거다. 모든 프레임의 의상 관통·피팅 품질이나 새 사진의 유료 생성 완료를 증명하지 않는다. 이번 재검증은 기존 산출물만 사용했다.
