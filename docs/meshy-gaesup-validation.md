# Meshy → gaesup-world 파츠 생산 검증

## 2026-09-17 추가 검증: 실제 Meshy 골격과 의상 배치

아래 2026-09-16 기록은 이전 23본 조립 경로의 기록이다. 현재 전신 결과 화면은 실제 Meshy 결과를 사용한다.

- 공장 작업 `f8bf4ba9c5490ec81eb2d452`: 전신 생성 task `01a0aac1-b314-7688-a785-ed23bb5d2519`, Meshy 리깅 task `01a0aad1-2e3f-7267-bafc-c46338855e80` 성공. 원본 24개 본·가중치를 유지하며 실제 Meshy 기본 걷기·달리기를 보존했다.
- 실제 UI에서 WebGPU·동작 정점 변화·새로고침을 확인했다. 이 기술 통과는 외형 승인이 아니다. 달리기에서 큰 머리/모자가 팔 동작에 끌려가는 결함이 보인다. 원본 walking/running GLB와 병합 결과의 메시·스킨·rest transform·inverse bind·기본 BIN이 동일하므로 병합 중 골격을 교체한 문제는 아니다.
- 해당 모델을 새 규격 후보 `1319b4b83054c753ec7b9879`로 정규화했다. 1.20m, 원본 24본, 2048px 정면/측면/후면, GLB·BLEND와 동작 렌더를 저장했다. 실제 외형을 확인한 뒤 `changes_requested`를 기록했다. 헤어·상의·하의·신발이 붙어 있고 리깅 변형이 있어 승인된 교체용 몸이 아니다.
- 사용자가 저장한 실제 Meshy 기본 동작 ID는 walk 692, run 539, jump 468, fall 503, sit 60, idle 252다. 설정 저장과 해당 동작의 유료 생성은 별개이며 현재 캐릭터에는 이 여섯 추가 동작을 제출하지 않았다.
- 고정 몸 의상 배치 API·화면·중단 복구를 구현했다. 실제 의상 배치 유료 생성, 정렬·피팅, 갈아입기 검수는 아직 완료하지 않았다. 첫 새 기준 몸·의상 대상과 시도 상한은 `data/avatar-standard/1/plans/wardrobe-first-batch.json` 초안에 있으며 제출되지 않았다.
- 실제 브라우저 점검에서 기본 자세가 100분의 1로 축소되는 뷰어 오류를 별도로 발견했다. 센티미터 단위 부모를 둔 Meshy 골격에 `Skeleton.pose()`를 호출하면 원본 로컬 변환이 바뀌었다. 원본 GLB의 로컬 자세를 저장·복원하도록 수정했다. 실제 기준 몸의 정지 화면과 WebGPU 렌더를 다시 확인했으며, 원본 파일·본·inverse bind는 수정하지 않았다.
- 자동 새로고침 때 3D 화면이 중복되던 같은 React key 충돌도 수정했다. 확인 스크립트는 `frontend/scripts/check-standard-batch.mjs`와 `check-meshy.mjs`이며 증거를 E2E가 지우지 않는 `data/verification/`에 저장한다. 초기의 빈 캔버스 캡처는 모델 표시 성공의 증거로 사용하지 않는다.

Meshy [Rigging API](https://docs.meshy.ai/en/api/rigging)는 팔다리 구조가 명확한 휴머노이드가 필요하다고 명시한다. [Image to 3D API](https://docs.meshy.ai/en/api/image-to-3d)의 `pose_mode: a-pose`를 사용하되, 제공자 성공 상태만으로 정확한 몸·관절·의상 적합성을 승인하지 않는다.

## 2026-09-17 즉시 옷장 교체 검증

기준 몸을 유지한 채 같은 본 객체에 파츠를 붙이는 `NativeWardrobe`와 착용 선택 저장 API·화면을 추가했다. 실제 Blender로 만든 폐기용 24본 몸·상의·모자에서 원본 본 공유, 의상 정점 변형, 같은 슬롯 교체, 교체 중 mixer 시간 보존, 파일/골격 불일치 거절을 확인했다. 현재 착용을 저장한 뒤 응답이 끊겨도 새로고침 후 같은 key·본문·revision으로 복구한다. 충돌이나 다운로드 오류는 기존 화면의 옷을 유지한다.

이 검사는 **자체 제작 fixture**이며 실제 Meshy 의상 배치를 생성하거나 외형 승인한 결과가 아니다. 실제 원본 후보 두 개는 아직 미승인이고 첫 유료 배치 초안도 미제출이다. 증거는 [검증 기록](../data/verification/native-wardrobe-20260917/report.json)과 [옷장 화면](../data/verification/native-wardrobe-20260917/fixture-wardrobe.png)에 저장했다. 화면의 실제 렌더러는 WebGPU다.

전체 백엔드 177개와 프론트 빌드가 통과했다. 24본 표준 fixture와 Meshy 복구 fixture를 함께 사용한 전체 브라우저 검사는 22개 통과, 별도 완성 전신/장비 fixture가 필요한 2개 제외다. 검사용 서버 연결이 중단됐던 실행은 통과 증거에서 제외하고 격리된 프로세스에서 전체 검사를 완료했다.

이후 성공 HTTP 응답의 JSON이 중간에 잘린 경우도 연결 유실로 처리하도록 보완했다. 요청 영수증을 지우지 않고 같은 key로 복구하며, 연결 단절·잘린 JSON·충돌 및 재접속의 추가 브라우저 검사 3개와 빌드가 통과했다.

## 2026-09-16 이전 경로 기록

이하의 신규 유료 제출 0회와 제안 상한은 그 날짜 작업 기준이다.

## 실제 에셋 검증

- 원본: `data/image/A.png`, SHA-256 `5847b126384dec9a842155ee5d454ce0de81a5ffec2f0f6038253c5e9e70331c`.
- 기존 이미지 생산 버전: `a6c8ef70cba44a9d95697176`.
- Meshy의 face/hairBack/hairFront/hat/top/bottom/shoes task 7개를 이번에 GET 조회: 모두 HTTP 200 / SUCCEEDED.
- 작업별 과거 consumed_credits는 30이다. 이번 실행의 새 과금이 아니다.
- 보존 원본, 개별 generated.glb, 조립 산출물의 해시 모두 일치.
- 런타임 파츠: body + face/hair/hat/top/bottom/shoes. 앞·뒷머리는 hair 슬롯에 2개 메시로 합쳐진다.
- 각 출력 GLB 구조 검사 오류 없음. 공통 23본 리그 1개를 사용한다.
- 현재 리그 출처는 `canonical_rebind`이며 Meshy 리깅이 아니다.

증거: [파일·제공자 검사](../data/verification/maple-parts-20260916-001048/report.json).

## 실제 런타임 검증

[검수 화면](http://127.0.0.1:5273/avatar.html?stage=glb&character=A&job=a6c8ef70cba44a9d95697176&tab=result)

현재 gaesup-world 1.0.30 / R3F 9.7.0 기반 실제 앱에서 다음을 확인했다.

- 실제 렌더러 backend: `webgpu`.
- idle/walk/run/jump/sit/armsUp/crouch 7개 클립 존재 및 시간 진행에 따른 뼈 변환 변화.
- face/hair/hat/top/bottom/shoes 6슬롯 해제·재장착 성공, skeleton ID 유지.
- 모든 skinned mesh가 같은 skeleton을 사용.
- 새로고침 후 동일 생산 버전 복원.
- 브라우저 오류 0, 서버 변경 요청 0. 이 검사는 모든 POST/PUT/PATCH/DELETE를 차단한다.

[런타임 결과](../frontend/test-results/factory-a6c8ef70cba44a9d95697176-1789485116272/result.json), [화면](../frontend/test-results/factory-a6c8ef70cba44a9d95697176-1789485116272/rest.png).

재실행:

```powershell
cd frontend
node scripts/check-factory.mjs a6c8ef70cba44a9d95697176
```

## 외형 및 동작 한계

실제 정면 렌더와 브라우저에서 앞머리·얼굴 간 큰 이마 간격, 허리·치마 연결 틈을 확인했다. 이 버전은 외형 수정 대상으로 남긴다. 현재 클립은 로컬 변형 검사용이며 Meshy 동작이 아니다. 뼈가 움직인다는 검사만으로 자연스러운 보행이나 변형 품질 승인을 대신하지 않는다.

## 이번 구현

- `character_cli rig-model --model <GLB> --height <m>`: 기존 조립 GLB를 보존하고 Meshy의 model_url Data URI 리깅 경로로 제출할 수 있다. 아직 실제 제출하지 않았다.
- 모델 해시·원본 복사·제출 의도를 먼저 저장한다. 응답 유실 시 기존 task ID를 복구하며 같은 run 재제출을 거부한다.
- `generate --body-type quadruped`: 4족 생성에 인간형 A-pose 옵션을 보내지 않는다.
- 4족의 공개 API 리깅은 제출 전에 거부하고 웹앱 경로를 안내한다.
- 재조립은 모델·작업 영수증을 검증하고 이미지/Meshy 제출 상한을 실행 시에도 검사한다. 영수증이 없어져도 0회 예산의 재조립이 새 유료 생성으로 바뀌지 않는다.
- rebuild API 경로 계약 테스트를 현재 스키마에 맞췄다.
- 검증: 전체 pytest 137 통과, 프론트 빌드 통과. 큰 JS 청크 경고는 남아 있다.

## 4족과 Meshy 리깅의 현재 지원 경계

[공개 Rigging API](https://docs.meshy.ai/en/api/rigging)는 표준 2족 휴머노이드만 지원 대상으로 명시한다. [웹앱 리깅](https://docs.meshy.ai/en/webapp/guides/3d-model/rigging)은 휴머노이드와 4족을 지원한다고 명시한다. 현재 연결된 브라우저가 없어 웹앱 리깅 조작은 수행하지 못했다.

4족 Meshy 리그를 가져온 뒤에는 일반 GLB 뷰어/gaesup-world 캐릭터 경로에서 원래 skeleton을 보존해야 한다. 현재 옷장 `AvatarRuntime`은 두 인간형 rig ID와 23본 계약만 지원하므로 4족을 그 계약으로 재명명하면 안 된다. 4족의 실제 생성·리깅·보행 및 별도 파츠 계약은 아직 미완료다.

## 제안한 다음 유료 실행 — 미승인·미제출

1. 기존 A의 생성 파츠를 재사용하고 외형 연결을 로컬 새 버전으로 보완.
2. 보완한 휴머노이드 조립본에 Meshy 리깅 1회: 공식 API 가격 5 credits.
3. 4족 고양이 원본 확정 후 Meshy 7 textured 생성 1회: 공식 API 가격 30 credits.
4. 합계 신규 API 상한 35 credits, 자동 유료 재시도 없음. 별도 애니메이션·리메시·4족 웹앱 리깅은 이 상한에 포함하지 않음.

가격 출처: [Meshy API Pricing](https://docs.meshy.ai/en/api/pricing). 대상 또는 단계가 바뀌면 제출 전에 계획을 갱신한다.
