# 작업 상태

2026-09-21 01:14 KST 저장 결과 / GLB 관리자 구현:

- 헤어 배치 `313c25afb1a7b4a00e34a36c`는 paused, 01~14번 실제 생성·조립·S3 저장 완료(14/18). 15~18번은 Meshy HTTP402로 접수 거절, provider task ID 없음. 추가 결제/충전/재제출은 하지 않았다. 완료본과 원본 입력은 보존하며 결제 상태가 해결되면 기존 배치/하위 작업으로 재개한다.
- GLB 라이브러리: 파일 선택/드롭/붙여넣기(256MiB), 원본 S3 등록·목록·다운로드, 나중에 파츠 몸 맞추기·기존 골격 연결 또는 본체 새 리깅을 선택한다. 원본 등록에는 기준 몸·Blender·유료 작업이 필요 없다. 실제 신규 GLB 업로드나 새 리깅은 실행하지 않았다.
- 관리자: 캐릭터 카드의 임의 파츠 fallback을 제거하고 실제 조립 저장 버전을 표시한다. 선택 버전의 원본/피팅/전체 조립 GLB, 정면·측면·후면, 기준 몸·버전·피팅 규격·골격·동작·파일 SHA, 저장 착용/헤어 색상/표정을 표시한다. 실제 저장 조합·표정은 기존 NativeAssembly로 연다.
- 프론트 TypeScript/Vite 빌드, 백엔드 compileall/패키지 빌드 통과. 동일 GLB 후처리 키 재접속 시 기존 자식 작업을 복구하도록 보완했고 목록 조회에서 GLB 전체 바이트 재읽기를 제거했다. pytest/Playwright/유료 생성 검사는 실행하지 않았다.
- 실행: `./start-local.ps1`, UI5273/API8104, PID25556, revision `e16e717babba8c517d8ed309508c1a6ba76617d628af9199596b51640d96c893`, 로그 `data/local-runtime/48d1072915904a9e8aaa956dba15c316`, FactoryReady True. 기존 API8103/PID6712 보존. PostgreSQL DNS 문제로 전체 health는 기존 degraded 상태다. 신규 GLB 목록 GET200 및 OpenAPI 경로 확인.
- CUA 수동 확인: GLB 선택/드롭/붙여넣기 화면, 관리자 선택 버전 `d0eb80cb6a39c9d4c64ded54` / `6a35dcd65a71a8cfab87160f`의 실제 조립 GLB 정면·후면 전환, 24본·동작·저장 색상·피팅 규격 표시 확인. 초기 데이터 로딩 전 undefined 접근으로 빈 화면이 되는 오류를 수정했다. 원본 모델 선택에 몸/헤어 이름을 붙이고 실제 part_name을 상세 목록에 표시한다.
- 외형 한계: 새 시트 헤어02 후두부에 큰 두피 노출이 보인다. 14/18은 실제 생성·조립·S3 저장 개수이며 전체 외형 품질 승인 수가 아니다. 이 턴에서 후두부 재피팅이나 새 유료 재생성은 실행하지 않았다.

2026-09-21 GLB 에셋 직접 등록 / 관리자 상세 요청 추가:

- 진행 중 사용자 지시: 에셋 GLB 직접 등록 후 선택적으로 리깅·몸 맞추기, 관리자에서 기본몸과 같은 결과를 상세히 보기. 원본 등록은 기본몸·리깅 없이 S3에 그대로 저장하고 후처리는 별도 작업으로 구현 중이다. 신규 GLB 또는 유료 리깅 실행은 요청받지 않았으므로 코드/API 준비만 수행한다.
- 관리자 차이 원인: 캐릭터 카드가 선택 버전 대신 root 기본몸 assembly를 유지하거나 첫 generated 파츠를 전체 캐릭터처럼 표시했다. 선택한 저장 버전·원본/피팅/조립 산출물을 구분한 큰 미리보기, 카메라 방향과 실제 파일/골격/동작 정보를 추가 중이다.
- 기존 헤어 배치 `313c25afb1a7b4a00e34a36c`는 계속 진행 중. 01:08 KST 11/18 조립·저장 완료, provider 작업 ID 발급 14/18. 15~18번은 HTTP402로 제출 거절, task ID 없음. 결제/크레딧 확인 없이 유료 재제출·충전하지 않는다. 접수된 1~14번 저장을 마무리하고 거절 입력/원본은 그대로 보존한다.

2026-09-21 첨부 hair.png 여성 헤어 18종 실행 재개:

- 최신 사용자 지시: `backend/assets/avatars/image-design/hair.png` 전체 분할·병렬 실제 생성 및 컬러피커. 기존 폴더 10종과 별도의 시트 18종을 이번 범위로 확정한다. 이미지 생성 0회, Meshy 3D 최대 18회, 신규 리깅/동작 0회, 최대 4개 병렬.
- 원본 SHA `7778d4e66c9d4e578c9daf0b51863b9b880d2db8ca295559fcbac9a627e4a4d1`가 현재 파일과 일치. 기존 S3 분할 시트 `af0dea41455980f7791c7134`의 18종/54뷰를 재사용한다. 18종 배치 접수 기록은 없음을 조회했다. 기존 폴더 배치 `aa08599e1c96639a7cb6a1dc`는 다시 제출하지 않는다.
- 기준 몸 `7602726d8f4cb5f5792eaf11` / `beeb29328e3ece5472a70b27`, body SHA `5a2b62d5e79e0614d8aa05eb34fdc265538999a092f5246011b588042dedc92b`의 현재 소유권·삭제 여부·저장 파일 확인. 고정 요청 키 `female-hair-sheet-20260921-v1`. Meshy 7.1 / geometry 2K / texture 4K / PBR / remesh false.
- `./start-local.ps1` 실행: UI5273/API8103, FactoryReady True, 로그 `data/local-runtime/f8da103e72b84cd5bd1b3aa720a13677`. 기존 PostgreSQL degraded. 실제 접수와 완료 수는 후속 기록으로 갱신한다.
- HTTP202 배치 접수 `313c25afb1a7b4a00e34a36c`, S3 입력 영수증 `avatar-factory/1/part-imports/20260921-female-hair-sheet-18.json`. 최초 4개 provider task ID `01a0bf71-7f74-72f3-9646-42e827662677`, `01a0bf71-7f6a-764b-bd7c-dc97aa50d935`, `01a0bf71-7f84-7293-8af6-bdb66f5402c4`, `01a0bf71-7f7f-7619-b5d6-63da99149fdd` 확인. 나머지 14개 대기.
- 기존 컬러피커·원본 색 복귀·명암/alpha/PBR 보존·조합 색 저장/복원 코드를 유지했다. 배치 접수 성공 후 목록 조회 실패를 새 제출로 오인하지 않도록 접수 응답을 즉시 목록에 반영하고 재개 중복 클릭을 방지했다. frontend npm run build, backend compileall 및 uv build 통과. pytest/Playwright 미실행.
- CUA의 실제 Chrome UI에서 기존 저장 헤어 `ddcf004e5cfe0591ec6213d3`에 색 `#d04435`를 적용해 붉은 헤어와 명암 유지, WebGPU 표기를 확인한 후 원본 색으로 복귀했다. 조합 저장은 변경하지 않았다. 시트 18종의 실제 조립 산출물은 아직 생성 중이다.
- 00:42 KST: 3D 파일 수신 4/18, 조립·S3 저장 2/18, 실제 요청 6/18, 오류 없음. 2번 첫 저장 산출물 `d0eb80cb6a39c9d4c64ded54` / `6a35dcd65a71a8cfab87160f`, hair SHA `9ff5ad4de9276bcc25d39b2b025eda1fe9056ced805d2952859fb21ae8946dcb`. 현재 진행 조회: `GET /api/avatar-factory/part-batches/313c25afb1a7b4a00e34a36c`.
- 00:49 KST: 1~6번 조립·S3 저장 완료(6/18), 7~10번 실제 생성 중, 11~18번 대기. 실패·재제출 없음.
- 00:58 KST: 1~8번 조립·S3 저장 완료(8/18), 9번 조립 및 10~12번 생성 진행. 현재까지 실패·재제출 없음.

2026-09-20 backend/assets/hair 여성 헤어 10개 실행:

- 후속 사용자 결함 보고: 거의 모든 헤어의 뒤통수 노출/구멍. CUA로 실제 S3 후면 확인: 여성 헤어01은 후면 아래 두피 노출, 여성 헤어06(`18aed31318ece4cba646d9c1`/`f144326b2d049840bf7cff10`)은 후두부 중앙에 큰 두피 노출. 저장 성공을 시각 품질 완료로 간주하지 않는다. 기존 10개 Meshy는 모두 성공했으며 새 유료 생성 없이 실제 헤어 원본으로 피팅을 수정한다.
- 원인 후보/수정: 기존 전체 헤어 bbox 균일 피팅 후 두피 교정이 0.025m로 제한되어 깊은 겹침이 남는다. 실제 두상 표면까지 scalp 정점을 이동하고 목 아래 긴 머리는 기존 제한을 보존하는 `measured-skull-v1` 추가. 면/UV를 추가·복제하지 않는다. `shared-size-v20-measured-hair-scalp`, production revision18. 이전 접수 입력은 이 옵션이 없어 동작을 보존한다. backend compileall/패키지 빌드 통과. 먼저 06번 재피팅 키 `female-hair06-skull-fit-20260920-v1`로 실제 수정 결과를 확인하며, 후면 해결 전 전체 완료를 주장하지 않는다.

- 최신 사용자 지시: 폴더의 PNG 10개(f_hair1~8, f_hair10, f_hair29)로 실제 여성 헤어 10종 생성, 최대 4개 병렬, 컬러피커 연결. 이전 18종 시트는 새로 제출하지 않는다. 실제 범위는 이미지 생성 0회, Meshy 3D 최대 10회, 새 리깅/동작 0회다.
- 원본 10개 및 분할 30뷰를 S3에 저장했다. 8개 파일은 등분 경계가 머리카락을 지나므로 투명 경계 자동 분할을 추가했다. 원본 픽셀/공통 캔버스 배율을 보존한다. 입력 영수증은 S3 논리 경로 `avatar-factory/1/part-imports/20260920-female-hair-10.json`.
- 고정 요청 키 `female-hair-folder-20260920-v1`, 배치 ID `aa08599e1c96639a7cb6a1dc`. 기준 몸 `7602726d8f4cb5f5792eaf11` / `beeb29328e3ece5472a70b27`. Meshy 7.1/2K geometry/4K texture/PBR/remesh false. 실제 접수·산출물은 다음 기록에서 갱신한다.
- 기존 4-worker 배치/동일 하위 작업 키/재개를 유지했다. 여러 이미지 업로드의 중복 React 키와 진행률 NaN 표시를 수정했다. 기존 컬러피커는 헤어 텍스처 명암을 유지하며 색을 바꾸고 조합에 저장/복원한다.
- 프론트 npm run build, backend compileall/uv build 통과. pytest/Playwright 미실행. 실행 UI5273/API8103, 로그 `data/local-runtime/937ead75c0494261bfa8845426f2e0d9`, FactoryReady True. 기존 서버/자료 보존.
- 실제 HTTP202 접수 완료. 첫 4개 Meshy task: `01a0bbe0-9291-71fd-87e8-f885b5158ffb`, `01a0bbe0-9291-73ce-8334-963646c1a37c`, `01a0bbe0-9339-75d3-be4f-462a595a9cb1`, `01a0bbe0-92c0-7390-a697-75c65f0822fd`. 나머지 6개 대기, 저장 완료 0/10. 새 유료 요청은 이 배치의 최대 10회 범위로 제한한다. 컬러피커의 WebGPU 텍스처 alpha 보존도 보완했다.
- 08:08 KST: 실제 3D 성공 8/10, 조립 및 S3 저장 5/10, 아홉 번째 생성 중. 최대 4개 작업이 생성/조립을 함께 처리하고 Blender는 기존 단일 실행 제한을 유지한다. 실패 0. 사용자 백엔드 실행 지시에 따라 ./start-local.ps1 재적용: 기존 API8103/PID37052 재사용, UI5273 프록시/FactoryReady True 확인. 실제 서버 로그는 위 937ead 디렉터리, 재실행 영수증은 `data/local-runtime/d498336abc8f4e99a11ab9be9d9307ea`. 전체 DB health는 기존 PostgreSQL DNS 연결 문제로 degraded이나 생성 작업은 정상 진행 중이다.
- 응답 유실/서버 중단 후 accepted 배치도 서버 can_resume에 따라 이어가기 가능하도록 UI를 보완하고 배치 오류를 표시했다. 최종 프론트 빌드 통과. 실제 브라우저 조작·품질 검사·pytest·Playwright는 실행하지 않았다.

2026-09-20 여성 헤어 시트 18종 일괄 생성 진행:

- 사용자 최신 지시로 `backend/assets/avatars/image-design/hair.png`를 직접 분할하고 실제 Meshy 생성을 실행한다. 범위는 헤어 18종, 각 front/side/back 3뷰, 이미지 생성 0회·3D 최대 18회·새 리깅/동작 0회다. 기존 여성 몸 `7602726d8f4cb5f5792eaf11` / `beeb29328e3ece5472a70b27`(24 bones, body SHA `5a2b62d5e79e0614d8aa05eb34fdc265538999a092f5246011b588042dedc92b`)을 사용한다. 삭제되지 않은 정확한 저장 버전을 확인했다.
- 원본 S3 asset `7778d4e66c9d4e578c9daf0b51863b9b880d2db8ca295559fcbac9a627e4a4d1`; 분할 sheet `af0dea41455980f7791c7134`, 18종/54개 PNG S3 저장 완료. 원본 픽셀 배율을 유지하고 피부/잔여 배경을 제거했다. 행·뷰별 절단 좌표와 투명 경계 분할을 고정하고 실제 분할 미리보기를 확인했다. 원본에서 겹친 뷰의 숨겨진 부분을 재생성하지 않았다.
- 프론트: 헤어 컬러피커·원본 색 복귀·조합 색 저장/복원, 시트 분할·54뷰 미리보기·선택·이름·최대4 동시 실행·S3 배치 조회/재개·localStorage 초안/동일 요청 복구. 배치 수락 시 몸 버전·프롬프트·Meshy 옵션을 고정하고 하위 작업 키/영수증으로 이어간다. `hair-sheet-crop-v3-row-view-seams`.
- 검증: frontend npm run build 통과, backend compileall 통과. backend 패키지 빌드 진행 중. pytest/Playwright는 실행하지 않는다. 실제 생성 배치 접수/진행/산출물은 후속 기록으로 갱신한다.

2026-09-20 Meshy 7.1 의상·파츠 생성 옵션:

- 상의·하의·헤어·모자/장식·신발·무기·도구·안경 단일 파츠 화면과 사진 전체 생성에 `Meshy 7.1 설정`을 연결했다. 단일 파츠는 종류별 브라우저 초안을 저장한다. 새 요청 기본값은 meshy-7.1, Ultra 2K geometry, 4K texture, PBR true, remesh false다. 전체 입력·범위·미지원 경계는 `docs/meshy-part-options.md`에 기록했다.
- 옵션: geometry, pose, remesh/topology/100~300000 target_polycount 또는 decimation 1~4, pre-remesh GLB, texture on/off/resolution/PBR/remove_lighting, source/관리 prompt/단일·다중 texture refs, image enhancement/moderation, auto_size/origin, 6개 출력 형식(GLB 필수), alpha/cardinal thumbnails. 다중 이미지 API의 현재 활성 옵션을 사용하며 4K geometry·deprecated aliases·무효 symmetry는 노출하지 않는다. image_urls는 기존 3뷰 파이프라인이 구성하며 대체 Meshy input_task_id 지정은 포함하지 않는다.
- 프롬프트 편집은 프롬프트 관리의 3D 텍스처 그룹으로 통합(기본몸+8파츠, 최대 800자). 참조 이미지는 owner S3 에셋/SHA를 접수 기록에 고정한다. 옵션 조합·범위를 서버에서 검증하고 비활성 필드는 provider payload에서 생략한다. 접수 옵션과 프롬프트는 재개 때 변경하지 않으며 기존 옵션 없는 요청의 fingerprint 호환을 유지한다.
- 설정을 접수한 파츠는 Blender 후처리의 기존 면 수 감축/텍스처 축소를 생략한다. 피팅/골격 연결은 유지한다. 추가 형식·미리보기는 개별 S3 영수증 및 결과 링크로 연결하고 기존 provider task GET으로 만료 URL을 갱신한다. 기본 GLB 및 저장된 추가 파일을 보존하며 새 유료 POST를 만들지 않는다.
- 검증: npm run build, backend compileall/uv build --package asset-3d-api, diff check 통과. UI 프록시 GET의 meshy-options 기본값/스키마와 프롬프트 9종·800자 확인. CUA 실제 파츠 화면에서 옵션 표시와 remesh 토글에 따른 폴리곤 입력 활성화 확인. 동작 선택의 기존 CSS class 충돌을 고쳐 펼친 패널의 정상 배치를 확인했다. 확인용 remesh 변경은 false로 복귀했다. pytest·Playwright·실제 유료 생성/업로드/추가 출력 다운로드·Blender 검사는 실행하지 않았다.
- 실행: ./start-local.ps1, UI5273/API8101, PID56440, revision `031a0e2ac8e896bb49cc602b7993e87aee778ef2430cd239b34641eb75338d3e`, 로그 `data/local-runtime/e7f93864bafb471a956b529bd0c494c3`. FactoryReady True, UI 프록시 health의 PID/revision 일치. 기존 PostgreSQL DNS degraded/큰 프론트 번들 경고는 유지한다. 기존 작업·서버 프로세스는 종료하지 않았다. 신규 생성 작업 ID 없음.

2026-09-20 GLB 기본몸 등록 — 바로 등록 / 새 리깅 분리:

- 사용자 최신 지시: API 옵션 편집보다 GLB 등록 우선. 기준 몸 리깅 전송을 필수로 두지 않고 `바로 등록` / `새로 리깅 후 등록` 두 경로를 제공한다.
- `POST /api/avatar-factory/base-bodies/glb-assets`와 owner-scoped S3 원본, 조회 API 및 `POST /base-bodies/glb` 연결. 입력: 이름, 남성형/여성형, GLB 원본 ID, import_mode(register/rig), generate_motions, prepare_expression_uv. 최대 256MiB의 메시·텍스처 내장 GLB. 브라우저별 남녀 입력과 동일 요청 키를 보존한다.
- 바로 등록은 리깅 유무에 관계없이 파일 바이트·메시·텍스처·UV·기존 골격/동작을 보존한다. Blender/제공자 처리 없이 저장 GLB 버전을 게시하고 기본몸 및 에셋 카드에서 읽는다. 골격을 요구하는 의상 뷰어와 분리된 원본 미리보기·내장 동작 재생을 연결했다. 새 리깅 유료 단계는 이 경로에서 비활성이다.
- 새 리깅은 이미지/3D 생성 0회, 업로드 GLB를 Meshy model_url 입력으로 전달한다. 리깅 1회와 선택 시 저장된 기본 동작 5종을 접수 영수증에 고정한다. 기존 리깅 여부에 관계없이 새 리깅 경로를 선택할 수 있다. 유료 POST 전 의도·작업 ID를 보존하며 응답 유실 시 새 제출을 만들지 않는다. 원본 파일은 유지한다. 표정 UV 준비는 선택 입력이다.
- 원본 그대로 등록한 몸을 이후 파츠 제작 기준으로 쓸 경우 리깅된 파일은 명시적 로컬 피팅·조립으로 좌표/렌더를 준비한다. 리깅 없는 파일은 먼저 새 리깅 후 등록이 필요하다. 원본 등록을 리깅/피팅 성공으로 표시하지 않는다.
- 검증: frontend npm run build, backend compileall/uv build --package asset-3d-api, diff check 통과. 실행 OpenAPI에서 두 import_mode와 옵션 확인. CUA 실제 화면에서 두 선택지와 기본 동작 옵션 표시 확인. 새 GLB 업로드/Blender/유료 리깅 실실행 및 pytest/Playwright는 수행하지 않았다. API 생성 전체 옵션 편집은 아직 구현하지 않았으며 GLB 우선 지시에 따라 후속 범위로 남겨둔다.
- 직전 남녀 고품질 생성은 저장된 조립 완료 상태다(남 `083be885018b3730071e2c7b` / `9c2cf9a020944c291c65c469`, 여 `53c5690a45130ddb6bb9da12` / `d1b2039f79ca870d681ccdb9`). 최신 카탈로그 GET에서 두 버전은 삭제 표시(2026-09-19 20:22 UTC)이며 그대로 보존했다. 이전 생성 목표는 현재 paused이고 여성 최종 화면 검수는 미완료다.
- 실행: `./start-local.ps1`, UI5273/API8099, PID26760, revision `7b026f851659d88b7d866ea3c4915f9fd03d7f18c62ef387a8b664cf80703299`, 로그 `data/local-runtime/2b1b8b11b224479ea05f8123ac83df2c`. FactoryReady True, UI 프록시 PID/revision 일치 확인. 기존 PostgreSQL DNS degraded. 새 리깅 모드의 작업 ID 복구/추가 동작 패널을 유지하고 마지막 프론트 빌드도 통과했다. CUA에서 입력 화면 배치 확인 후 바로 등록 기본 선택으로 남겼다.

2026-09-20 고품질 동작 파일 다운로드 복구:

- 남성 조립 `9c2cf9a020944c291c65c469` S3 저장 완료(review_required, error null), body SHA `e572fb13243e67b03f780ee349d893d89647b4a33723c0805894ed34169fbb82`. 동작 5종 모두 SUCCEEDED·다운로드·통합 완료, Meshy 버전 `0dcccf5bbeb4c36db255d3a7`. 브라우저 run 동작 재생 프레임 확인. 조립 정면에서 눈꺼풀/코/입 입체 형상이 남아 있음을 확인했으며 무안면 형상 해결로 주장하지 않는다.
- 여성 `53c5690a45130ddb6bb9da12`를 예약한 키 `20260920-high-v1-female-a1`로 접수(202). 위 남성 조립을 골격·동작 원본으로 고정, 추가 리깅·동작 유료 제출 없이 공유한다. 생성·연결·조립은 진행 중이다.
- 여성 Meshy 생성 `01a0bb51-1e26-775f-b224-42b76567b382` 성공, 240,432 triangles. 골격 공유 작업 `dce351900188d3a24456ea9a` 실행 중. 남성 최종 body는 179,771 triangles, 65,362,096 bytes, 4K 원본/8192×4096 표정 atlas 및 idle/walk/run/jump/fall 클립을 저장했다.
- 남성 `083be885018b3730071e2c7b`는 생성 성공(211,006 triangles), 새 리깅 `01a0bb47-3d3c-7400-82e2-23900df52e01` 성공(24 bones, 179,771 triangles). 면 수 제한에 걸리지 않았다. 동작 idle249/walk30/run16/jump466/fall503 모두 기존 task ID가 저장되어 있다.
- 중단 원인은 animation GLB 다운로드가 일반 25MiB 제한을 사용한 것. 보존형 몸의 동작 다운로드에도 기존 preserve_detail 정책(256MiB, 구조 검증 유지)을 적용했다. 새 유료 요청 없이 저장된 task를 재개했다. 재개 키 `20260920-hq-animation-download-resume-a1`, stage receipt `390520bcfc4f73bd973c7a327760d4e267c8c44d014ef28454a674eb9bec6c56`.
- backend compileall/패키지 빌드/diff check 통과. ./start-local.ps1의 최초 capabilities 확인은 시간초과였으나 이후 UI 프록시와 API8096의 revision `29b7430ff8b781cefea5327368e83b10c2cb9f11eb4aa2d3e42f84c56a22cabd`, PID10544 확인. 로그 `data/local-runtime/ddc66a6ccaf74eb9b23e77bc77b54c29`. 이전 API8095 보존. 실제 동작 저장과 조립, 여성 생성은 아직 확인 중이다.

2026-09-20 고품질 남녀 기본몸 실제 생성 승인:

- 남성 작업 `083be885018b3730071e2c7b` 접수됨. 실제 Meshy 생성 task `01a0bb43-495a-7421-b0e3-a55eaced8a65`, IN_PROGRESS 확인. 수락 예산 3D1/리깅1/동작5, 실제 고정된 동작 idle249/walk30/run16/jump466/fall503. 여성은 남성 리깅 완성 후 같은 여성 요청 키로 접수한다. 임의로 이전 동작 ID로 되돌리지 않는다.
- 사용자 후속 선택: “새 리깅 1개와 기본 동작 5종 생성”. 남성을 새 리깅으로 먼저 완성한 후 그 남성 기본몸의 저장 리깅/5동작을 여성에 공유한다. 승인된 총 범위는 고품질 3D 2회 + 리깅 1회 + 동작 5종이다. 삭제된 리깅은 복원하지 않는다. 아래 최초 재사용 계획 대신 이 범위를 적용한다.
- 실행 중 발견한 현재 제한: 서버에서 리깅 기준 `fae150416820bedfae7d668a`와 최신 남녀 원본 작업 모두 삭제 상태다. rig-transfer/sources는 빈 목록이다. male 생성 요청은 API 422 invalid_rig_source로 접수 전 거절됐으며 provider POST/새 작업 ID 발급은 없었다. 기준 몸 하나만 복원해 재사용할지, 새 리깅 1개+기본 동작 5종을 만들지 사용자 선택을 기다린다. 삭제 상태를 임의 복원하거나 우회하지 않는다.
- 사용자가 고품질 설정과 함께 “남녀 기본몸 생성까지 실행”을 명시적으로 선택했다. 앞선 준비만 지시를 이번 두 건에 대해 변경했다. 원본은 남성 `367ffece72a697b5385d7c46`, 여성 `2131fd930923a4a785379f16`의 앞/옆/뒤 3장, 리깅은 각 입력에 저장된 `fae150416820bedfae7d668a`/`763ebf5eb6e6efcaaad4b8bb`를 재사용한다.
- 신규 high-v1 계약: Meshy 7.1, geometry_resolution=2k(Ultra), texture_resolution=4k, should_remesh=false, target_polycount 생략. 4K 바탕을 얼굴 UV 준비에서 2K로 축소하지 않도록 원본에 맞춰 8192×4096 atlas까지 보존한다. 기존 접수·재개의 설정은 변경하지 않는다.
- 고정 요청 키/예상 작업 ID: 남성 `20260920-high-v1-male-a1` → `083be885018b3730071e2c7b`, 여성 `20260920-high-v1-female-a1` → `53c5690a45130ddb6bb9da12`. 각 3D 생성 1회, 추가 이미지·유료 리깅·동작 생성 0회. 응답 유실 시 이 ID/키를 먼저 조회하고 새 요청 키를 만들지 않는다.
- compileall, backend 패키지 빌드, diff check 통과. UI5273/API8095, 로그 `data/local-runtime/12c89ce3316e4a9e8a953eba7ae3a7fe`. 아직 새 산출물 품질은 확인 전이다.


2026-09-20 earlier preparation only (record encoding repaired):

- User initially asked to prepare and run it themselves. No new generation was submitted in that turn. New requests had remesh disabled; body/face atlas regions were increased from 512 to 2048 pixels. Compileall, package build, frontend build and diff check passed.
- UI drafts were filled from male 367ffece72a697b5385d7c46/f98123eec2170995472cae2b and female 2131fd930923a4a785379f16/ee9d248aa4281b1f540c0ff6, with the then-saved rig fae150416820bedfae7d668a/763ebf5eb6e6efcaaad4b8bb. Later source deletion is recorded above.
- Runtime at that point: UI5273/API8094, PID10032, revision 28b702a77a195e8f970379ee4ae9178589396054e1ee49237cf5d0e3ca05f88e, logs data/local-runtime/67104374d2b54ee4886de9b120998be7. Existing processes/data preserved.

2026-09-20 remesh and texture audit:

- Older male 0499c7d601a267de72b06048/95514790da359109cda36194 and female ac2f84115011ef972cadd2fa/686a588559461d47878513f5 used Meshy7, remesh=true, target_polycount=8000. Generated/assembled triangles were 8356/8356 male and 8319/8319 female. No pre-remesh GLB was saved. No additional assembly decimation occurred.
- Their 2048x2048 source albedo had been reduced to a 1024x512 expression atlas with two 512x512 regions. New preparation preserves larger source textures; old artifacts were not overwritten.

2026-09-20 subtle-blush neutral overlay application:

- S3 PNGs: male 527b9145481bb0a0da5d97e5f759af6c0b2512cd500884f6a57668ecf114c0fb; female dd485d6ef3818f574929957220f85012d3035636cc9c1574f4800269af76e0ea. Both1254x1254 RGBA, alpha0-255, S3 read-back SHA verified.
- Saved and selected one neutral expression on each older body above: male61d0718ff1e4d47fd367a756, femalea59339367f0d8d334c4ab23d. Male browser showed eyes but existing protrusions beneath them; placement/geometry quality was not approved. Female visual inspection was interrupted by the user's quality request. No original GLB, rig or additional expression generation was performed.

2026-09-20 사용자 첨부 이미지 — 남·여 기본 눈·코·입 PNG 제작:

- 사용자 지시에 따라 첫 번째 파란 눈 이미지는 남성형, 두 번째 붉은 눈 이미지는 여성형으로 내장 image_gen 편집 2건을 실행했다. 눈/눈썹·코·입만 남긴 기본 표정 RGBA PNG 두 개를 만들었으며 모두 1254×1254, 실제 alpha 0–255다. 기존 몸에 적용하거나 추가 표정을 생성하지 않았다. 코드·3D·리깅·실행 서버 변경 없음.
- 소유자 에셋 API로 S3 저장 완료: 남성형 `2adb09ab2d35bbc868ac462836bcf83308322500223d59887d85415b295787e9`, 여성형 `589e85e760c67f6249ead40d163f3a1d36210e7b9415f468c4daa4a3547b8c4f`. GET의 S3 redirect를 따라 받은 파일 SHA가 각 ID와 같은 것을 확인했다. 다운로드 URL과 정확한 편집 프롬프트는 `docs/face-default-textures.md`, 동일 기록은 S3 `face-texture-sets/20260920-base-defaults-v1/provenance.md`에 저장/재조회 확인했다.

2026-09-20 사용자 요청 — 직전 정면·후면 2장 변경 원복 완료:

- 바로 아래에 기록된 front_back 변경만 되돌렸다. 기본몸 업로드는 정면·측면·후면 3장 필수, 새 사진/단일 파츠는 front_side_back으로 복귀했다. 새 후면 canonical 준비 계약/reference.back 프롬프트, 2장 API/spec/provider 지원, UI 수량/배치 변경도 원복했다. 기존 머리 교체 제거·표정 텍스처 overlay와 그 이전 dirty 변경은 보존했다.
- 검증: frontend npm run build, backend compileall/uv build --package asset-3d-api, git diff --check 통과. 첫 패키지 빌드의 Windows egg-info 파일 잠금은 재시도로 해소됐다. 실행 OpenAPI에서 front/side/back 필수, front_back 제거, overlay POST 유지 확인. 프롬프트 GET에서 reference.front/side만 확인. 기존 몸 `393f0786e9874a60572ad749`/`4753bcc84b623ef72f430e9e` SHA `228a295f6bc7daf647bd2a2b329df93298d61f51fe14407f2f3bb68958c02320` 동일. pytest/Playwright/Blender/실제 생성은 실행하지 않았다.
- 실행: ./start-local.ps1, UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8092`, PID50316, revision `a36391145d9c839d5bdae51f748d4f81793bf58c80ce02e67e3bfd57627b018a`, 로그 `data/local-runtime/b5436b642bd04c5e9111c01cd5df914d/`, ready/FactoryReady True. 기존 프로세스·작업 자료 보존. 기존 PostgreSQL degraded/큰 번들 경고 유지.

2026-09-20 사용자 확정 — 새 생성 입력을 정면·후면 2장으로 변경:

- 사용자의 “앞뒤로만”은 2D 전환이 아니라 3D 생성 입력을 정면·후면 2장으로 줄이는 뜻으로 확인했다. 기본몸 업로드는 front/back만 새로 전송하고, 사진 파츠/단일 파츠 새 요청은 `view_mode=front_back`을 사용한다. 업로드 칸·수량·다시 생성 링크·진행 단계 표시도 반영했다.
- API literal, production_spec, 이미지 생성, Meshy 제출에서 front/back 순서를 지원한다. 후면 생성의 필수 side 참조를 제거하고 실제 전달 이미지와 프롬프트 역할을 일치시켰다. 측면이 없으면 후면 폭으로 깊이를 계산하지 않고 공통 규격 범위를 유지한다. 기존 Meshy 모델·리깅·동작 설정은 변경하지 않았다.
- 사진 원본 준비도 새 front/back 계약과 별도 후면 영수증을 사용한다. 저장 몸의 `body-back.png`, 동일 T자 자세, 후면 카메라 `-Z_to_+Z`를 사용한다. `reference.back` 편집은 프롬프트 관리에 추가했다. 기존 front/side 및 front/side/back 요청, 초안의 측면 asset, 접수 키/입력과 기존 영수증은 변환하지 않는다.
- 검증: frontend `npm run build`, backend `compileall`/`uv build --package asset-3d-api`, `git diff --check` 통과. 실행 OpenAPI에서 기본몸 필수 입력 front/back 및 두 API의 front_back 허용 확인. UI 프록시 프롬프트 GET의 reference.back과 기본몸 페이지 HTTP 200 확인. 현재 몸 `393f0786e9874a60572ad749`/`4753bcc84b623ef72f430e9e`의 body SHA `228a295f6bc7daf647bd2a2b329df93298d61f51fe14407f2f3bb68958c02320` 동일. 실제 업로드/생성/재개·브라우저 렌더·pytest·Playwright·Blender는 실행하지 않았다.
- 실행: `./start-local.ps1`, UI `http://127.0.0.1:5273/?tab=character&mode=body`, API `http://127.0.0.1:8091`, PID40148, revision `2d38c048570776b4cf1820e371f3eff8c5cb682d4d0eae673fc8fae29dac6088`, 로그 `data/local-runtime/89169893a9fa4ccabcfa5c31cd18f2b4/`, ready/FactoryReady True. 기존 API8090/PID14392 보존. 기존 PostgreSQL degraded/큰 번들 경고 유지.
- 별도 코드 검토 메모: 과거 fit_profiles 필드 추가 전 image-jobs 요청은 API model_dump가 넣는 fit_profiles=None으로 기존 fingerprint와 달라질 가능성이 있다. 이번 front_back 변경에서 새로 도입한 경계는 아니며 실제 복구 검증은 하지 않았다. 후속 수정 시 None 포함/미포함으로 이미 저장된 양쪽 fingerprint를 모두 보존해야 한다.

2026-09-20 사용자 확정 — 현재 모델 유지, 머리 교체 제거, 눈·코·입 텍스처만 적용:

- 사용자가 현재 결과가 잘 나왔다고 확인하고 머리 붙이기를 제외한 표정 적용을 지시했다. 현재 완료 몸 `393f0786e9874a60572ad749`/`4753bcc84b623ef72f430e9e`는 이미 저장된 기본 머리를 포함한다. 그 GLB를 되돌리거나 재조립하지 않고 SHA `228a295f6bc7daf647bd2a2b329df93298d61f51fe14407f2f3bb68958c02320`를 그대로 유지했다. Meshy 모델·리깅 선택·원본·기존 산출물도 변경하지 않았다.
- `avatar_blank_head_blender.py`, 신규 blank-head spec 설정/조립 호출/worker hash, body 머리 보정 API 입력과 교체 버튼을 제거했다. 기존 저장 spec의 blank_head 값도 더 이상 조립에서 실행하지 않는다. 뷰어는 기존 body.glb 전체를 직접 로드하며 head-parts POST와 body-without-head/base-head 조합을 사용하지 않는다. 머리 분리 POST는 410으로 종료하고 과거 저장 머리 산출물의 읽기 경로는 보존했다.
- 표정 저장/생성 후 자동 머리 분리를 제거했다. 선택한 표정의 재질별 합성 PNG를 `savedExpression`으로 적용하고 해제 시 원본 텍스처로 복귀한다. 표정별 머리 GLB를 뷰어에 붙이지 않는다. 매번 저장 몸 바탕에서 합성하므로 이전 표정이 누적되지 않는다.
- `POST /api/studio/bodies/{job}/{version}/expressions/overlay`와 `완성 표정 PNG 적용` 입력을 추가했다. 소유자 S3 PNG·2048px 이하·실제 투명도/그림 유무를 확인하고 기존 body의 UV에 알파 합성한다. 제공자 호출 없이 body/model 파생 파일을 저장한다. 표정 생성 참조는 통합 1장, 기존 눈/입 2장, 눈/코/입 3장을 지원하고 코는 제공된 경우에만 원본을 유지한다. 기존 생성 영수증/파일명/요청 키는 재사용한다.
- 검증: frontend npm run build, backend compileall/uv build --package asset-3d-api, git diff --check 통과. 실행 OpenAPI에서 overlay POST/reference 최대3장/body refit 제거 확인. UI 프록시 GET에서 현재 body SHA 동일, 머리 교체 action 및 head split 필드 없음, 표정0개 확인. 실제 PNG 입력·합성·시각 검증, pytest/Playwright/Blender/유료 생성은 실행하지 않았다.
- 실행: `./start-local.ps1`, UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8090`, PID14392, revision `d5a0b5bee68b66f89508448dd51ead9114cce0f915c6a0e6c9cd277062a8625e`, 로그 `data/local-runtime/61541ef8938f4babb152a7e59a797e20/`, ready/FactoryReady True. 기존 API8089/PID31096 보존. 기존 PostgreSQL degraded/번들 경고 유지.

2026-09-20 반복되는 눈구멍 — 무안면 머리 메시 교체 경로 추가:

- 사용자 재지적: 텍스처 프롬프트를 적용해도 Meshy가 눈구멍을 생성한다. 텍스처 지시로 메시 형상을 막을 수 없는 경계를 유지하고, `avatar_blank_head_blender.py`에 목 위 생성 머리를 제거한 뒤 측정한 폭·깊이·정수리 높이의 닫힌 타원형 기본 머리로 교체하는 로컬 조립 처리를 추가했다. 원본 머리 윤곽을 그대로 복원하는 방식은 아니며 전체 머리가 매끈한 기본형으로 바뀐다.
- 새 머리는 기존 Head 관절에 연결하며 골격·동작을 재사용한다. 남은 목의 Head 가중치는 parent 관절로 옮겨 표정 투영 범위에서 제외한다. 피부색은 윗머리 텍스처에서 추출하고 전용 피부 atlas/표정 UV를 만든다. 제공자가 만든 얼굴 normal/displacement/occlusion 재질은 새 머리에 사용하지 않는다. 이후 bind_body_head/decimation이 이 계약을 바꾸지 않도록 분기했다.
- 새 wardrobe_base의 생성 계약 및 신규 로컬 조립에 `closed-blank-head-v1`을 봉인한다. 이미 접수된 조립 버전은 기존 입력으로 재개한다. 완료 기본몸은 `native-parts/refit`의 `slot=body`로 기존 body.glb와 다른 피팅 파츠를 보존한 파생 버전을 만들 수 있다. 표정은 저장 PNG에서 새 머리에 다시 합성하고 기존 머리 GLB/atlas를 복사 적용하지 않는다. UI 단순/고급 화면에 `눈·코·입 없는 머리로 교체 · 로컬 처리`와 같은 작업 재개를 연결했다. 응답 유실은 기존 요청 키/서버 접수 키로 정리하고 다른 파츠 요청과 섞지 않는다.
- 읽기 전용 현황: 최신 `6ee760597da89355b8781487`와 `ce0b923de4ec4103a92b453b`는 Meshy 모델 SUCCEEDED지만 삭제된 리깅 기준 몸 참조로 pipeline_paused이며 조립 버전이 없다. 기존 자료·선택·삭제 상태는 변경하지 않았다. 완료 기본몸 `8feaf37d53b73c4cb112a3e0`/`ad415a58e7988d380b3ab954`의 실행 GET에서 blank_head_available=true, repair_pending=false 확인. 생성 원본 GLB는 보정 전 원본이며 이 변경은 조립 결과에 적용된다.
- 검증: frontend npm run build, backend compileall/uv build --package asset-3d-api, git diff --check 통과. 실행 OpenAPI의 refit body 입력과 UI 프록시 기능 상태 GET 확인. AGENTS.md에 따라 pytest/Playwright/Blender 실제 처리/유료 생성 검사는 하지 않았다. 실제 머리 교체·목 연결부·표정 위치·동작·렌더의 시각 결과는 미검증이며 해결 완료로 판정하지 않는다.
- 실행: `./start-local.ps1`, UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8089`, PID31096, revision `52c7c17f2bb18bceac9c39509a50848199f87ed51248161827ad91080a6e0df8`, 로그 `data/local-runtime/3575517c92fc4732bb74ee0a6361330b/`, ready/FactoryReady True. 기존 API8088/PID16472 보존. 기존 PostgreSQL degraded/번들 크기 경고 유지.

2026-09-20 무안면 지시 및 눈·입 원본 기반 투명 표정 레이어 구현:

- 사용자 확정: 기본몸에 눈·코·입 세 가지가 모두 없는 것이 의도된 디자인이다. `parts.body`에 누락으로 추정·복원하지 말라는 문구를 추가했다. 프롬프트 관리에 `meshy_texture.body`를 추가하고 새 업로드 기본몸/사진 기본몸 접수에 고정해 Meshy의 실제 `texture_prompt`에 전달한다. 기존 접수·응답 복구는 원래 설정을 유지한다. Meshy 공식 multi-image-to-3d 문서상 이 필드는 텍스처 전용이며 눈구멍 메시를 강제로 없애는 기능이 아니다: https://docs.meshy.ai/en/api/multi-image-to-3d
- 새 표정 흐름: 기본몸 결과의 표정 텍스처 생성 패널에서 눈·입을 함께 담은 PNG 1장 또는 눈/입 PNG 2장을 등록한다. 원본은 기존 owner-scoped S3 asset 저장을 사용하고 job별 원본 선택을 revision 비교로 보존한다. 생성 접수는 원본 ID·순서·프롬프트·몸 버전을 고정하고 참조 이미지 사본/해시를 저장한다. 무안면 몸 사진 대신 등록한 눈·입 그림만 표정 정체성의 원본으로 사용한다.
- 기본·웃음·울음·화남·놀람 5종 일괄 생성과 단건 생성을 연결했다. 일괄 작업은 표정별 고정 요청 키를 사용하고 완료 이미지를 보존하며 미확인 유료 요청을 새로 제출하지 않는다. 브라우저 요청 키 복구, 서버 재개, 원본 선택 교체와 생성 입력 분리, 업로드/생성 상태를 연결했다. 프롬프트 편집은 프롬프트 관리에만 둔다.
- 출력은 transparent RGBA PNG 요청이며 알파가 없는 응답도 파일로 보존하되 피부를 덮는 표정으로 적용하지 않는다. 기존 `bake_expression`의 원본 body 색상+투명 표정 합성을 재사용하고, UV 공유 경계에서 같은 반투명 픽셀이 두 번 합성되는 문제와 투명 픽셀의 RGB가 가장자리를 어둡게 만드는 보간을 수정했다. 매번 원본 body.glb에서 합성해 이전 표정을 누적하지 않으며, 원본 바탕 PNG/표정 PNG/합성 PNG와 파생 GLB를 저장한다. 머리·리깅 형상은 이 합성으로 바뀌지 않는다.
- 새 UI/API 단건 요청은 눈·입 원본을 필수로 확인하되 기존 영수증 복구와 내부 사진 기반 파이프라인의 입력 계약은 보존한다. 원본 PNG 업로드는 S3 미설정 시 저장 전 차단한다. 단건·배치 영수증 전이는 같은 호스트의 API/CLI 사이에서 OS 잠금으로 직렬화하고, 실행 중인 자식 표정은 배치에서도 진행 중으로 표시한다. 이 잠금은 기존 단일 제어 서버 계약이며 여러 호스트의 분산 큐를 추가한 것은 아니다.
- 검증: frontend npm run build, backend compileall 및 uv build --package asset-3d-api, git diff --check 통과. 새 실행 OpenAPI에서 원본 저장·일괄 생성·재개와 단건 reference_assets 확인. UI 프록시 GET에서 `parts.body` 597자/`meshy_texture.body` 344자, 최신 기본몸 `5f634f5fda26d37ac113dc00`/`54b341ebf0f03876bf93b32e`의 reference revision0/assets[]/batches[]/생성0개/ready true 확인. 원본은 아직 제공받지 않았으며 실제 업로드·유료 생성·합성·렌더·pytest/Playwright 검사는 하지 않았다.
- 실행: `./start-local.ps1`, UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8088`, PID16472, revision `1fd467f102c46495cd3f51650a3378b7efaa1e6a8f2cd34338ec9a265dec83be`, 로그 `data/local-runtime/480cbc92505e4a1ab3e9e487f16e1538/`, ready/FactoryReady True. 최종 보완 후 backend compileall/패키지 빌드/diff 확인 및 새 API OpenAPI/표정 목록 프록시 GET 통과. 기존 API8087/PID5304 보존. 기존 PostgreSQL degraded/번들 크기 경고 유지.

2026-09-20 기본 리깅 동작 설정 초기화 수정:

- 원인: 공통 motion-defaults는 남아 있었지만 작업별 GET은 해당 작업 파일만 읽어 새 기본몸에서 빈 설정을 반환했다. 사진 생성은 코드의 DEFAULT_ACTIONS를, 업로드 기본몸은 빈 motion_actions/동작 예산0을 사용해 저장한 선택을 반영하지 않았다. UI는 카탈로그와 기본값 조회를 묶었고 전체 선택 스냅샷을 저장했다.
- 기본값 GET/PUT를 소유자 공통 설정으로 통합했다. 작업 경로는 기존 소유권 검사를 유지한다. 기존 공통/작업별 기록은 저장 시각 순으로 복구해 읽고 원본 기록을 보존한다. 이후 저장은 선택한 슬롯만 현재 설정에 병합한다. 카탈로그 실패가 설정 조회를 지우지 않으며, 조회 취소·작업 전환·늦은 응답 처리를 추가했다. 공통 설정 저장 성공 여부를 리깅 상태 조회 실패와 분리했다.
- 새 기본몸/사진 생성은 공통 설정의 idle/walk/run/jump/fall 5개를 접수 기록·pipeline에 고정하고 동작 작업 예산에 반영한다. 기본몸 접수 중 복구는 저장된 motion_actions를 사용하며, 기존 구 접수의 빈 목록·예산은 보존한다. 저장된 골격 재사용은 기존 동작을 사용한다. 기존 유료 작업 계약·GLB·동작을 재생성하거나 바꾸지 않았다.
- 실제 읽기 전용 확인: 공통 및 `5f634f5fda26d37ac113dc00`, `e55bceed44a62396f626355f`, `6bf3bf63f526778c18efea21`의 기본값 GET 모두 idle252/walk30/run16/jump468/fall503/sit363 반환. 원본 최신 설정 시각은 2026-09-19T15:45:23.596085+00:00. 앉기 선택도 유지하며 자동 기본 생성은 5종이다.
- frontend npm run build, backend compileall/uv build --package asset-3d-api, git diff --check 통과. pytest/Playwright/실제 생성/설정 PUT 검사는 실행하지 않았다. 실제 신규 생성 및 재접속 UI 동작 검증은 미실행이다.
- `./start-local.ps1` 반영: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8086`, PID40396, revision `17f4cc37af1c9adb697afb57713a316eeb94f8ab757b831f68b1093779efb826`, 로그 `data/local-runtime/e134744584bb4fe9a29c58cde991f831/`, ready/FactoryReady True. 기존 API8085/PID19264 보존. 기존 PostgreSQL degraded 및 큰 번들 경고 유지.

2026-09-20 무안면 업로드 기본몸의 눈구멍 원인 확인:

- 사용자가 문제 단계를 업로드한 무안면 그림으로 생성한 3D 기본몸으로 특정했다. 최신 여성 기본몸 `5f634f5fda26d37ac113dc00`, 조립 `54b341ebf0f03876bf93b32e`의 저장된 정면·측면 원본과 정면 렌더를 읽기 전용으로 확인했다. 원본에는 눈이 없지만 조립 렌더에는 눈 테두리와 패인 눈 부위가 보인다. 기존 원본·GLB는 변경하지 않았다.
- 준비된 기본몸 업로드는 이미지 생성 프롬프트를 거치지 않고 정면·측면·후면 PNG를 Meshy에 전달한다. 현재 multi-image 요청은 Meshy 7/텍스처/PBR/remesh/T-pose 설정이며 얼굴 표면을 고정하는 메시 제약은 없다. source_preserved 몸은 후속 조립에서 생성된 형상을 보존한다. 무안면 그림만으로 눈구멍 없는 메시를 보장한다는 이전 안내는 부정확했다.
- 해결에 필요한 경계: 기준 머리의 눈 주변 굴곡을 실제 메시에서 정리하거나 검수된 매끈한 머리 메시로 고정한 뒤 골격·UV·표정 텍스처를 연결해야 한다. 텍스처 교체와 현재 머리 분리 기능만으로는 기존 눈 굴곡이 없어지지 않는다. 이번 턴은 원인 확인이며 코드 수정·메시 보정·유료 재생성·pytest/Playwright/Blender 실행은 하지 않았다. UI5273/API8085 유지.

2026-09-19 에셋 카드 3D 미리보기·전체 삭제/복원·조합 편집 반영:

- 관리자 에셋 카드에 기존 R3F/WebGPU/gaesup-world 뷰어의 카드 모드를 연결했다. 캐릭터 조립 GLB와 각 파츠의 피팅 GLB를 우선 표시하고, 조립 전에는 저장된 생성 GLB를 표시한다. 2D 이미지 전환, 로딩/오류/재시도, 드래그 회전·확대, 화면 밖 뷰어 해제, 카드 비율에 맞춘 XYZ 프레이밍을 추가했다. WebGL 호환 모드는 별도 표시한다.
- 작업 목록에 현재 조립 영수증의 버전·GLB URL·SHA를 포함한다. 카드별 별도 native-parts 조회 없이 저장 파일과 생성 단계를 함께 보여준다. 산출물이 아직 없는 대기 파츠도 표시하고 파츠 분류에 기본몸을 추가했다. 카드의 조립 완료 표시는 저장 상태이며 시각 품질 승인과 구분한다.
- 캐릭터 전체/조합 버전/개별 파츠 휴지통 및 복원을 연결했다. 새 PATCH `/api/studio/catalog/{job_id}/visibility`는 owner 및 If-Match CAS를 확인해 캐릭터 또는 버전 삭제 메타데이터만 갱신한다. 캐릭터 복원 시 개별 파츠 삭제 상태·이름·보관 상태를 보존한다. 삭제된 몸은 새 생성/리깅 기준 선택에서 제외한다. 실제 삭제 요청이나 데이터 제거는 실행하지 않았다.
- 카드에서 조합·표정 편집을 명시적으로 열면 기존 파츠 선택/현재 조합 저장/저장 조합 복원/표정 머리 교체 UI로 이어진다. 단순 카드 조회는 머리 분리·생성 POST를 실행하지 않는다. 얼굴 관련 질문: 기존 AvatarExpressionHeads와 NativeAssembly는 머리 없는 몸+기준 머리+같은 토폴로지의 표정 머리를 지원한다. 기존 얼굴 그림은 머리 분리만으로 없어지지 않으므로 기준 머리의 얼굴 텍스처 정리가 별도로 필요하다. 이번 턴에 원본 재가공·머리 분리·표정 생성은 실행하지 않았다.
- 검증: frontend `npm run build`, backend `compileall` 및 `uv build --package asset-3d-api`, tracked 변경 `git diff --check` 통과. 새 실행 API OpenAPI에서 visibility(character/version) 확인, 관리자 주소 HTTP 200. GET `6bf3bf63f526778c18efea21`은 기존 조립 `20abcaa5d44e5c7a22028644`와 SHA가 있는 GLB 7개, 생성 GLB 6개를 반환했다. 이 기록은 기존 결과 조회이며 잘못된 피팅 모양의 해결 증거가 아니다. pytest/Playwright/브라우저 시각 검사/삭제·복원 mutation 검사/실제 생성은 실행하지 않았다.
- `./start-local.ps1`: UI `http://127.0.0.1:5273/?tab=admin`, API `http://127.0.0.1:8085`, PID19264, revision `893ff54906621491dd9234ca9ac3ab4c73cf8e0ee4ddcfae01ff0c4b1d6fdebe`, 로그 `data/local-runtime/3d4cb381eb584f8599421aaa66b99844/`, ready/FactoryReady True. 기존 API8084/PID23944 보존, PostgreSQL degraded 및 기존 큰 번들 경고 유지.

2026-09-19 기본몸 전용 생성 및 파츠 타입 탭 반영:

- 현재 요청은 준비된 남녀 기본몸 이미지 6장을 등록할 전용 화면과 파츠별 제작 탭 구현이다. 캐릭터 기본 진입은 기본몸이며, 상의·하의·헤어·모자/장식·신발·무기·도구·안경을 나눴다. 관리자 기본몸 추가도 같은 화면으로 연결한다. 주소: `http://127.0.0.1:5273/?tab=character&mode=body`.
- 남녀 각각 정면·측면·후면 PNG/JPEG 3장을 S3에 등록하고 초안을 따로 유지한다. 사용자가 기본 몸 3D 생성을 누르면 이미지 생성 없이 준비한 3뷰로 몸 Meshy 1건을 접수한다. 기존 리깅 기준 몸을 선택하면 저장된 골격을 연결하고, 선택하지 않으면 새 리깅 1건을 사용한다. 요청 키와 입력을 저장하여 응답 유실 시 같은 요청으로 복구한다.
- 기본몸 단독/일부 파츠 조립을 허용하고 업로드 몸의 형태를 보존한다. 새 파츠 생성은 기준 몸과 프롬프트 관리의 저장 내용을 사용한다. 이번 턴에는 업로드·이미지/Meshy/Blender 생성·기존 데이터 삭제를 실행하지 않았다. 실제 6장 입력 후 생성·조립 결과 검증은 아직 하지 않았다.
- 검증: frontend `npm run build`, backend `compileall` 및 `uv build --package asset-3d-api`, 변경 tracked 파일 `git diff --check` 통과. 실행 API OpenAPI에서 base-bodies 경로, male/female, 필수 front/side/back 확인. 화면 주소 HTTP 200. pytest/Playwright/브라우저 시각 검사/실제 생성 검사는 실행하지 않았다.
- `./start-local.ps1`: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8084`, PID23944, revision `b99f8fa6806c94fa6a9eb13bc6100ff0e5b298d4ac4831757112bff5ba1f694d`, 로그 `data/local-runtime/d7e3c15895c949db9422ad559087e55e/`, ready/FactoryReady True. 기존 API8083/PID48980 보존. 기존 PostgreSQL 연결 degraded 상태 유지.

2026-09-19 이전 공통 체형 파츠 피팅 작업 — 사용자 지시로 중단:

- 공통 몸 설정, 의상 프로필, 착용점 균일 정렬, 구간별 길이/여유, 영역별 스킨/몸 가림, 관리자 기준점 보정과 버전 복원 구현. 재접속은 저장 입력과 요청 키로 재개한다. 기존 작업 데이터는 유지한다.
- frontend npm build와 backend compileall/package build 통과. pytest/Playwright/유료 생성은 실행하지 않았다.
- `./start-local.ps1`: UI `http://127.0.0.1:5273/`, API8083/PID48980, revision `1726d76085f3230e7c23c41a6620f42154048a3ffd4082344ea255f395f2243c`, 로그 `data/local-runtime/d9d17180a7074cb584be3f45b876f9fd/`, FactoryReady True. 기존 API8082는 보존.
- 저장 원본 로컬 재피팅 대상 `6bf3bf63f526778c18efea21`. 상의 요청 키 `single-body-fit-top-6bf-20260919-v1`, source `553cba405a087d4db0853969`, target `20abcaa5d44e5c7a22028644` 저장 확인. 표정 5개 재사용. 화면에서 상의 방향과 소매 길이 문제가 남았고 이후 사용자가 직접 처리 중단을 지시했다. 하의 적용·추가 피팅·공통 몸 등록을 이어서 실행하지 않는다. 기존 자료 삭제도 실행하지 않았다.


2026-09-19 공통 체형 1종 파츠 피팅 계획:

- 사용자 요청에 따라 `docs/single-body-part-fitting-plan.md` 작성. 공통 몸·골격 1개, 의상 종류별 피팅 기준, 착용점 균일 정렬과 구간 보정을 채택하는 계획이다.
- 기존 몸 재사용·3뷰 생성·단일 파츠 교체·공용 스킨·표정 머리·S3/복구를 재사용한다. 상·하의 전체 XYZ 박스 맞춤, 모든 소매의 손목 정렬, 의상 길이와 맞지 않는 몸 가림이 주 변경 대상이다.
- 첫 구현은 대표 몸 프로필과 저장 상의 1개. 생성 원본의 착용점 확보, 기존 fit_matrix 계산 재사용, 소매/몸통 보정과 가림을 연결한 뒤 하의로 확장한다. 범용 체형 변환·케이지·천 시뮬레이션은 이번 범위에서 제외한다.
- 이번 요청은 계획서 작성만 완료했다. 제품 코드·실행 중 작업·서버·저장 산출물을 변경하지 않았고 생성/재조립/테스트는 실행하지 않았다. 아래 실행 주소와 작업 상태는 각각 기록 당시의 정보다.

2026-09-19 후속 정정: 현재 뒷머리는 3뷰 생성 결과가 아님:

- 사용자 지적대로 `6bf3bf63f526778c18efea21`/조립 `553cba405a087d4db0853969`의 뒷머리 외형은 해결된 것으로 볼 수 없다. 실제 pipeline.generated_views는 front/side 2개이며, hair Meshy task `01a0b8ca-7c6f-7342-89aa-b004dfaf2e24`의 저장된 sources도 2개다. 최신 작업 목록에도 새 3뷰 작업은 없다. 앞선 3층 보완은 원본 앞머리 복제였고 사용자 요구인 후면 이미지 기반 생성이 아니었다.
- `complete_unified_hair_shell` 및 복제·후면 투영 helper, rear_hair_strands 설정을 제거했다. legacy hairBack의 단색 scalp backing 생성도 제거했다. 피팅 revision은 `shared-size-v19-preserve-generated-rear-hair`; 새 조립은 생성된 파츠의 후면 메시를 유지하며 임의 뒷머리를 추가하지 않는다. 기존 저장 결과는 변경·재조립하지 않았다.
- 새 UI 요청의 front_side_back → 저장 spec의 front/side/back → 이미지3장 → 같은 Meshy multi-image-to-3d 1회 경로를 코드로 추적했다. generate_multiview_part에 expected_views를 전달해 전송 이미지 수·뷰 순서를 계약과 대조하고 각 source의 view/name/SHA를 영수증에 저장한다. 기존 2뷰 pending 요청·task는 같은 키와 기존 입력으로 복구하며 자동으로 3뷰로 바꾸지 않는다.
- 파츠별 `후면 이미지 없음` 상태와 `3뷰로 다시 생성` 진입을 추가했다. 링크는 해당 캐릭터/파츠를 단일 파츠 생성 화면에 미리 선택한다. 피팅 버튼은 `기존 모델 위치·크기 맞추기`로 구분했다. 실제 새 유료 생성은 실행하지 않았다.
- 준비된 헤어 생성 화면: `http://127.0.0.1:5273/?tab=character&mode=parts&base=6bf3bf63f526778c18efea21&part=hair`. 실행 범위는 이미지3장+Meshy1회이며 몸/다른 파츠/표정은 재사용한다. 현재 모델을 실제 3뷰 결과로 교체하는 작업은 아직 남았다.
- frontend npm run build, backend compileall/package build, 변경 파일 diff --check 통과. pytest/Playwright/실제 유료 생성·Blender 재조립 없음. `./start-local.ps1`: UI5273/API8082/PID30944, revision `42859d36e77883014460c35e9372b76fb7e40d57f8782ee4a7a82321beb94ddf`, 로그 `data/local-runtime/a2711eb7f85f479c922d4353d212aec9/`, ready/FactoryReady True. 기존 PostgreSQL degraded 유지.

2026-09-19 최종 반영: view_mode 오류·머리 교체·파츠 분류:

- `view_mode: Input should be 'single' or 'front_side'`는 새 UI와 이전 API 8079의 스키마 불일치였다. `./start-local.ps1`로 8081에 반영했고 실제 OpenAPI에서 single/front_side/front_side_back 허용을 확인했다. UI `http://127.0.0.1:5273/`, API PID 53180, revision `aaa193427c04a43c2be6ee12eff2641603586479fd8ea31a7b0c7adad6472529`, 로그 `data/local-runtime/15c91e89bcf941bda37ca69e6eea2c79/`. Phase ready/FactoryReady True. 기존 API는 종료하지 않았다.
- 대상 job `6bf3bf63f526778c18efea21`, character `char-fd8d1bdf8d35`. hair v18 source `0bef15c3a42ed48d5eecf558`, key `repair-part-pipeline-rear-strands-6bf-v18-20260919`, 최종 조립 `553cba405a087d4db0853969` S3 저장 및 표정5 재사용 완료. GET review_required/expression_pending=false/preview=null. hat/top/bottom/shoes는 source0bef와 SHA가 각각 같다.
- 단색 뒷머리 shell을 제거하고 원본 앞머리의 실제 메시·UV·재질을 뒤통수에 3층 배치했다. 실제 저장 head-back.png에서 중앙 후면에 머리카락이 채워진 것을 확인했다. 앞쪽 원본 메시를 유지했다. 옆·아래 끝의 작은 피부 틈은 남아 있어 외형 전체가 완벽하다는 판정은 하지 않는다.
- 머리 전체 교체: 원본 몸 32,528면을 몸26,856면+머리5,672면으로 보완집합 분리해 S3 저장했다. 기존 위치·UV·스킨·뼈24개·동작6개를 보존한다. body-without-head/base-head/표정 머리5종 실제 다운로드 SHA가 모두 영수증과 일치했다. 유료 새 머리 생성이 아니라 저장된 표정 몸 GLB에서 파생했다.
- 최종 표정 머리: neutral `180f4a1cffcadb4c9036d949`, angry `1cdeaf0437e38f139f92ec11`, surprise `74b138b28ec9565f0eabab9a`, smile `bc82bfcee40b948832a38890`, cry `c6575f0dec091ad3ec000e92`. 몸 파일 SHA `2214014fd6aa30bd273a07242a61902c7a1206a4d162dd5586d5cb5d9220f62f`, neutral head SHA `094d05c4cb8da0f643949cef1778d165f444ddfcbd91c6edb1e6620682cdd51c`.
- 실제 경로에서 발견한 머리 분리 metrics 키 오류를 수정했다. 표정0개인 몸도 기본 머리를 분리하도록 했으며, 여러 재질 primitive가 Group 아래 로드되는 GLTFLoader의 extras 상속도 처리했다. 취소된 viewer는 분리 응답 뒤 새 모델 로드를 시작하지 않는다.
- Chrome 수동 WebGPU 화면에서 neutral 눈·입 표시, smile 머리 교체와 입 모양 변경, 의상 유지 확인. 기존 neutral 선택으로 복원했다. 관리자 캐릭터별은 body 재사용 계보가 아닌 실제 character_id로 묶어 3캐릭터/각 버전을 표시하며, 파츠별 헤어 필터와 캐릭터 선택을 확인했다. 서로 다른 캐릭터가 같은 몸을 쓴다는 이유로 합쳐지지 않는다.
- 단일 파츠 화면의 8종 중 한 개 선택, 정면·측면·후면 이미지3장/3D1개 범위와 프롬프트 관리 링크를 확인했다. 생성 화면에는 프롬프트 편집이 없다. 신규 측면 원화/가이드/몸 렌더는 팔을 벌린 T자이며 관리 API의 실제 side 기본값도 확인했다. 이미 접수된 구 I자 요청의 영수증·복구 입력은 유지한다.
- 최종 frontend npm run build, backend compileall/uv build --package asset-3d-api 및 diff --check 통과. pytest/Playwright/유료 이미지·Meshy 생성 없음. 신규 3뷰 생성의 제공자 결과와 새 T자 이미지 외형은 실행하지 않아 미검증이다. 기존 PostgreSQL degraded/큰 번들 경고 유지. 원격 배포 없음.
- 대상 화면: `http://127.0.0.1:5273/?tab=character&mode=photo&photoCharacter=char-fd8d1bdf8d35&photoJob=6bf3bf63f526778c18efea21`. 아래 기록은 이전 단계의 경과다.

2026-09-19 파츠 파이프라인 후속 복구 진행:

- 새 요청의 후면 생성 계약 구현: 전체 사진/단일 파츠 모두 신규 UI 요청에 `view_mode=front_side_back`을 명시하고 정면·측면·후면 3장/파츠를 같은 Meshy 작업에 전달한다. 기존 front_side 및 view_mode 없는 pending single-part는 기존 입력/fingerprint/2뷰/요금 한도를 유지한다. frozen body-back 로컬 렌더/영수증, back의 정면+측면 참조 역할·SHA, front/side 재시도 의존성과 후면 라벨/3장 예산을 연결했다. backend py_compile 및 frontend npm run build 통과. 실제 신규 3뷰 이미지/Meshy 생성은 실행하지 않았다.
- 조립 파일이 저장돼도 표정 재사용이 끝날 때까지 이전 완성 미리보기를 유지하도록 수정했다. 최신 저장 조립 `0bef15c3a42ed48d5eecf558`는 표정5/5 완료, 선택 neutral `acba2f3059cdf811668138b2`. 새 코드의 start-local 반영은 아직 남았다.
- 후면 결함 확정: v17의 단색 rear shell은 사용자 요구에 맞지 않아 폐기 예정. 실제 원본 hair_0 중앙 후면 중·하부에 형상이 없으며 정수리 테두리만 있다. 원본/런타임 모두 2039 triangles로 decimation 손실이 아니고, 중앙 후면 205 정점 중 내부 정점6개/거리 중앙값 +29.1mm로 관통이 주원인도 아니다. 기존 실제 hair strand mesh/UV를 이용한 후면 보완 작업 중이며 완료로 간주하지 않는다.
- `97720d72fa838b9fa6dc2d55` hair 조립/S3/표정5 완료, hat/top/bottom/shoes GLB는 source13f와 SHA 동일. 모자 크기 수정 후 source977에서 key `repair-part-pipeline-hat-6bf-seat-20260919`, target `0bef15c3a42ed48d5eecf558` 조립/S3 완료, 표정 재적용 진행을 확인했다. 정면 모자는 실제 두상 폭에 맞게 수정됐다.
- 현재 UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8079`, 로그 `data/local-runtime/2d1504ac87814ff1ae71e760000e0d2e/`. frontend build/backend compile/package build 통과. 이후 backend 변경의 최종 빌드/start-local은 남았다.
- 대상 `6bf3bf63f526778c18efea21`. 사용자 hat 요청 `5a25252e-3433-41e5-902b-b90da0b6fcce` 복구 결과 `13f23b9c4c66550c18e88916` S3 저장/표정5 완료. 직전 같은 요청의 `4ac2e6547372e045308214e5` 완료도 GET에서 확인했다. 같은 키의 완료 요청이 코드 변경 때문에 다시 조립되던 부분을 수정했다.
- 실제 Head 피부(.55961m) 측정, 옷 안감 제외, 뒤통수 shell 생성과 rigid bind를 반영했다. 후속 hair refit: source `13f23b9c4c66550c18e88916`, key `repair-part-pipeline-hair-6bf-v17-20260919`, target `97720d72fa838b9fa6dc2d55` 진행 중. 저장된 정면에서 옛 hat/hair bbox 비율 재적용으로 모자가 작아진 문제도 확인·수정했으며 hair 완료 후 hat만 재피팅할 예정이다.
- pytest/Playwright/유료 이미지·Meshy 생성 없음. 로컬 Blender 재조립만 수행 중. 최종 외형 완료 판정 전이다.

2026-09-19 진행 중: 파츠별 독립 파이프라인·얼굴/헤어 위치·뒤통수 구멍:

- 대상 `6bf3bf63f526778c18efea21`, 원래 조립 `898cf98c3ffd45baec614f03`, neutral `da395296004090935d570d9a`. 이미지/Meshy 유료 요청 없음. 파츠 8종 중 하나만 이미지2/3D1 생성하는 API/UI와 파츠별 로컬 refit API를 추가했다. 다른 파츠는 fitted native GLB/몸/골격/동작을 재사용하고 표정 원본을 동결해 재베이크한다. 부모 local_refit/native_part_reuse/expression_reuse 포인터는 새 작업에 그대로 상속하지 않는다.
- 사진/표정 화면 프롬프트 편집 및 프롬프트 문장을 제거하고 관리 링크만 남겼다. 파츠별 이미지/3D/피팅·조립 상태 및 단일 refit 버튼을 연결했다. 기존 완료 미리보기를 refit 진행/실패 중에도 유지하도록 보완했다.
- WebGPU classic material의 custom TSL 색상 노드가 다른 재질의 빈 atlas와 프로그램 캐시 키를 공유하던 오류를 수정했다. Chrome 수동 화면에서 눈·입 표시 확인. 얼굴 bounds에서 Head 가중치를 가진 옷 안감을 제외했다. 헤어 유무로 scalp90% 전체를 숨기는 처리와 누적 coverage metadata를 제거했다.
- 로컬 hair refit 키 `repair-part-pipeline-hair-6bf-20260919-v16`: 첫 `1f124c7e0d85e8e42046c677`은 Blender bone 표시용 메시 오인으로 실패, body_meshes 필터로 수정. 같은 키의 `2912cedcd01f502c9975d3c1`은 완료/S3 저장 및 표정5 재베이크 완료. neutral `5e9f5cd6f78214e9ab14aa29`. hat/top/bottom/shoes GLB SHA는 898cf와 각각 동일하다.
- 2912 실제 후면 PNG에서 헤어 뒤 내피 부재/피부 노출을 확인했다. head_region에 T-pose 팔까지 섞여 target width .875m(실제 Head skin .55961m)인 문제와 unified hair rear backing 수정 중. 아직 외형 완료 아님.
- 사용자가 이후 hat refit 실행: source `2912cedcd01f502c9975d3c1`, key `5a25252e-3433-41e5-902b-b90da0b6fcce`, target `2e51ee153cd50346414b53f4` 실패. Blender 추론 bone tail 등의 strict 비교를 이름/부모 + world-rest matrix tolerance 1e-4로 수정했다. 실제 GLB 최대 차이는 4.51277e-06. 이 hat 요청 복구 후 hair 외형 수정 재조립을 이어야 한다.
- 표정 재사용 잠금/process/부분 성공 복구/선택 CAS 보호 및 expression stage 로컬 재개 추가. reuse 계약이 있으면 기존 paid default-expression 계약은 실행하지 않는다. 현재 UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8078`, 로그 `data/local-runtime/ed14b345bf424638b621d699b62fd04e/`. 이후 코드 변경의 최종 빌드/start-local 및 저장 결과 확인이 남았다. pytest/Playwright/유료 생성 검사는 실행하지 않았다.

2026-09-19 얼굴 텍스처 코드 점검·저장 선택 재적용:

- 사용자 요청은 얼굴 텍스처 미적용 코드 점검이다. 최신 저장 작업 `6bf3bf63f526778c18efea21`, 몸 버전 `898cf98c3ffd45baec614f03`, 선택 surprise `2e50418ae2366394022ca1e1`을 GET으로 확인했다. 기본 표정 5개가 저장되어 있고 선택된 material 0/3/6/7 PNG 4개의 실제 다운로드 SHA가 영수증과 일치하며 크기는 1024×512다. material-0.png를 메모리에서 열어 오른쪽 얼굴 영역의 눈·입을 확인했고 몸 GLB의 baseColorTexture는 TEXCOORD_1을 참조한다. 기존 작업 `814cf650bf9d9accfe7de8d2`도 5개 표정 및 surprise 선택이 유지된다. 어느 작업/화면에서 발생한 사용자 증상인지는 아직 답변을 받지 않았다.
- 확정한 코드 결함: Expressions의 initialized 플래그가 최초 적용 뒤 서버 선택 변경·동일 표정 산출물 갱신을 무시했다. 현재 viewer 인스턴스와 표정 ID/텍스처 SHA를 비교하도록 변경했고, 적용 중 polling으로 바뀐 선택은 적용 완료 후 다시 동기화한다. 실패한 요청은 다음 제한된 polling/명시적 다시 불러오기에서 재시도해 즉시 반복을 막는다.
- NativeAssembly는 로딩 완료된 viewer 객체를 React 상태로 전달한다. TextureExpressions/ModelViewer는 취소·폐기된 적용을 false로 반환해 화면에서 적용 성공으로 기록하지 않는다. 공유 재질을 중복 복제하지 않으며 WebGPU 색상 노드가 텍스처 UV 채널과 변환 행렬을 함께 사용하도록 보완했다. 저장된 S3 원본·선택·생성 기록은 변경하지 않았다.
- 검증: 최종 `npm run build`(tsc + Vite), 변경 파일 `git diff --check` 통과. backend 코드는 수정하지 않았다. pytest/Playwright/실제 이미지·Meshy·Blender 생성, 브라우저 시각 검수 및 상태 전이 재현 시험은 실행하지 않았다. 발견한 재적용 결함의 수정이며 초기 표시 실패의 단독 원인이나 실제 화면 해결까지 확정한 결과는 아니다. 기존 큰 번들 경고 유지.
- `./start-local.ps1` 완료: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8076`, 기존 API PID `15928` 재사용, revision `c102f8b45a3db4d67df32ab8f4cf64599f85ab8b18d4eca17b21e1f22a8ab574`, 로그 `data/local-runtime/55fb6f738eca475b8c37d8d18781da62/`. FactoryReady True, 기존 PostgreSQL degraded 유지. 대상 화면 `http://127.0.0.1:5273/?tab=character&mode=photo&photoJob=6bf3bf63f526778c18efea21`. 원격 배포 없음.

2026-09-19 프롬프트 관리 화면·한글 기본 프롬프트:

- 별도 `프롬프트 관리` 탭: `http://127.0.0.1:5273/?tab=prompts`. 공통 규격 정면/측면 2개, 몸·파츠 9개, 표정 6개, 기물 3개, 바닥 타일 9개, 이모티콘 원화 1개, 총 30개를 상세 한글 문장으로 관리한다. 기본 몸 무표정 바탕, 머리 장식 종류, 헤어 길이, 분리된 신발, 원본 눈 정체성과 반복 타일 조건을 포함한다.
- `studio_prompts.py`가 기본값과 사용자 설정을 소유하고 인증된 GET/PUT `/api/studio/prompts`로 제공한다. 사용자별 `library/prompts.json`은 기존 공장 S3 경로에 저장하며 revision 충돌과 응답 유실 후 동일 저장 재요청을 처리한다. 편집·검색·기본값 복원·최신 저장값 복귀·미저장 표시와 로컬 편집 초안을 연결했다. 화면에서 변경 저장을 눌러야 기본값에 반영된다.
- 관리값은 파츠 capability, 표정 목록, 기물/타일/원화 목록의 기본값에 연결된다. 신규 사진/기존 몸 파츠 접수 시 원화·파츠·기본 표정 5종 문장을 고정하며 기존 작업과 idempotency 입력은 바꾸지 않는다. 공통 규격 참조 v4는 고정 T/I 가이드와 저장 프롬프트 해시를 사용한다. v1/v2/v3의 기존 요청/영수증 경로는 유지한다. 기존 몸의 파츠 교체 시 새 설명보다 상속된 design_prompt가 우선하던 부분을 수정했다.
- 기존 캐릭터 프롬프트 초안 v1 중 과거 영어 기본값과 정확히 같은 문장만 새 기본값으로 전환한다. 직접 편집한 문장은 v2 개별 덮어쓰기 초안으로 보존한다. 생성 화면의 개별 편집이 관리 기본값보다 우선하며 `저장된 기본값 불러오기`로 되돌릴 수 있다. 기존 요청 복구 입력은 그대로 유지한다. 기본 타일의 절차적 생성은 프롬프트를 사용하지 않으며 AI 재질 탭에는 눈/모래/잔디/흙/벽돌 분류를 추가했다.
- 검증: 최종 `npm run build`, backend `compileall`, `uv build --package asset-3d-api`, `git diff --check` 통과. 인증된 Vite 프록시 GET으로 한글 기본값 30/30, 글자 제한 준수, 저장 가능 설정 및 파츠 capability 기본값 일치를 확인했다. 프롬프트 화면 URL HTTP 200. 기존 작업 `814cf650bf9d9accfe7de8d2`는 `review_required`, character flow `complete` 유지. 실제 설정 PUT/재접속 충돌 시험, pytest/Playwright, 유료 이미지/Meshy/Blender 생성 및 브라우저 시각 검수는 실행하지 않았다.
- `./start-local.ps1` 반영: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8076`, PID `15928`, revision `c102f8b45a3db4d67df32ab8f4cf64599f85ab8b18d4eca17b21e1f22a8ab574`, 로그 `data/local-runtime/65dc41d453a345c39b26efafa128d575/`. Phase ready/FactoryReady True, 기존 API 8075 보존. 기존 PostgreSQL degraded와 큰 번들 경고 유지. 원격 배포 없음.

2026-09-19 얼굴 미표시 수정·몸 바탕 위 표정 합성:

- 대상 `814cf650bf9d9accfe7de8d2`, 몸 버전 `d8aff5311f60b231b30d4540`. Chrome 실제 WebGPU 미리보기에서 저장된 표정 선택은 있지만 얼굴이 비어 있는 상태를 확인했다. 기존 합성 PNG에는 눈·입이 있고 얼굴 UV 좌표도 일치했다. 실제 몸 재질에는 원래 피부 emissiveTexture/emissiveFactor=[1,1,1] 및 생략된 metallicFactor(기본 1)가 남아 있었다.
- 브라우저는 재질별 독립 텍스처 슬롯과 명시적인 얼굴 UV/색상 노드를 사용하고, 표정 전환 시 같은 GPU 텍스처의 Source만 갱신한다. 발광·금속 설정을 제거해 피부 재질로 보정했다. 새 조립 Blender 경로와 표정이 포함된 body.glb/model.glb 저장에도 같은 재질 보정을 반영했다. 표정 캐시는 최근 3세트이며 추가 얼굴 메시·draw call은 없다.
- 몸 바탕 PNG + 원본 투명 face.png + 합성 PNG를 `body-albedo-face-overlay-v1`로 함께 S3에 저장하고 선택한 표정에서 각각 미리보기/다운로드한다. 기존 표정 적용 전 렌더는 접힌 '표정 적용 전 조립 이미지'로 구분했다. 몸 바탕은 기존 생성 몸의 UV 텍스처를 재사용한다. 새 AI 몸 텍스처/표정 이미지 생성 요청은 하지 않았다.
- 기존 수신 이미지 5개로 로컬 합성/GLB 저장만 갱신했다. neutral `0734bff0be5d966fb08db896`, smile `a19999bd3a853014bda892d3`, cry `e20bd7ddc279895a30cee51f`, angry `4f1f9ff27006a66da65bb17e`, surprise `b6f033fa68b8b95e22ab941b`. cry POST 응답은 60초에 유실됐지만 GET으로 같은 ID의 저장 완료를 확인했으며 재제출하지 않았다. 최종 GET에서 5/5에 새 composition 및 바탕/레이어/합성/GLB 파일 기록을 확인했다.
- Chrome 수동 화면 확인: 수정 후 놀람의 눈·입이 얼굴에 표시됐고 기본 표정으로 교체했을 때 입/눈 모양 변경도 확인했다. 이후 기존 놀람 선택을 복원했다. surprise body/model GLB는 내려받은 SHA가 영수증과 일치하며 발광 0/metallic 0, skin 1개와 기존 animation 6개를 보존한다. 이동 화면의 이번 수정 후 시각 확인은 하지 않았다.
- 전체 작업 목록 GET이 40~80초로 누적되어 표정/의상 파일도 지연되는 현상을 확인했다. 목록 스캔을 인스턴스 내 잠금과 10초 캐시로 공유하고, UI 목록 조회 간격을 15초로 조절했다. 선택 작업은 개별 GET으로 먼저 복원하므로 전체 이력 수신을 기다리지 않는다. 개별 작업 GET 약 2.9초, 새 서버에서 body.glb 조회 약 3.1초 확인. 동작/개별 작업 조회와 제출은 목록 캐시를 사용하지 않는다.
- 최종 frontend npm run build, backend compileall/uv build --package asset-3d-api 통과. pytest/Playwright/실제 유료 생성/Blender 재조립 검사는 실행하지 않았다. 기존 큰 번들 경고와 PostgreSQL degraded 유지. 기존 작업 및 사용자 변경/삭제 파일 보존, 원격 배포 없음.
- `./start-local.ps1` 적용: UI http://127.0.0.1:5273/ , API http://127.0.0.1:8075, API PID 53260, revision `d9082fc7761f996424edc06f15ed1a36a73be00e69da9b7b1cf60136a4efcbba`, 로그 `data/local-runtime/411e8a74967942e0b0609785de92b824/`, Phase=ready/FactoryReady=True. 8074 첫 실행은 초기화 지연으로 하네스 제한 시간을 넘겼으며 같은 프로세스의 시작 확인 후 재실행해 연결했다. 최종 8075 이전 프로세스는 종료하지 않았다.

2026-09-19 머리 장식 명칭·사진 생성에서 저장 기본 몸 선택:

- UI·갤러리·미리보기·오류의 모자 표시를 머리 장식으로 통일했다. 기존 저장 슬롯 ID hat는 유지한다. 새 파츠 프롬프트 measured-views-v20-head-accessories는 헤어밴드/리본/장식/모자의 원래 종류와 빈 공간을 보존하며 밴드에 모자 챙·덮개를 만들지 않도록 한다. 과거 기본 모자 프롬프트와 정확히 같은 브라우저 초안만 새 기본값으로 전환하며 직접 편집한 초안과 기존 요청 영수증은 유지한다.
- 사진으로 전체 생성의 기본 몸 선택에서 새 몸 생성 또는 저장한 몸을 고른다. 저장 몸의 body-front만 미리보기하며 선택 ID는 photoBase URL, 제출 버전은 기존 이미지 요청 복구 입력에 고정한다. 몸 자체가 저장돼 있으면 표정 단계가 중단됐어도 선택 가능하다.
- 기존 /image-jobs 접수·idempotency 경로에서 base_job_id/base_version 선택을 기존 AvatarVariants 경로로 연결했다. 새 사진 소유권·원본 SHA·blueprint revision과 기본 몸 소유권·버전·SHA·삭제/보관 여부를 검사한다. 새 사진 작업은 body.glb·골격·클립만 복사하고 기존 의상/헤어/장식은 복사하지 않는다. 선택 몸의 실측 규격·정면 T자/오른쪽 측면 I자 렌더로 새 원본을 준비한 뒤 파츠 5종 정면/측면→3D→동일 몸 피팅→기본 표정 5종으로 진행한다. I자 렌더는 임시 pose이며 원본 bind pose는 변경하지 않는다.
- 생성 범위는 규격 2장+파츠 10장+표정 5장, 3D 5개, 몸/리깅/동작 유료 제출 0개다. 기존 동작은 선택 몸에 저장된 클립을 그대로 재사용한다. 새 몸 생성의 기존 요청 fingerprint와 기존 작업 데이터는 유지한다. 별도 파츠 교체 경로는 완료된 원본 정규화 파일도 함께 보존해 후속 조회 누락을 막고 표정 생성 수를 UI/작업 예산에 표시한다.
- 최종 npm run build, backend compileall/uv build --package asset-3d-api, git diff --check 통과. 중간 Workspace 타입 오류를 수정한 뒤 프론트를 재빌드했다. pytest/Playwright/실제 이미지·Meshy·Blender 생성 검사는 실행하지 않았다. 신규 유료 생성·기존 캐릭터 재조립 없음. 새 선택 몸의 I자 렌더 및 끝까지 생성·피팅된 외형은 미검증이다.
- `./start-local.ps1` 실행 반영: UI http://127.0.0.1:5273/ , API http://127.0.0.1:8073, API PID 51684, revision `99dcddd53b2ab2f2a9c2924f623049ff0d876bdd1525194e345c4535795ddb81`, 로그 `data/local-runtime/2ce76239bc1544a7b99be170044a7641/`, Phase=ready/FactoryReady=True. 기존 PostgreSQL degraded와 큰 번들 경고 유지. 기존 API 8072를 보존했다. GET으로 UI HTTP 200, 새 base_job_id/base_version schema와 머리 장식 기본 프롬프트, 기존 작업 `814cf650bf9d9accfe7de8d2`의 몸 버전 `d8aff5311f60b231b30d4540` 및 body.glb/body-front.png 보존을 확인했다. 원격 배포 없음.

2026-09-19 전체 캐릭터 얼굴 재질 연결 오류 수정:

- 대상 작업 `814cf650bf9d9accfe7de8d2`, 조립 `d8aff5311f60b231b30d4540`. 사용자 실행에서 기본 표정 neutral/smile/cry/angry/surprise 이미지 5개는 모두 complete이고 UV 저장은 0/5, expressions 단계 paused다. neutral/smile 수동 bake도 기존 API에서 HTTP 409였다.
- 실제 저장 GLB 조회로 원인 확인: body.glb 얼굴 베이크 대상 재질은 0/3/4, 전체 model.glb에는 0에 대응하는 재질 1만 남는다. 3/4는 의상·헤어 가림 때문에 전체 모델에서 의도적으로 제거한 면이다. 재질 이름과 원본 albedo SHA로 실제 남은 면을 연결하고, 가림으로 빠진 재질의 텍스처는 body.glb에 보존하도록 수정했다. 누락된 가시 재질·다른 원본 텍스처는 계속 오류로 처리하며 쓰기 전에 매핑을 확정한다. manifest에 model_omitted_body_materials를 기록한다.
- 확인: 실제 GLB를 메모리에서 읽은 연결 결과 0→1, 의도적 제외 3/4. 백엔드 compileall 및 uv build --package asset-3d-api, 변경 파일 diff --check 통과. 프론트는 직전 빌드 이후 변경하지 않았다. pytest/Playwright/유료 생성 검사는 미실행이다.
- `./start-local.ps1`로 UI http://127.0.0.1:5273/ , API http://127.0.0.1:8072에 적용했다. API PID 29344, revision `164d366d174f9884112c61ce86eef079aa08e44a9ba2c2c5e67df7bfaaa284b8`, 로그 `data/local-runtime/abf0f262160443489ff51119100a93ee/`, Phase=ready/FactoryReady=True, 기존 DB degraded 유지. 기존 API 8071은 보존했다. 이미지 5개 complete·busy=false·expressions action paid=false를 확인한 뒤 저장 단계만 복구 접수했다. 요청 키 `repair-expression-materials-814cf650-20260919-01`, 실행 ID `7a47d07c3247a1f9299a3f9a6190619ef4cbb63ea7752a3ce024cbb68f257438`.
- 실제 복구 완료 2026-09-19T07:36:40Z: 같은 생성 ID 5개를 재사용해 UV PNG/body.glb/model.glb를 S3에 저장했다. 기본 neutral `0734bff0be5d966fb08db896`, smile `a19999bd3a853014bda892d3`, cry `e20bd7ddc279895a30cee51f`, angry `4f1f9ff27006a66da65bb17e`, surprise `b6f033fa68b8b95e22ab941b`. GET에서 5/5 complete, error=null, default_selected=true, stage 실행 complete를 확인했다. neutral body/model GLB를 다시 내려받아 봉인 SHA와 내장 albedo가 저장 PNG SHA에 일치함을 확인했고, 두 GLB 모두 skin 1개·기존 animation 6개를 보존한다. 새 이미지/Meshy 유료 POST나 재조립은 실행하지 않았다. 브라우저 표정 외형 검수는 수행하지 않았다.
- 대상 화면: http://127.0.0.1:5273/?tab=character&mode=photo&photoCharacter=char-7ea1e65a1cb6&photoJob=814cf650bf9d9accfe7de8d2 . 원격 배포 없음.

2026-09-19 기본 동작·표정 파이프라인과 2D 원화 탭 반영:

- 사용자 최신 정정은 실제 생성 대행이 아니라 파이프라인 코드 수정이다. 이 작업에서 이미지/Meshy 유료 POST, 기존 캐릭터 재조립은 실행하지 않았다.
- 현재 저장 결과 GET: 작업 `10d7b694acea4cee13821bfe`, 조립 `6eb5a127ce0d0a9a633516fa`, expression-generations 0개. 저장된 head-front.png를 열어 얼굴 텍스처가 없는 상태를 확인했다. 눈 변형을 수정한 새 실제 생성 결과는 아직 없다.
- 새 photo 작업은 정면 T자/오른쪽 측면 I자 참조를 각각 원본에서 생성·배경 제거한 뒤 파츠 생성에 사용한다. 측면 I 가이드를 파츠의 기존 T 가이드와 분리했다. v1 단일 정면 작업의 저장 프롬프트·영수증은 유지한다. 새 입력 예산은 규격 2 + 파츠 12 + 표정 5 = 이미지 19장이다.
- 기본 동작 idle/walk/run/jump/fall을 신규 작업에 고정한다. 기존 빈 motion_actions 입력 때문에 walk/run만 전달되던 경로를 수정했다. 실제 Meshy 라이브러리 GET에서 0/1/14/466/502를 확인했으며, 리깅에 포함된 기본 walk/run은 추가 유료 작업 없이 재사용한다. 사용자 지정 ID와 실제 기본 파일 누락은 저장한 작업 의도로 처리한다. 기존 대상의 저장 클립 3개를 5개 완료로 표시하지 않는다.
- 기본 표정 neutral/smile/cry/angry/surprise 5개는 조립 뒤 별도 이미지 파이프라인→UV 베이크→PNG/body.glb/의상 포함 model.glb 저장→neutral 기본 선택으로 이어진다. 새 작업의 default_expressions=true 계약이 있는 경우만 실행한다. 재시작·재조립은 최초 5개 생성 ID·이미지를 재사용한다. 완성한 표정은 부분 실패 중에도 보존하며 expressions 단계부터 재개할 수 있다. 완료 판정은 실제 봉인 파일의 존재·SHA-256도 확인하고 손실 시 저장 응답으로 재베이크한다. 명시적으로 저장된 사용자 표정 선택은 보존한다.
- 눈 투영은 브라우저의 머리 X/Y 개별 확대 코드를 제거하고 서버의 정사각 등비 투영으로 통일했다. 조립은 1024×512 baseColor atlas에 기존 피부와 얼굴 전용 UV를 분리하고 normal/ORM UV·기존 메시·재질 그룹을 유지한다. glTF V 원점 상하 뒤집힘을 수정했고 frozen 재조립은 기존 atlas를 보존한다. UV 준비 불가 시 조립은 보존하고 표정 단계에 기술 오류를 남긴다. 실제 새 표정 5종 외형·Blender 실행 검증은 하지 않았다.
- 이동 연습장은 gaesup-world 3인칭 카메라 거리·높이·줌·추적을 조절하고 96×96 평지와 외곽 collider를 추가했다. 스튜디오/이동 전환 후 저장된 표정 텍스처를 복원한다. 표정 수신 전 화면이 먼저 열려도 neutral 도착 후 자동 적용하며 최근 텍스처 3세트만 캐시한다.
- 2D 이모티콘 원화 탭을 연결했다. 편집 프롬프트/초안, 새 원화·선택 원화 참조 생성, 이력/비교/기준 선택/PNG, 같은 요청 복구를 사용한다. SVG 변환·2D 리깅·자세 자동 생산은 아직 구현하지 않았다.
- 최종 검증: npm run build, backend compileall, uv build --package asset-3d-api, git diff --check 통과. 중간에 담당 agent가 합성 GLB로 베이크 함수 1회를 확인했지만 실제 사용자 산출물 검증과 구분한다. pytest/Playwright/실제 이미지·Meshy 생성·Blender 재조립은 미실행이다. 최종 GET에서 기존 조립 버전/표정 0개 보존, 새 schema default_expressions 및 expressions 재개 경로, illustration ready=true/원화 0개, UI HTTP 200을 확인했다.
- 실행: `./start-local.ps1`, UI http://127.0.0.1:5273/ (2D 원화 `?tab=emoticons`), API http://127.0.0.1:8071, API PID 34156, 로그 `data/local-runtime/78605bdfa387424eb40dabc459809da0/`, revision `5e93473dc963124a5dd97b8131e67477983b5c1c075ead204526b07d3dbeb82d`. Phase=ready/FactoryReady=True. 기존 PostgreSQL degraded와 큰 viewer/physics 번들 경고는 유지된다. 원격 배포 없음.

2026-09-19 원본 규격 정규화와 별도 표정 파이프라인, 임의 기본 눈 제거:

- 새 사진 전체 생성은 `prepare_reference=true`로 공통 규격 정면 이미지 1장을 먼저 요청하고 배경을 제거한 뒤 파츠 정면/측면 12장으로 이어진다. 원본 source.png, 제공자 canonical-raw.png, 처리된 canonical-reference.png와 요청/응답 영수증을 각각 S3에 보존한다. 새 작업 예산은 이미지 13장이고 구 요청은 payload/idempotency 입력을 바꾸지 않는다. 새 정규화 이미지의 실제 생성은 실행하지 않았다.
- 표정은 몸 버전별 별도 `expression-generations` 파이프라인이다. 종류/프롬프트 편집 → 명시적 이미지 1회 요청 → 상태/완료 PNG → 얼굴 적용 → UV 텍스처 저장/교체를 연결했다. 정규화 참조와 원본 눈 참조를 함께 봉인하고, 눈 윤곽/비율/홍채색/하이라이트/선 굵기 보존 지시와 정확한 provider prompt를 작업 기록에 고정한다. 응답 유실은 같은 요청 키와 저장 응답으로 복구하며 새 유료 POST를 자동으로 만들지 않는다.
- 사용자 지적에 따라 이번 작업 중 넣었던 임의 Canvas 기본 눈·표정 그리기(drawFace)와 관련 버튼/슬라이더를 완전히 제거했다. 저장된 표정을 선택하지 않은 기본 몸에는 얼굴을 덧그리지 않는다. Chrome 실제 화면에서 눈/입이 없는 상태와 별도 표정 요청 패널을 확인했다. 원본 기반으로 새 눈을 생성해 외형을 확인한 것은 아니다. 기본/웃음/울음 등은 실제 생성 PNG로만 적용하고, 저장한 UV 선택은 S3에서 복원한다.
- 실제 화면에서 작업 폴링 시 단계 실행 패널이 반복해서 쌓이는 오류를 확인했다. CharacterFactory의 StageRunner와 NativeAssembly가 같은 sibling key를 사용하던 문제를 수정했고 새로고침/후속 조회에서 실행 패널 1개를 확인했다. 표정 전환은 몸의 기존 UV 재질을 교체하며 추가 메시를 만들지 않고 최근 아틀라스 3개만 캐시한다.
- 대상 작업 `10d7b694acea4cee13821bfe` / 캐릭터 `char-fd8d1bdf8d35`. 작업 중 서버에 새 저장 조립 `6eb5a127ce0d0a9a633516fa`가 나타났다. 기존 API 8067 로그에 `native-parts?canonical_pose=true` POST가 있으며 이 턴 에이전트가 보낸 요청은 아니다. GET에서 review_required/100%, 12개 이미지·6개 3D 보존을 확인했다. 입력 recipe는 v10이지만 실행 결과의 hat 피팅은 변경된 head 측정 함수였다. 실제 화면에서 머리카락에 모자가 가려져 외형 완료로 판정하지 않았다.
- 모자 피팅은 고정된 큰 박스 대신 실제 머리와 피팅된 상부 머리카락의 폭/정수리를 사용하도록 보완했다. 요청의 파츠 순서와 무관하게 모자를 마지막에 피팅하고, 상부 머리카락 샘플이 없으면 기존 머리 기준으로 처리한다. recipe `native-parts-v12-hair-crown-headwear`; recipe 차이도 fit_update_available에 반영한다. 현재 자료의 계산상 모자 폭은 약 0.588m/정수리 1.40m이며 새 실제 조립 결과가 아니다. 원본과 기존 조립은 보존했고 에이전트 재조립·유료 이미지/Meshy 호출은 실행하지 않았다.
- 최종 검증: frontend npm run build, backend compileall/uv build --package asset-3d-api, git diff --check 통과. Chrome에서 임의 눈/입 제거, 별도 표정 요청 패널 및 중복 실행 패널 제거를 직접 확인했다. 새 정규화·표정 실제 생성, 선택 저장/새로고침 복원 실조작, pytest/Playwright는 미실행이다. 마지막 API GET에서 기존 조립 version 유지, fit_update_available=true, expression generation ready=true/작업 0개, 원본 눈 보존 neutral 기본 프롬프트를 확인했다.
- 최종 실행: `./start-local.ps1`, UI http://127.0.0.1:5273/ , API http://127.0.0.1:8070, API PID 8012, 로그 `data/local-runtime/ac3ecd5184c34f4abb7fa42e3243710e/`, revision `2e62ea7df84359daba70645e39a7ce68bb6e55b11bab5c96683c2b23fc1f42e7`. Phase=ready/FactoryReady=True. 기존 PostgreSQL health=degraded와 대형 viewer/physics 청크 경고는 유지된다. 원격 배포 없음.

2026-09-19 프롬프트·기물·3D 타일 및 재발한 리깅 422 복구:

- 최신 실패 작업 `10d7b694acea4cee13821bfe` / `char-fd8d1bdf8d35`가 2026-09-19T05:25:31Z에 생성됐고, 원본 리깅 응답은 HTTP 422 / pose estimation failed다. 몸 생성 요청에는 이미 `pose_mode=t-pose`가 있었다. 구 작업 `95c3e86eee764d503f7a7115`의 오류 표시만 남은 상황이 아니다. 원래 이미지·3D 및 제공자 거절 기록을 보존한다.
- 422가 발생한 사진 전체 생성은 별도 지정 동작이 없고 같은 프로필의 저장 골격이 있으면 로컬 골격 전사→조립으로 이어간다. 응답 불확실/다른 HTTP 실패에는 적용하지 않는다. 기존 복구 기록이 있으면 자동 중복 실행하지 않는다. 복구 버튼은 제작 진행률 바로 아래에 옮겼고 권장 골격을 기본 선택한다. 실행 중에는 이전 Meshy 오류 대신 실제 골격 연결 상태를 표시한다.
- 사용자 최신 오류 해결 요청에 따라 기존 에셋만 사용하는 로컬 복구를 실행했다. 요청 키 `repair-rig-10d7b694-20260919-01`, 복구 ID `e4b219e3d3ccbd708fd08683`, donor `cac779f1448c241dbd9c9104` / 버전 `6cb5c1e8cd847e3684708c6a`. 복구 complete, 골격 버전 `99213d9cfa1111bc77ff2ca7`, 24 bones 및 기존 walk/run 포함 3개 clip이 저장됐다. 조립 버전 `ae258740c23e74080b8e6e88`은 review_required, model.glb/6개 파츠 GLB/master.blend/저장 렌더를 S3에 보존했다. 최종 실제 GET의 character_flow=complete, progress=100, error=null을 확인했다. 새 유료 이미지/Meshy 요청은 없다. 이는 최신 작업의 실제 로컬 복구 결과이며 새 작업에서 자동 422 전환의 재현 시험이나 외형/동작 시각 승인까지 수행한 것은 아니다.
- 몸·헤어·모자·상의·하의·신발 프롬프트를 편집/초기화하고 초안을 보존한다. 고정 카메라·미터 규격·격리 조건은 유지하며 수락한 디자인 입력을 작업에 저장한다. 기물 탭의 가구·나무·소품은 편집 프롬프트로 이미지→Meshy를 연결했다. 타일은 기본 생성 및 프롬프트 생성 모드를 분리하고 나뭇결·나무껍질·벽돌을 추가했다. 선택한 PBR 타일을 평면/상자/구, 반복 횟수와 회전으로 볼 수 있다.
- WebGPU 초기화 뒤 미리보기를 마운트하고 화면 밖/숨김 탭에서 렌더링을 중지한다. 반복 횟수 변경 시 텍스처 재요청을 피하고 오류/늦은 로드도 자원을 해제한다. 기물 원본 GLB를 보존하며 런타임 텍스처 최대 크기를 조절한다. 프롬프트 타일의 normal은 albedo 명도 근사로 출처를 명시한다. 생성 요청 키/입력/제공자 영수증/산출물을 S3에 저장하고 불확실한 유료 POST는 재제출하지 않는다.
- 확인: frontend npm run build, backend compileall 및 uv build --package asset-3d-api, git diff --check 통과. 프록시 GET에서 UI 200, 6개 design_prompt_defaults, 기물/프롬프트 타일 capabilities.ready=true, 기존 기본 타일 2개 보존을 확인했다. pytest/Playwright/새 유료 생성 검사는 실행하지 않았다. 공식 API 참조: https://docs.meshy.ai/en/api/rigging 및 https://developers.openai.com/api/reference/resources/images/methods/generate . 브라우저 3D 시각 검수는 미실행이다.
- 실행: `./start-local.ps1`, UI http://127.0.0.1:5273/ , API http://127.0.0.1:8067, API PID 50684, 로그 `data/local-runtime/eae80dbae424458fb34a6c14eeb55830/`. Phase=ready, FactoryReady=True. 최신 복구 결과: http://127.0.0.1:5273/?tab=character&mode=photo&photoCharacter=char-fd8d1bdf8d35&photoJob=10d7b694acea4cee13821bfe . 기존 PostgreSQL health=degraded, 대형 viewer/physics 청크 경고는 유지된다. 원격 배포 없음.

2026-09-19 사진 드래그앤드롭·파츠별 갤러리 관리:

- 사진 전체 생성 및 관리자 기본 몸 추가의 공통 CharacterFactory 입력에 PNG/JPEG 1장 드래그앤드롭을 추가했다. 기존 api.create → api.upload 경로, 파일 선택/키보드/붙여넣기를 유지하며 중복 접수 잠금, 중첩 drag 진입 강조, 잘못된 형식/다중 파일 오류, 페이지 파일 드롭의 브라우저 이동 방지를 연결했다. 드롭만으로 유료 생성을 제출하지 않는다.
- 관리자 갤러리 카드에 파츠별 이름 수정·삭제·복원을 추가했다. 이름/파츠 검색, 휴지통 목록과 개수, 기존 머리/앞머리/뒷머리 분류, 이미지 없는 모델 카드도 표시한다. 작업 단위 이름/보관은 기존대로 유지하며 파츠 이름이 우선한다.
- S3 catalog.json에 `parts[job_id:slot]`을 추가했다. PATCH `/api/studio/catalog/{job_id}/parts/{slot}`은 소유권·실제 저장된 파츠·이름 1~80자·If-Match revision을 검사한다. 작업/파츠 메타데이터 저장 로직을 공통화했고 동일 필드의 응답 유실 재요청은 동일 상태로 처리한다. 삭제는 휴지통용 tombstone이며 원본 GLB/이미지·기존 조립본·제공자 기록은 삭제하지 않는다.
- 삭제된 기본 몸은 새 파츠 생성과 골격 복구 선택 목록에서 제외하고 서버에서도 새 접수를 거절한다. 이미 접수한 작업의 동일 키 복구와 기존 조립은 유지한다. 새 body 이름은 기본 몸 선택과 골격 목록에 반영한다.
- 검증: frontend npm run build, backend compileall 및 uv build --package asset-3d-api, git diff --check 통과. 실제 GET에서 관리자 UI 200/제목, catalog.parts 응답, 저장 골격 목록 9개를 확인했다. 브라우저 드롭/저장/삭제 실조작, pytest/Playwright/생성 검사는 실행하지 않았다. 기존 catalog revision=0을 유지했으며 실제 사용자 에셋 이름변경·삭제 PATCH도 보내지 않았다.
- 실행: `./start-local.ps1`, UI http://127.0.0.1:5273/?tab=admin , API http://127.0.0.1:8066, API PID 1756, 로그 `data/local-runtime/8a9d585c1ea84f1291321e4c27a52d09/`. Phase=ready, FactoryReady=True. 기존 PostgreSQL 연결 실패에 따른 health=degraded와 viewer/physics 큰 번들 경고는 유지된다. 원격 배포·유료 생성 없음.

2026-09-19 Meshy HTTP 422 작업의 저장 골격 복구 경로:

- 대상은 `95c3e86eee764d503f7a7115` / 캐릭터 `char-fd8d1bdf8d35`. 저장된 정면 몸 이미지는 이목구비 없는 큰 머리와 벌어진 팔다리의 T 자세였고, 원본 generated-body.glb는 6,150,176 bytes, POSITION 7,027개, 재질 1개/이미지 3개/skin 0개였다. 원본 Meshy 거절 응답 본문이 없어 정확한 거절 원인을 특정하지 않는다.
- 캐릭터 결과와 관리자 동작 패널에 `저장된 골격으로 복구`를 추가했다. 소유자의 완료된 기본 몸 버전에서 골격·동작을 선택하여 새 몸의 형상/텍스쳐를 유지한 균일 미터 스케일과 몸 표면 가중치 전사로 연결한 뒤 기존 파츠 조립을 이어간다. 기존 Blender 바인딩·내보내기 및 조립 서비스를 재사용한다. 새 Meshy/이미지 유료 POST는 없다.
- `/api/avatar-factory/rig-transfer/sources`, `/jobs/{job_id}/rig-transfer` GET/POST를 추가했다. 입력/원본 해시·고정된 소스 버전·실행 프로세스·출력 해시를 S3 영수증으로 보존하며 원래 422 및 이전 worker 기록도 보존한다. 복구 성공 출처는 `transferred_meshy_rig`로 구분한다. 완료된 복구 뒤 이전 중단 메시지가 조립 결과를 덮거나 Meshy를 재제출하지 않도록 연결했다.
- 접수 응답 유실에는 localStorage에 보관한 같은 입력/키로 재조회·재전달한다. 일치하는 request_key만 접수 근거로 사용한다. Blender 실행 잠금과 scratch workspace를 조립 전에 해제하며 공장 큐와 workspace 잠금 순서가 뒤집히지 않게 했다. 실제 장애 재현은 실행하지 않았다.
- 검증: frontend npm run build, backend compileall 및 uv build --package asset-3d-api, git diff --check 통과. 프록시 실제 GET에서 대상 복구 상태 not_started/can_start=true, 저장된 골격 목록 9개, 원래 작업 blocked/rig 보존을 확인했다. 복구 POST·Blender·pytest·Playwright·유료 생성은 실행하지 않았다. 실제 가중치 변형/동작·조립 산출물은 아직 미검증이고 선택·실행된 복구 source도 없다.
- 실행: `./start-local.ps1`, UI http://127.0.0.1:5273/?tab=character&mode=photo&photoCharacter=char-fd8d1bdf8d35&photoJob=95c3e86eee764d503f7a7115 , API http://127.0.0.1:8065, API PID 51904, 로그 `data/local-runtime/37f072d3afc74002bb0d745546ed4384/`. Phase=ready, FactoryReady=True. 기존 PostgreSQL 연결 실패로 health=degraded이며 원격 배포는 실행하지 않았다.

2026-09-19 헤더·갤러리·Meshy 오류 표시 및 DRY/KISS 정리:

- 상단 이미지 배너를 제거하고 헤더/HTML 제목을 `GAESUP-STORE`로 통일했다. 텍스쳐 탭은 `기본 바닥 타일`이며 눈·모래·잔디·흙·돌의 기존 타일 생성, 해상도/시드, 반복 미리보기와 다운로드를 유지한다. 사진 한 장 전체 생성도 유지한다.
- 관리자 갤러리는 저장된 몸·헤어·모자·상의·하의·신발·무기·도구·안경 이미지와 생성 GLB를 표시한다. 선택한 작업의 피팅 GLB는 별도 링크다. 24개 단위 더 보기, 분류 필터, 상속 파츠 중복 제외, 관리 패널 이동을 추가했고 중복된 기본 몸 카드 목록은 선택 메뉴로 줄였다.
- 실제 중단 작업 `95c3e86eee764d503f7a7115`: 이미지 12/12, 3D 6/6 저장. 몸 생성 task `01a0b636-bfd4-7523-aa28-e7024652f20b`, 리깅 접수는 `submission_rejected` / HTTP 422이며 리깅 task ID는 없다. 기존 코드가 이 확정 거절을 ValueError와 작업 ID 보존이라는 일반 문구로 덮었다. Meshy 공식 rigging 문서의 422 설명은 pose estimation failed다. 이 작업의 원래 거절 응답 본문은 저장돼 있지 않아 세부 모델 원인까지 확인한 것은 아니다.
- 저장된 영수증에서 오류 원인을 도출하여 Meshy/진행률/단계 실행에 공통으로 표시한다. 리깅 실패를 3D 생성 중단으로 표시하거나 생성 단계의 100%를 리깅 진행률로 재사용하지 않는다. 이미 저장된 이미지/3D를 반복 실행하여 같은 거절에 도달하는 버튼도 비활성화한다. 앞으로 생성/리깅/동작 제출 응답은 비공개 S3 기록에 보존한다. 기존 기록·task ID·파일은 변경/삭제하지 않았으며 새 유료 요청이나 리깅 성공을 만들지 않았다.
- DRY/KISS: Meshy 중단 상태/이유와 실행 중 판정을 공통화, 이미지/파츠 API의 확정 거절 판정을 공통화, 4개 화면의 파츠 이름과 생성 슬롯을 공유한다. 참조가 없는 setting 래퍼와 관련 import, 기타 미사용 import/갤러리 상수를 제거했다. Python/TS 진입점·테스트·CLI·동적 Blender 코드 참조를 점검했다. character_blender.py의 json은 문자열로 붙이는 실행 코드에서 필요해 보존했고 avatar runtime/호환 API도 보존했다.
- 검증: frontend npm run build, backend compileall 및 uv build --package asset-3d-api, git diff --check 통과. pytest/Playwright/Blender/유료 생성 검사는 하지 않았다. 최종 프록시 GET에서 UI 200/제목, 해당 작업의 rig_pose_rejected 및 저장 수, 이전 정상 작업의 ready, 타일 목록 2개를 확인했다. 시각 검수와 새 리깅 성공은 미검증이다. 기존 viewer/Rapier 대형 청크 경고는 남는다.
- 실행 반영: `./start-local.ps1`, UI http://127.0.0.1:5273/, API http://127.0.0.1:8063, API PID 31580, 로그 `data/local-runtime/a169e66ee1e34f38ac1896166546f66a/`. Phase=ready, FactoryReady=True. 기존 PostgreSQL DNS 실패에 따른 health=degraded는 유지된다. 기존 서버 프로세스/사용자 자료를 종료·삭제하지 않았다. 원격 배포는 실행하지 않았다.

2026-09-19 사용자 정정 — 사진 한 장 전체 생성 유지, 텍스쳐는 기본 바닥 타일:

- 사용자 의도는 기존 캐릭터 사진 한 장 붙여넣기 → 기본 몸·헤어·모자·상의·하의·신발 전체 생성 흐름을 다시 사용하는 것이다. 몸만 별도 생성하는 새 production_mode를 만들지 않는다. 기존 character_parts 유료 범위 및 idempotency/복구 계약을 유지한다.
- 기본 몸은 생성 프롬프트 단계부터 이목구비·귀 없는 매끈한 머리로 요청한다. 기존 몸의 머리를 잘라 구체로 교체하던 임시 보정 코드는 제거했다. 현재 저장된 이전 원본과 보정 산출물은 삭제하지 않는다. 새로운 사진 기반 유료 생성은 실행하지 않았다.
- 신발 수정은 유지: 좌우 연결 성분 분리, 발별 rigid weight, 전체 몸 표면 보정 제외, T 자세 정렬 후 최종 발 중심에서 간격 재피팅. 로컬 보정 산출물 `6cb5c1e8cd847e3684708c6a`가 S3에 저장되었고 결과 기록의 최종 좌우 간격은 0.00800000457m다. 이는 새 몸을 처음부터 생성한 결과가 아니다.
- 텍스쳐 탭은 눈·모래·잔디·흙·돌의 반복 바닥 타일(albedo/normal/ORM), 256/512/1024px, 시드, 3×3 반복 미리보기를 뜻한다. 캐릭터 표정 작업과 구분한다.
- 프론트 연결 완료: 캐릭터 탭 기본은 `사진으로 전체 생성`, `기본 몸에 파츠 생성`은 별도 토글이다. PNG/JPEG Ctrl+V 및 파일 선택을 지원한다. 텍스트 입력의 붙여넣기는 유지하며, `photoCharacter`/`photoJob`/`partsJob`으로 모드별 URL 상태를 분리했다. 관리자 기본 몸 추가도 같은 전체 생성 화면을 사용한다.
- 검증: frontend npm run build, backend compileall 및 uv build --package asset-3d-api, git diff --check 통과. 브라우저/pytest/실제 유료 생성 검사는 실행하지 않았다. 저장된 기존 작업의 로컬 신발 보정 근거와 새 사진에서 전체를 생성하는 미실행 경계를 구분한다.
- 최종 실행: ./start-local.ps1, UI http://127.0.0.1:5273/?tab=character&mode=photo, API http://127.0.0.1:8061, 로그 `data/local-runtime/78cbe593fe4b437db06c8da58c487a47/`. Phase=ready, FactoryReady=True. 기존 PostgreSQL 연결 불가로 health=degraded. 원격 배포와 새 유료 이미지/Meshy 제출은 하지 않았다.

2026-09-19 무표정 기본 몸·신발 수정 진행 중:

- 사용자 최신 요청: 기본 몸은 이목구비 없는 달걀형 머리, 신발 늘러붙는 문제 수정. 최신 실제 작업 `cac779f1448c241dbd9c9104`의 이전 조립 `3370ffcae0a5139180557365`에서 기본 몸에 눈/눈썹/입이 포함된 렌더를 직접 확인했다.
- 원본 얼굴 보존 프롬프트를 삭제하고 기본 몸용 프롬프트/규격을 무이목구비로 변경했다. 기존 저장 몸은 머리 상단 크기에 맞춘 smooth egg surface와 256px 단색 UV 텍스쳐를 가진 별도 파생본으로 만든다. 원본 에셋은 보존한다.
- 신발은 전체 몸 표면 projection/가중치 전사 대신 좌우별 연결 geometry 피팅과 LeftFoot/RightFoot 단일 본 고정을 적용한다. 중앙 bridge 면이 있으면 실제 mesh 절단으로 분리한다. 균일 스케일과 좌우 간격 보완 중이다.
- 로컬 재조립 접수 버전 `c58ceb5f52d7028e821188b5`, API 8058, UI http://127.0.0.1:5273/, 로그 `data/local-runtime/baea60257ac640dfb60ca1956c83d6b5/`. 새 유료 작업 없음. 결과 저장 및 수정본 직접 확인 전이므로 완료로 기록하지 않는다.

2026-09-19 Internal server error 후속 수정:

- 기존 API 8055 로그에서 `POST /api/characters`의 HTTP 500을 확인했다. 요청 ID `63bc286b-b416-4624-8056-40c06d9f80fc`. S3 StoredPath로 전달된 `.registry.lock.guard`를 `a+b`로 열면서 `Cloud assets support complete reads and writes only` 예외가 발생했다. 같은 오류의 이전 요청 2건도 로그에 남아 있다.
- `process_identity.lease_guard`는 OS 잠금 파일을 pathlib.Path로 명시적으로 열도록 수정했고, object_storage의 S3 경로 매핑에서 `.lock.guard`를 제외했다. 에셋·작업 기록의 S3 저장 계약과 기존 데이터는 보존했다.
- 검증: backend compileall, uv build --package asset-3d-api, git diff --check 통과. pytest/Playwright/생성 검사는 실행하지 않았다. 캐릭터 등록 POST도 재전송하지 않아 수정 후 실제 등록 결과는 아직 확인하지 않았다. 사용자에게 오류 화면/주소를 요청한 상태이며 로그 오류와 사용자가 본 화면의 일치는 아직 별도 확인 전이다.
- `./start-local.ps1`로 반영: UI http://127.0.0.1:5273/, API http://127.0.0.1:8057, API PID 48724, 로그 `data/local-runtime/ec484f705b0b45d49436991a3e9053d1/`, Phase=ready, FactoryReady=True. 프록시의 현재 API revision/PID 일치를 시작 스크립트가 확인했다. 기존 PostgreSQL 연결 불가로 health=degraded는 유지된다. 기존 서버 프로세스는 종료하지 않았다.
- 아래 기존 dist/aws 준비 아카이브는 이 잠금 수정 전 버전이다. 배포 전 prepare-aws.ps1로 재생성이 필요하며 이번 오류 수정에서는 원격 배포를 실행하지 않았다.

2026-09-19 관리자·동물·캐릭터·텍스쳐 및 자동배포 준비 (현재 코드):

- 기존 작업 트리와 저장된 산출물은 보존했다. 캐릭터는 저장된 기본 몸을 선택해 헤어·모자·상의·바지/치마·신발·무기·도구·안경을 생성한다. 관리자에서 몸과 파츠 버전의 이름/보관/GLB를 관리하고 몸별 Meshy idle/walk/run/jump/fall을 지정한다.
- 헤어는 명시한 숏/롱을 우선하며 설명에 명확한 길이 단서가 있으면 적용한다. 두상 폭과 정수리는 고정하고 아래 머리 길이를 별도로 조정한다. 바지와 치마를 구분해 치마는 골반, 바지는 몸 표면에서 전달한 다리 가중치를 사용한다. 실제 새 헤어·하의 생성/조립은 이번에 실행하지 않았다.
- 동물의 강아지/고양이/용 4족 리그는 별도 Blender 경로다. 업로드와 실행 영수증·재시작 상태·산출물 해시를 연결했다. 눈/모래/잔디/흙/돌은 반복 가능한 albedo/normal/ORM WebP와 WebGPU material manifest를 S3에 저장하는 구현이다. 웃음/울음 등 기존 UV 표정 저장·적용 경로를 유지했다.
- 최적화 구현: 파츠별 삼각형 목표, 몸 1024/주요 파츠 512/소형 장비 256px 텍스쳐, 무광 PBR 보정, 같은 슬롯 내 동일 재질/메시 통합, 내보낸 GLB의 실제 삼각형/드로우 수 기록, 화면 밖 렌더 중지, GPU 자원 해제 공통화. 기존 저장 GLB를 이번에 재조립한 것은 아니며 실제 WebGPU FPS/메모리 및 외형은 미검증이다.
- 진입점·import·테스트·스크립트 참조를 확인해 미사용 Factory/ImageWorkbench/StandardFactory 화면 트리와 전용 CSS/API·보조 컴포넌트를 제거했다. 현재 앱과 공개 avatar 런타임/호환 백엔드 API는 유지했다. 삭제된 스킬/문서 참조와 상충하던 하위 AGENTS 검증 지침도 정리했다.
- 무기/도구/안경이 포함된 단계 재개를 공통 파츠 계약에 연결했다. 동일 idempotency 요청의 접수 후 background 전달 유실은 queued/accepted 영수증을 재전달하며 executor의 잠금·상태 검사로 중복 실행을 막는다. 공백 S3 설정의 로컬 우회도 막았다. 이 복구 코드는 문법/빌드 근거만 있고 장애 재현 검사는 실행하지 않았다.
- GitHub main→OIDC→S3 불변 릴리스→SSM EC2 업데이트, 릴리스 SHA 및 /version.json 확인, 이전 컨테이너 복구를 구현했다. 실제 AWS에서 기존 S3 비공개/암호화/versioning/owner-enforced 및 두 CloudFormation 템플릿 검증을 확인했다. 전용 gaesup-asset-studio EC2는 아직 없으며 stack/OIDC 배포 역할/GitHub production 변수 연결과 실제 배포는 남았다. S3 릴리스 업로드나 EC2 생성은 하지 않았다. 최종 아카이브와 해시는 dist/aws/receipt.json을 따른다.
- 최종 준비 아카이브 SHA-256: `0ff98927eea3604cc63b709dd2fced85d95831f0d4fa3cd947b3ee19cacbf7af`. 패키지에 포함된 모든 파일이 현재 소스와 일치함을 확인했다. uploaded=false, ec2_created=false.
- 검증: frontend npm run build, backend compileall 및 uv build --package asset-3d-api, 배포 스크립트 문법 통과. pytest/Playwright/실제 생성 검사는 사용자 지시대로 실행하지 않았다. Vite의 viewer/physics 대형 chunk 경고는 남아 있다.
- 실행: ./start-local.ps1, UI http://127.0.0.1:5273/, API http://127.0.0.1:8056, 로그 data/local-runtime/0e42b3d3cc3b4834ac316c2fe0e03ad3/. 시작 영수증 data/local-runtime/current.json의 Phase=ready, FactoryReady=True. 이전 8055 프로세스는 보존했다. 기존 PostgreSQL 연결 불가로 health=degraded다.
- 이번 턴 신규 유료 작업 ID는 없다. 실제 제공자 산출물·동물 리깅·타일·표정의 브라우저 검수와 원격 자동배포 성공을 완료로 주장하지 않는다.

2026-09-19 후속 구현 및 실물 확인:

- 자세 정렬 새 버전 `e3805d182449af6f940bb816` 저장 완료. 정면/측면 기본 몸과 착용 정면/걷기 프레임 직접 확인. 양팔 손목 좌표 ±0.348822773 / 0.583973348 / 0.045629341m, 다리 좌우 X=±0.049002871m, hip/knee/ankle의 Z=0.038853385m, 발목 높이=0.073455036m, 발끝 Z=0.102153629m. 기존 3개 클립을 rest 변경에 맞춰 재기록했다. 원본 몸은 보존했다.
- 의상 전용 네 방향 렌더를 더한 `b78176797d91dbd80bd38b04`도 저장 완료. 기본 몸 단독은 38,205삼각형/21재질/텍스쳐1개/5,911,728바이트임을 실제 GLB에서 확인하여 기본 몸에도 8,000삼각형 목표를 적용하는 후속 조립을 시작한다. 몸까지 감면한 결과는 아직 직접 확인하지 않았다.
- 무기·도구·안경 입력, 기본 몸 관절 좌표 기반 생성 명세, 손/머리 고정 연결을 구현했다. 기존 장비 API의 `ImageSlot`/`equipment_layer` 계약을 함께 유지했다. 신규 장비의 실제 유료 생성은 추가 실행하지 않았다.
- 웃음/울음/화남/놀람/눈감기: 기존 UV 텍스쳐 합성, 위치 조절, S3 표정/GLB 저장, 저장한 표정 다시 적용 경로를 구현했다. 아직 실제 브라우저 표시·저장 확인 전이다. CUA의 브라우저/앱 목록이 모두 비어 있어 캔버스 검수는 못 했다.
- UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8055`, 로그 `data/local-runtime/35d2907091264e498cfc0fec1a5f9bb5/`. 실제 카탈로그·동물·텍스쳐·표정 목록 API 모두 HTTP 200. 코드 빌드/문법 통과; 이후 몸 감면과 복구 경로 변경에 대한 최종 빌드는 남았다.
- 서버 재시작 중 기존 장비 타입 참조 누락을 발견하여 복구했다. 프로세스가 없는 실패한 8055 기동을 확인한 뒤 같은 포트로 정상 기동했다. 기존 8054 등 프로세스는 종료하지 않았다. 저장된 기본 몸에 Meshy 리깅을 다시 유료 제출하는 경로를 차단하고 기존 클립 메타데이터를 표시한다.

2026-09-19 스튜디오 전환 진행 중. 아래 과거 완료 기록은 전체 요청 완료를 뜻하지 않는다.

- 화면을 관리자페이지·동물·캐릭터·텍스쳐로 전환했다. 저장된 기본 몸에서 파츠 생성, S3 카탈로그 이름/보관, 몸별 Meshy 동작 설정, 동물 GLB와 별도 4족 리깅 경로, 반복 타일 생성 경로를 추가했다. 표정 및 무기/도구/안경 연결은 남아 있다.
- 실제 재생성 작업 `bb4e5f5172299cb068f0af58`, 기본 몸 출처 `aa706790f3b54fdca6bf2a9a` / `a454822a912efc4d0674a8f9`, 요청 키 `zero-tilt-base-parts-20260919-01`. 상의·하의·신발 정면/측면 이미지 6개와 Meshy 3개가 실제 완료되어 S3에 저장됐다. Meshy 작업은 `01a0b5ac-6e7b-77f4-a23b-e509323f08ee`, `01a0b5ac-7f58-7313-8d96-0d2fd97aa8eb`, `01a0b5ac-8e16-76f2-b218-f96cbcec1723`이다.
- 최신 저장된 조립 `7d31f7591e91e4ee993c41ad`, 로컬 재조립 요청 `6b97fc3b28df998920103da0983171e17b610e75e0ebe8348b6f3c46ef160df3`, 키 `zero-tilt-welded-lod-20260919-01`, complete. 원본 GLB 보존, 파츠 감면 전 겹친 정점을 연결하여 깨지는 표면을 수정했다. 정면/측면/후면 직접 확인. 팔은 수평이나 기존 몸의 무릎·발끝 축이 조금 비틀려 있어 추가 보정 중이다. 정확한 전체 자세 완료로 기록하지 않는다.
- 파츠별 폴리곤/1024 텍스쳐 상한과 정지 장면 demand 렌더를 적용했다. 실제 WebGPU FPS와 전체 몸 포함 성능은 아직 확인하지 않았다. 동물 리깅과 타일은 구현/빌드 근거만 있고 실제 입력 결과 검수는 남아 있다.
- CLI로 전용 S3 버킷 접근과 공개 차단, 기존 EC2 목록을 조회했다. 기존 인스턴스는 변경하지 않았다. `infra/prepare-aws.ps1`로 CloudFormation 검증 및 배포 아카이브 준비만 수행했다. EC2 생성·배포는 아직 하지 않았다. 이후 코드 변경으로 아카이브를 다시 만들어야 한다.
- 현재 UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8053`, 로그 `data/local-runtime/8bde02e3e8af45dda0a21451c501b486/`. FactoryReady=True, 기존 PostgreSQL 연결 불가로 health는 degraded. 프론트 빌드와 백엔드 문법/패키지 빌드 통과. pytest/Playwright는 실행하지 않았다.
- 남은 확인: 다리·발 축과 클립 보정 후 실제 조립 결과, 무기/도구/안경 및 표정의 실제 저장/착용, 동물 입력 리깅 결과, 타일 반복 결과, 재접속/작업 복구, UI 실제 연결, 최종 배포 준비물 및 코드 중복 정리.

2026-09-19 T자 팔/얇은 관절 반영 완료: 대상 `aa706790f3b54fdca6bf2a9a`. `shared-size-v14-t-pose-slender-joints`, 규격 16. 몸·소매를 같은 T rest pose로 변환하며, 소매 끝을 실제 손목에 먼저 정렬한다. 본 rest 변경에 맞춰 기존 동작 채널을 보정한다. 손목 0.028m·발목 0.032m, 기존 얇은 몸통 0.22×0.13m를 유지한다. 새 생성 가이드/프롬프트도 T자로 고정하고 미리보기의 최초 자세는 기본 자세로 표시한다.

- 최종 결과 `a454822a912efc4d0674a8f9`, 요청 `2c3bcbcddb3d3b7c41bf2cc8b2271858fa06da69aeb5e1a97006a4dd62da6694` complete, S3 저장 완료. 실제 기본몸 정면·착용 네 방향·걷기 1/4 프레임을 직접 확인했다. 팔 과대 연장과 몸통 밑단이 팔에 끌려가는 현상이 정리됐다. 실제 body.glb의 양쪽 어깨/팔꿈치/손목 높이는 모두 약 0.583973m, 손목 X는 +0.351098/-0.346551m다. run/walk/원본 기본 클립 보존. 프론트 빌드·백엔드 문법/패키지 빌드 통과. pytest/Playwright/유료 생성 없음. 브라우저 캔버스와 전체 동작 구간 직접 검증은 하지 않았다.
- 최종 실행 UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8051`, 로그 `data/local-runtime/d7275e33c93943f3be970373d430f347/`. 시작 영수증 갱신, FactoryReady=True, 재시작 후 단계 busy=false/complete 확인.

- 최신 요청 `2c3bcbcddb3d3b7c41bf2cc8b2271858fa06da69aeb5e1a97006a4dd62da6694`, 키 `t-pose-slender-wrists-20260919-03`, 접수 `2026-09-18T17:16:22Z`. API 8050, 로그 `data/local-runtime/93b9aeac7c434e4db680dd8ef102280a/`. 직전 `d881ae0991af3769a2ae3d05`에서 팔 길이와 손목 연결은 복구됐으나 겨드랑이 아래 옷감이 팔에 끌려갔다. 소매 영역만 팔 가중치를 사용하고 몸통/밑단은 몸통 본을 사용하도록 수정해 재조립 중이다. motion.png는 실제 walk 중간 프레임을 저장하도록 보완했다.
- 첫 결과 `1a088883079a3ba3dc6e98ab`는 직접 렌더에서 팔이 화면 밖으로 늘어난 것을 확인해 부적합으로 기록한다. Blender 표시용 bone.length를 관절 간 길이로 사용해 손목 X가 약 ±27m가 됐다. 실제 월드 관절 좌표 사이 거리로 수정했다.
- 후속 요청 `3ed6c5da50bcd0cec2c08eaf8227ac61ed626c13b7e6abfd8f307d224cda9cf7`, 키 `t-pose-slender-wrists-20260919-02`, 접수 `2026-09-18T17:12:58Z`. UI 5273, API 8049, 로그 `data/local-runtime/60bdbb3db69142e5b88b716d7b57d28c/`. 완료 후 실제 몸 단독/착용 팔 길이 확인 필요.
- 프론트 빌드·백엔드 문법/패키지 빌드 통과. UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8048`, 로그 `data/local-runtime/f17fe918b324415fb796ed2c4d007135/`.
- 기존 저장 모델 로컬 재조립 키 `t-pose-slender-wrists-20260919-01`. 새 유료 생성 없음. 실제 기본몸/착용 네 방향/동작 산출물 확인 중.

2026-09-19 머리/몸 소실 복구 완료 (아래 이전 결과보다 최신): 대상은 새 작업 `aa706790f3b54fdca6bf2a9a`다. 이전 작업 `e2219a05f982f7324f7ccaf5`만 보고 최신 화면을 확인한 것으로 판단하면 안 된다.

- 복구 결과 `240c92acd438a75299787e92`, 요청 `bf12874322127005314ecc3510042a7cf67527898dcf1f67a7031939fcac2397` complete, S3 저장 완료. 전체 네 방향·기본몸 정면·motion.png를 직접 확인했다. 얼굴/두상과 흰색 몸이 보존되고 일체형 긴 머리가 실제 머리에 맞게 복구됐다. 내피 최대 변위는 0.0651m, 머리 정수리 목표 1.27m, Head 연결 보정 15,222정점이다.
- 실제 제공되는 body.glb에 머리 높이 1.2m와 run/walk 클립이 보존됐고, 현재 조합은 hair/hat/top/bottom/shoes 전체를 포함한다. UI HTTP 200. 브라우저 제어 연결이 없어 실행 중인 캔버스는 직접 확인하지 못했다. 기존 소매 끝과 손목의 위치 차이는 렌더에 남아 있으며 이번 머리 소실 복구를 전체 피팅 품질 완료로 간주하지 않는다.

- 최신 저장 결과 `976acc44af4510a3b8f71172`의 전체/몸/머리 렌더를 직접 확인: 얼굴이 목 높이의 얇은 면으로 붕괴하고 hair가 가슴 크기로 축소됐다. 원본 Meshy GLB에서 얼굴 정점 14,735개가 LeftShoulder 지배 가중치를 가졌다. 얇은 몸 처리의 최대 변위 0.6004m와 Head 가중치만 사용한 머리 측정(정수리 0.6356m)이 원인이다.
- `shared-size-v13-preserve-geometric-head`: 실제 어깨 위 두상을 기하로 측정하고 Head 본에 연결한다. 골격/클립은 보존한다. 얇게 만드는 처리는 확인된 내피이면서 머리 아래인 정점에만 적용한다. 얼굴/피부를 팔 굵기로 축소하지 않는다. hair는 실제 두상 폭/정수리에 맞춘다.
- 프론트 빌드, 백엔드 문법/패키지 빌드 통과. UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8047`, 로그 `data/local-runtime/aac8ea0afe6c4892b95145ef7eb41d70/`. 현재 브라우저 제어 연결 없음; 실제 저장 렌더와 GLB를 확인 중이다.
- 기존 저장 파츠만 로컬 재조립 요청: `bf12874322127005314ecc3510042a7cf67527898dcf1f67a7031939fcac2397`, 키 `restore-head-body-20260919-01`, 접수 `2026-09-18T16:46:05Z`. 새 유료 생성 없음. 완료 및 직접 렌더 확인 결과는 위 기록을 따른다.

- 최종 실행 반영: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8046`, 로그 `data/local-runtime/d09bb3fe11254b65873194e4199fae08/`, FactoryReady=True. 프론트 빌드, 백엔드 문법 및 패키지 빌드 통과. 실행 OpenAPI에서 hair_length의 source/short/long 입력을 확인했다. 실제 저장 결과 `4114dc0915ef86bb4c42b8be` 네 방향 직접 확인 완료. 새 길이별 유료 생성은 실행하지 않았다.

2026-09-19 최신 완료 기록: 머리 길이를 두상 크기와 분리한 생성 프로그램을 반영했다.

- 새 입력 `hair_length`: `source`(원본대로, 기본값), `short`(두상 높이 1.0배), `long`(두상 높이 1.7배). 새 UI에서 선택하며 요청 영수증·pipeline.json·production_spec에 고정한다. 중간 단계 재개/조립에서도 해당 선택을 읽는다. 원본대로는 머리 폭에 맞춘 균일 배율을 사용하고 숏컷/롱컷 길이로 강제 늘이거나 줄이지 않는다. `shared-size-v12-hair-length-profiles`, `measured-views-v13-hair-length-profiles`.
- 흰색 내피·커진 긴 머리·독립 모자의 실제 저장 결과 `4114dc0915ef86bb4c42b8be`를 전체 네 방향에서 직접 확인했다. 파란 가슴 면이 사라졌고 모자의 얼굴 무늬가 다시 보이며 뒷머리의 수평 돌출선이 정리됐다. 이 결과는 기존 분할 생성 원본을 다시 맞춘 것이며 새 일체형 hair 생성 결과로 주장하지 않는다.
- 마지막 조립 요청 `44038f7e7c60caefca53fc6d996c9275ba0406a0318197feb639061f301786b9` complete. 유료 이미지/Meshy 새 요청은 없으며 새 길이 선택의 실제 유료 생성 결과는 아직 없다. pytest/Playwright 미실행. 프론트 빌드와 백엔드 문법 확인 통과, 패키지 빌드도 수행한다.
- 최신 실행 UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8045`, 로그 `data/local-runtime/665087443e7d4eed8573018f4d3c26a9/`. 다음 서버 반영 시 후속 주소를 기록한다.

- 마지막 경계 확인 실행: `44038f7e7c60caefca53fc6d996c9275ba0406a0318197feb639061f301786b9`, 키 `white-base-long-hair-crown-20260919-05`, `2026-09-18T16:01:01Z`. API `http://127.0.0.1:8044`, UI `http://127.0.0.1:5273/`, 로그 `data/local-runtime/d564ca16126b40acad14f967313f9d07/`. 직전 `110310c90fd7372bcf61a24b`의 네 방향을 확인해 모자 무늬/뒷머리 상단 경계가 남은 것을 보았고, 기존 분할 머리의 윗부분 단면을 두상 타원 단면에 따라 안쪽으로 정리했다. 머리 하단 폭·길이와 모자 독립 슬롯은 유지한다. 새 일체형 hair는 이 기존 분할 보정에 들어가지 않는다.

- 최신 확인/실행: 흰색·긴 머리 버전 `b1303039b68523d029d9e514` 저장 완료 후 전체 네 방향과 기본몸 정면/측면을 직접 보았다. 9,421개 내피 면이 흰색이며 가슴의 파란 면은 사라졌다. 머리 폭/길이는 확대됐지만 모자 무늬 가림과 뒷머리 상단 노출이 남았다. 기존 분할 머리의 윗뿌리만 공통 머리 곡면 안쪽으로 정돈하고 모자를 커진 머리 바깥 크기로 맞춘 후속 실행은 `b2586aa04098e1b086b71e62da6d2d93f95c773719191785ceb44dae3acc93f3`, 키 `white-base-long-hair-seat-20260919-04`, 접수 `2026-09-18T15:57:36Z`다. UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8043`, 로그 `data/local-runtime/63b7913740f34f0297f7687f1deedd8d/`. 새 hair는 비율을 유지하는 균일 배율로 목표 폭과 전체 길이를 확보한다. `shared-size-v11-white-base-full-hair-seat`. 이전 head 통합/voxel 경로는 사용하지 않는다.

2026-09-19 최신 지시: 기본 내피는 파란색이 아닌 흰색, 머리카락은 원본과 비교해 훨씬 크게 만든다.

- `data/image/A.png`를 직접 열어 비교했으며 SHA256 `5847b126384dec9a842155ee5d454ce0de81a5ffec2f0f6038253c5e9e70331c`가 대상 작업 원본과 같다. 원본의 풍성한 긴 뒷머리는 신발 위까지 내려오지만 이전 피팅은 하단 0.38m로 어깨 부근에서 끝나도록 제한하고 있었다.
- 새 hair 공통 목표는 너비 1.17m·하단 0.10m·정수리 1.27m, 실제 머리 너비 대비 1.5배다. 원본처럼 긴 양옆/뒷머리를 줄이지 않도록 프롬프트에 넣고 기존 분할 원본의 앞/뒷머리 피팅도 확대했다. 모자는 독립 슬롯을 유지하며 생성 시 완성된 hair의 정면/측면을 참조한다.
- 새 기본몸 생성은 얇고 불투명한 무광 흰색 내피다. 저장된 파란 기본몸은 조립 시 내피 면만 흰 재질로 바꾸고 피부/얼굴을 유지한다. 색 분류는 머리의 눈 등에 영향을 주지 않도록 목 아래로 제한했으며, 잘못된 보호 본 가중치가 있는 내피의 두께도 근접 골격 축으로 처리한다.
- 현재 로컬 조립 요청 `678be5f431fb234d29711eb819840095aa34e255ee053a831062982151906c91`, 키 `white-base-long-hair-20260919-03`, 접수 `2026-09-18T15:53:26Z`. UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8042`, 로그 `data/local-runtime/4e14d5337cf94a7aabf7e1248b1eb623/`. `shared-size-v10-white-base-full-hair`, `measured-views-v12-white-base-full-hair`. 저장된 기존 7종 파츠로 로컬 확인 중이며 새로운 일체형 hair의 유료 생성은 실행하지 않았다.
- 앞선 내피 경계 수정 요청 `f7c8c127ae27f99adca45271e371fbbfcc56c6a40909077ef226f17c34cc456b` / 버전 `f9759db8bbfd33f45b78b0be`는 저장 완료. 이는 흰색/긴 머리 변경 전 결과다.

2026-09-19 추가 지시: 파츠 절단면 불일치, 두꺼운 파란 기본몸, 머리 비율을 함께 수정 중이다.

- 실제 저장 버전 `a25377a0443bf81a1bf9f05f` 정면·측면·후면을 직접 확인했다. 이전 voxel union의 머리 재질/표면은 손상되어 사용할 수 없으며 해당 경로는 제거된 상태다. 새 생성은 머리카락 하나와 별도 모자 6종 구성을 유지한다.
- `base_body`: 몸통 너비 0.22m·깊이 0.13m, 팔 지름 0.036m, 다리 지름 0.044m. 생성 가이드와 본문 모두 얇고 불투명한 밀착 내피로 바꾸고 두꺼운 스웨트셔츠·바지·패딩·주름을 제외한다. 조립 시 기존 몸도 원래 스킨에서 의상 가중치를 복사한 뒤 골격 축 주변 두께만 줄인다. 얼굴/목/손발과 본·애니메이션은 보존한다.
- 기본몸 정규화는 높이에 따른 균일 배율로 원래 얼굴 비율을 보존한다. 새 hair는 실제 Head 가중치 정점의 머리 크기와 중심에 맞춰 균일 배율로 배치하며 XYZ 독립 확대를 하지 않는다. `shared-size-v9-slim-base-proportional-hair`, `measured-views-v11-slim-base-balanced-hair`.
- 옷깃 크롭은 후드 최상단 대신 목·어깨 관절 높이를 사용하고 Head/Neck 면을 자르지 않는다. 하의 밑단 바깥의 기본몸을 무조건 발목까지 자르지 않는다. 기본몸 단독 네 방향 렌더도 저장한다.
- 최신 프론트 빌드·백엔드 문법 확인 통과. 로컬 재조립 및 직접 렌더 확인 예정이며 유료 이미지/Meshy 새 요청은 없다.

2026-09-19 최신 정정: **머리카락만 처음부터 일체형으로 생성하고 모자는 별도 파츠로 유지한다.** 아래 과거 기록의 머리·모자 통합 해석과 통합 결과는 사용자 요구를 잘못 이해한 것이며 최종 결과로 인정하지 않는다.

- 새 생성 입력은 `body/hair/hat/top/bottom/shoes` 6종이다. `hair`는 앞머리·양옆·정수리·뒷머리·목덜미를 포함한 풍성한 머리카락 하나이고, 모자에 가려졌던 정수리도 완성한다. 머리카락 이미지에는 모자·토끼 귀·챙을, 모자 이미지에는 머리카락을 제외한다. `measured-views-v10-complete-hair-separate-hat`.
- 머리·모자 join/voxel union 및 모자 높이에서 머리카락을 잘라내는 함수를 제거했다. 새 `hair.glb`와 `hat.glb`는 독립 파일·착용 슬롯이다. 네 방향 렌더는 착용 모습, 머리카락 단독, 모자 단독을 별도로 저장한다. 기존 앞/뒤 파츠 작업의 재개는 원래 슬롯을 보존하며 이를 새 일체형 머리 생성으로 간주하지 않는다.
- 공통 피팅 `shared-size-v8-complete-hair-separate-hat`, 로컬 조립 `native-parts-v9-separate-hair-hat`. 의상에 가려진 파란 몸체 크롭과 중간 단계 재개는 유지한다.
- 직전 잘못된 통합 실행 `156dc3223afd2ffe6f9e76c27ab4762d742b11cf9f37769ba75421046c7095b3` / 버전 `a25377a0443bf81a1bf9f05f`는 저장 완료지만 사용자 요구에 부합하는 결과가 아니다. 기존 자료를 삭제하지 않았으며 정정 이후 새 유료 이미지·Meshy 요청이나 기존 머리 붙이기 실행은 하지 않았다.
- 정정 후 프론트 `npm run build`, 백엔드 `compileall` 통과. 패키지 빌드·실행 서버 반영은 아래 후속 기록으로 갱신한다. 새 생성 모델의 외형은 아직 확인하지 않았다.

2026-09-18: 중단된 구현 마무리. 아래 최신 기록이 이전 실행 주소·대기 기록보다 우선한다.

- 현재 실행 `156dc3223afd2ffe6f9e76c27ab4762d742b11cf9f37769ba75421046c7095b3`, 키 `head-review-20260919-05-surface`, 버전 `a25377a0443bf81a1bf9f05f`, API `http://127.0.0.1:8038`, UI `http://127.0.0.1:5273/`, 로그 `data/local-runtime/14091b975216456b8d78a0298b738ab7/`. 일체형 머리의 겹친 표면을 3.5mm voxel union으로 정리하고 원본 재질/UV를 투영한 뒤 Head 하나에 다시 바인딩한다. 오래된 분할 머리를 합치는 경로에만 적용한다. 모자 착용선 부근의 머리 뿌리를 안쪽으로 수렴시킨다. 정면/측면 렌더 생성 확인, 전체 저장/네 방향 확인은 대기 중.
- 직전 `54cfe0241a2f565670bfc603`는 저장 완료 후 네 방향 직접 확인: 모자 얼굴 무늬는 드러났지만 뒷머리 뿌리의 수평 절단선과 안쪽 거친 면이 남아 현재 surface 실행으로 수정 중이다. 새 생성은 일체형 head 입력만 받으며 이미 접수된 구 7종 작업은 기존 기록대로 재개된다.

- 최신 확인/추가 수정: 일체형 버전 `ba0a47103286cb0ad42a5226`(요청 `cd04f38e...`)은 S3 저장 완료 후 전체 정면과 머리 네 방향을 직접 봤다. 파란 몸체/중복 모자는 제거됐고 head 한 슬롯으로 합쳐졌지만 뒷머리 상부의 거친 잔여 면과 모자 무늬를 덮는 앞머리는 남아 있어 외형 완료로 보지 않는다. 원래 모자가 섞였던 뒷머리 윗부분을 잘라내고 온전한 아래쪽 머리결의 뿌리를 모자 착용선까지 이어 올렸으며, 모자 테두리 위로 나온 머리카락을 정리하고 머리 파츠 착용 시 가려지는 두피를 슬롯 마스크에 포함했다.
- 현재 실행 `f510c6f3af786cfb87104a9f491e0ed9503be340abf98d4e44587acc81e9de13`, 키 `head-review-20260919-04-seat`, 2026-09-18 15:23:48 UTC 접수. UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8037`, 로그 `data/local-runtime/1ef8e60bddef4f06abea98a06e2ca9c8/`, 규격 `shared-size-v7-unified-head-seat`. 완료 후 실제 네 방향 렌더 확인 필요. 유료 요청 없음.

- 최신 지시 변경: 앞머리/뒷머리/모자로 나누지 않고 풍성한 일체형 머리와 모자로 만든다. 새 캐릭터 공장은 `body/head/top/bottom/shoes` 5종 입력으로 변경했고 head 이미지·Meshy 작업 자체에 전체 머리와 모자를 함께 포함한다. 기존 7종 작업은 중간 단계 재개를 유지하며, 로컬 조립에서 머리 요소를 실제 하나의 메시/Head 바인딩/head.glb/착용 슬롯으로 합친다. 새 유료 생성은 실행하지 않았다.
- 현재 일체형 조립 실행: `cd04f38e133698b9b24d02cacc9d5e2c9c0bccf758118651c656cc084d1db0cd`, 키 `head-review-20260919-03-unified`, 2026-09-18 15:20:37 UTC 접수. UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8036`, 로그 `data/local-runtime/66d72f7fc8ac421d89fd73dd4bbc270b/`. `native-parts-v8-unified-head`, `shared-size-v6-unified-head`; 기존 헤어 폭 10%·깊이 14% 확대, 머리카락 25mm·두피 바탕 3mm 간격, 모자 원형 비율 유지. 프론트 타입/빌드·백엔드 문법 통과. 조립 결과 네 방향은 확인 대기 중이다.
- 직전 실제 수정 결과 `e6f5aca34be6cf6a224fc72e`: 로컬 조립·S3 저장 완료, 네 방향과 단독 뒷머리 렌더를 직접 확인했다. 파란 몸체 크롭과 중복 토끼 모자 제거, 납작하게 눌리던 모자 비율은 반영됐지만 뒤통수의 매끈한 바탕이 너무 드러났다. 바탕 7mm가 머리카락 6mm보다 바깥에 놓인 원인을 수정해 바탕은 3mm, 머리카락은 25mm로 분리했고 전체 볼륨을 키우는 일체형 실행으로 이어갔다.
- 재조립 대기 개선: `local_workspace`의 명시적 inputs를 추가해 현재 조립 버전과 입력 GLB만 임시로 처리한다. 과거 조립 전체/제공자 응답 재다운로드·재업로드를 없애고 기존 로컬 입력이 다르면 덮어쓰지 않는다. S3 저장 성공 후 이번에 만든 정확한 임시 파일만 정리한다. 이전 전체 다운로드 방식의 실행 `587d8cb...`와 다음 scoped 실행 `dfd82c1...`은 모두 저장 완료했다.

- 2026-09-19 후속 지시: 에이전트가 완성 모델을 직접 확인하고 머리·모자와 네 방향 보기를 수정한다. 이전 실제 조립/시각 확인 미실행 제한에 대한 이번 사용자 지시를 따라 저장 파츠의 로컬 조립과 렌더 확인을 진행한다. 유료 이미지/Meshy 요청은 없음. pytest/Playwright는 계속 실행하지 않는다. 연결된 CUA 브라우저가 없어 프로그램의 실제 Blender 렌더를 직접 읽어 확인한다.
- 현재 실행: 대상 `e2219a05f982f7324f7ccaf5`, 조립 요청 `587d8cb081b362508a7b7cfcc99a66e6daf906aca4de84c6410864166ce33e09`, 재사용 키 `head-review-20260919-01`, 2026-09-18 15:05:16 UTC 접수. UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8034`, 로그 `data/local-runtime/2b6dcdf809be441cbc5ce83d2ce01c98/`. 기존 파츠로 크롭 결과와 분리한 앞머리·뒷머리·모자의 정면/왼쪽/후면/오른쪽을 렌더 중이다. 프론트 타입/빌드·백엔드 문법 통과. 아직 이 실행의 완료/외형 확인 전이다.
- 확인한 이전 네 방향 결과: 뒷머리를 뚫고 나온 살색 뒤통수, 옆에서 두피와 분리된 머리 층, 모자의 뒤쪽 돌출을 확인했다. UI에 전체/머리·모자/앞머리/뒷머리/모자별 네 방향 저장 렌더를 연결했다. 앞·뒷머리와 모자 결합 수정은 분리 렌더 확인 후 진행 중이다.

- 2026-09-19 최신 지시: 옷이 너무 크므로 크기를 줄이고 파란 기본 몸체를 경계선으로 크롭한다. `shared-size-v4-body-crop` / `native-parts-v6-body-crop`로 변경했다. 상의 공통 폭/두께 0.74/0.276m, 하의 0.38/0.296m로 줄이고, 기본 몸체를 감싸기 위해 옷의 폭·깊이를 다시 키우던 경로를 끈다. 어깨 기준 높이 보정과 주름 보존은 유지한다.
- 몸체 크롭 구현: 의상 목둘레·밑단·허리, 골격 손목·발목, 신발 입구에서 실제 메시를 분할하고 슬롯별 숨김 재질을 지정한다. 표면 ray가 맞는 경우에만 가리던 조건을 제거해 옷 밖으로 튀어나온 기본 몸체도 크롭한다. 손/손가락은 제외하고, 목둘레 위 몸체는 유지한다. body.glb에는 모든 면과 숨김 슬롯을 남겨 착용 해제 시 복원하며, 전체 model.glb에서는 착용 슬롯에 해당하는 기본 몸체 면을 제외한다. 절단선은 결과 `body_crop_lines`에 기록한다.
- 백엔드 compileall·패키지 빌드 통과. `./start-local.ps1` 반영: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8033`, 로그 `data/local-runtime/555ad059b2ae4bf4b2a4580f63dc40b7/`, FactoryReady=True. 이번 변경에서 프론트 소스 수정 없음. pytest·Playwright·실제 생성/조립 검사는 실행하지 않았다. 새 크롭 조립 결과의 외형은 미확인이다.
- 읽기 전용으로 확인한 직전 사용자 조립: 대상 `e2219a05f982f7324f7ccaf5`, 버전 `1a3ede191afb525ac36d2e6c`, shared-size-v3-loose, 요청 `db7f828e8b09758d01c4e2755ebba43554ba152d9b5db51dea73a8abafc6f7d6` complete. 저장된 front.png에서 넓은 의상과 어깨·허리·종아리에 남은 파란 기본 몸체를 확인했다. 이 결과는 새 크롭 로직 적용 전이다. 중간 단계 `피팅·조립부터 실행`으로 기존 이미지/3D/리깅을 재사용한다.

- 최신 사용자 지시 반영: 몸에 밀착시키지 않고 여유 있게 크게 입힌다. `shared-size-v3-loose` / `native-parts-v5-loose`로 공통 규격을 갱신했다. 상의 목표 경계는 좌우 3.5cm·앞뒤 4cm, 하의는 좌우 3cm·앞뒤 3.5cm의 몸 표면 여유를 포함하며 밑단도 늘렸다. 상·하의에는 정점을 몸 표면으로 투영하는 보정을 하지 않아 원래 주름·볼륨을 보존한다. 이후 이미지 요청의 프롬프트에도 같은 여유 수치를 전달한다.
- 직전 사용자 실행 `c2e919e9f9267e368c64d9921de6cd82e27cc3c2f2eb84f1721e622b8731a566`은 14:44:40 UTC complete, 버전 `d90786d492f5fe440f9e5f32`(shared-size-v2-body-surface)는 파일 저장 완료. 기존 front/side와 body GLB를 읽어 상의가 가슴 아래로 눌린 모습과 neck 관절 높이 0.4255m가 실제 어깨 0.52m보다 낮은 것을 확인했다. 새 의상 피팅은 어깨 위치와 목 높이를 함께 사용해 상의 길이가 가슴 아래로 압축되지 않도록 했다. 이 직전 산출물을 새 여유 규격의 결과로 간주하지 않는다.
- 백엔드 compileall·패키지 빌드 통과. `./start-local.ps1` 반영: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8032`, 로그 `data/local-runtime/9aa31b31bd9c47c4b85e9f0ddd48c319/`, FactoryReady=True. 프론트는 직전 빌드 이후 변경 없음. pytest·Playwright·실제 생성/조립 테스트는 실행하지 않았다. 새 규격으로 조립한 시각 결과는 아직 미확인이다. 대상 `e2219a05f982f7324f7ccaf5`에서 기존 이미지·3D·리깅을 재사용하는 `피팅·조립부터 실행`에 새 규격이 적용된다.

- 저장된 실제 결과 확인: `e2219a05f982f7324f7ccaf5`의 단계 요청 `7e0c5cc05b06021a7863dd08672e7885c5a4cc625ba66ba37c15f605fd57ecdc`는 14:32:35 UTC complete, 조립 버전 `11f9c9f08230554deb8ec0fa`는 shared-size-v1 파일 저장 완료. 저장된 front/side PNG를 메모리에서 읽어 기본 청록색 상·하의가 새 의상을 가리는 문제를 확인했다. 파일 저장 성공을 시각 품질 완료로 판정하지 않는다. 에이전트는 생성/조립 POST를 제출하지 않았다.
- 원인 수정: 고정 XYZ 박스 외에도 실제 정규화된 몸의 neck/Hips/발목과 의복 영역 표면으로 피팅 대상을 보정한다. 의상은 15mm 이동 제한·최종 bbox 강제 클램프를 없애고 몸 표면 바깥으로 이동한 뒤 그 위치에서 스킨 가중치를 전사한다. 헤어·모자는 기존 제한을 유지한다. 실제 의상 표면이 덮는 기본 몸의 면만 착용 슬롯별 재질로 분리하며, 브라우저 착용/해제 시 가림/복원을 함께 적용한다. 전체 조립 GLB에서는 가려진 기본 몸 primitive만 제외하고, body.glb의 UV·스킨·기본 면은 보존한다. 품질 검사/출고 차단은 추가하지 않았다.
- 새 recipe `native-parts-v4-body-surface`, fitting `shared-size-v2-body-surface`. 프론트 타입/프로덕션 빌드·백엔드 문법/패키지 빌드 통과. `./start-local.ps1` 반영: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8031`, 로그 `data/local-runtime/34500142a8d04c9ebaf429f20c9bf634/`. 수정 후 재조립/pytest/Playwright/실제 생성 테스트는 하지 않았다. 기존 이미지·3D·리깅으로 피팅·조립부터 실행할 수 있으며, 현재 저장된 shared-size-v1 결과를 수정 후 결과로 취급하지 않는다.

- 중간 단계 실행 구현: `GET /jobs/{id}/stages`에서 저장된 이미지/3D/리깅과 단계별 실행 가능 사유를 반환하고, `POST /jobs/{id}/stages/{images|models|rig|assemble}/resume`으로 시작 단계를 선택한다. 화면의 진행바 바로 아래에 4개 실행 버튼을 연결했다. 3D 시작은 이미지 생성·원본 재처리를 건너뛰고 기존 3D task ID/다운로드 결과를 재사용한다. 리깅 완료 시 조립으로 바로 이어가며, 피팅·조립 시작은 로컬 조립만 실행한다.
- 실행 요청은 S3 `stage-runs/`에 접수/진행/완료·중단 상태와 요청 식별자 해시를 보존한다. 프론트는 localStorage에 동일 idempotency key를 유지하며, 응답 유실 시 같은 요청으로 영수증만 복구한다. 진행 중 중복 실행 및 불확실한 제공자 요청 재제출을 막고, 재접속 후 저장된 단계에서 선택할 수 있다. 기존 이미지 재요청은 시작 단계를 images로 되돌려 3D 재개 설정이 새 이미지 처리를 건너뛰지 않게 했다.
- 단계 실행 서버 반영: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8030`, 로그 `data/local-runtime/3cb7f6cc1610463f964227328c6fc11d/`, API PID 31912. 프론트 타입/빌드, 백엔드 문법/패키지 빌드 통과. pytest·Playwright·실제 생성 테스트 및 에이전트 실행 POST 없음. 반영 후 읽기 전용 단계 조회에서 대상 `e2219a05f982f7324f7ccaf5`의 이미지 14/14·3D 7/7·리깅 저장과 조립 실행 요청 `7e0c5cc05b06021a7863dd08672e7885c5a4cc625ba66ba37c15f605fd57ecdc` running을 확인했다. 이 요청은 에이전트가 제출한 것이 아니며 완료 결과는 아직 확인 중이다.

- 공통 크기 자동 피팅 구현: 실제 저장 조립 `e2219a05f982f7324f7ccaf5` / `bb61cbcc194f42401aa1b62e`에서 상의 목표 높이 0.7056m, 신발 0.5456m를 확인했다. 이미지 bbox 측정값을 조립 치수로 쓰던 경로와 균일 배율 재계산을 제거했다. 규격 revision 3의 `fitting.bounds`에 몸 높이 1.2m와 6종 파츠의 XYZ 치수/위치를 고정하고, 축별 보정 행렬을 골격 바인딩에 직접 적용한다. 좌우 신발은 각각 고정 발 위치에 맞춘다. 현재 고정 치수는 상의 0.72×0.25×0.26m, 하의 0.36×0.17×0.28m, 신발 한 짝 0.13×0.13×0.22m(XYZ)다.
- 새 조립 recipe `native-parts-v3-shared-size`: 이전 단일/다중 시점 작업도 저장된 몸·3D 파츠를 재사용해 현재 피팅 규격으로 조립한다. 기존 이미지 영수증·원본·이전 조립 버전은 보존한다. 프롬프트/가이드도 같은 피팅 목표를 사용한다. 완료된 캐릭터 화면에 공통 규격 재피팅 버튼을 연결했다. 품질 검사/차단은 추가하지 않았다.
- 사용자 정정: 에셋을 대신 조작하는 작업이 아니라 프로그램 구현 요청이다. 외부 에셋 CLI/실제 조립·유료 생성은 실행하지 않았다. 프론트 `npm run build`, 백엔드 `uv run python -m compileall -q backend/src`, `uv build --package asset-3d-api` 통과. `./start-local.ps1` 적용 완료: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8029`, 로그 `data/local-runtime/f50aece653544edca121247abf08818b/`. FactoryReady=True, 기존 DB 연결 degraded. UI 프록시 GET에서 기존 조립 버전 보존과 `fit_update_available=true` 확인. pytest·Playwright·Blender 실행 없음; 실제 착용 모양/동작 품질은 미검증이다.

- 최신 사용자 지시: 공장의 규격·관통 검사 및 관련 테스트 제거. 몸/파츠 비율 허용치, 골격 앵커·표면 교차·동작 프레임 QC, 이미지 합격 판정, 최종 GLB 품질 게이트를 제거했다. 이미지 준비/공통 좌표/피팅/저장 파일 해시와 필수 산출물 확인은 유지한다. `test_avatar_image_intake.py` 삭제. 진행바는 공통 규격 → 정면·측면 → 3D 파츠 → 리깅·동작 → 피팅·조립 5단계로 변경했다. 이 변경을 검사 통과로 기록하지 않는다.
- 적용 완료: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8028`, 로그 `data/local-runtime/2cc3a0c805c545cea5434fcb4539f3e2/`. 프론트 타입/프로덕션 빌드 및 백엔드 문법/패키지 빌드 통과. pytest·Playwright·실제 생성·Blender 실행 없음.
- 현재 대상 `e2219a05f982f7324f7ccaf5`, 이전 조립 버전 `bd4669f2a67b3662dd5b7359`, 기존 qc_failed 기록 보존. 새 recipe는 `native-parts-v2-no-quality-gates`이고, 기존 이미지/3D 파츠를 재사용하는 조립 다시 하기 버튼을 연결했다. 제거한 검사 때문에 멈춘 구버전은 조립 재개 필요로 표시한다. 결과를 합격으로 바꾸거나 실패 기록을 삭제하지 않았으며 새 조립은 실행하지 않았다.
- 최신 적용 완료: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8027`, 로그 `data/local-runtime/5b1ed3de15c54b45a049a510f96cad51/`, API PID 27244. 프론트 타입/프로덕션 빌드, 백엔드 문법/패키지 빌드 통과. pytest·브라우저·실제 생성 POST는 하지 않았다. 저장된 실패는 그대로이며 화면의 몸 정면 재요청 작업은 enabled다.
- URL 오류 수정: 새 작업 `15c25171d5bdf9386743eeef`는 몸 정면 HTTP 400 / `invalid_value`, param `url`, 진단 `92f109940471`, 이미지 0/14. 실제 입력 S3 URL GET에서 글로벌 호스트가 서울 리전으로 307 이동한 뒤 403 `SignatureDoesNotMatch`가 발생했다. `object_storage.py`의 지역 엔드포인트 고정 및 WebP MIME 지정, URL 오류 분류를 수정했다. 수정한 실제 provider_image 함수의 JPEG/WebP URL 모두 리다이렉트 없이 HTTP 200, MIME 및 SHA-256 일치. 새 서버의 UI 프록시 GET에서 같은 작업의 오류/상태바가 reference_url 분류로 표시되고 retry_image(body/front)가 활성화된 것을 확인했다. OpenAI의 수정 후 생성 성공은 미검증이다.
- AWS CLI 저장 완료: 기존 작업 `dde03adae39977208b7ed79a/output/`의 실제 수신 PNG 10장을 공장 전용 S3 동일 작업 경로로 업로드했다. CLI head-object로 10/10 SHA-256 일치와 AES256 저장 확인. 새 작업 0/14와 별도이며 기존 로컬 파일은 보존했다.
- 최신 사용자 지시: 실제 생성 대행 중단. 코드 수정과 S3 생성/연결만 수행한다. 아래 과거의 실제 생성 재개 지시를 현재 실행 허가로 해석하지 않는다. 이 지시 이후 OpenAI/Meshy 생성 POST는 하지 않았다.
- 최종 적용 주소: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8026`, 로그 `data/local-runtime/56508039d1ce4fb4991c48ef578c6034/`. 완료 기록을 산출물 업로드 뒤에 저장하는 보완까지 백엔드 문법/패키지 빌드를 다시 통과하고 반영했다. 이전 생성 결과 `dde03adae39977208b7ed79a`는 10/14 수신, 측면 4장 응답 불확실로 보존한다. 추가 생성으로 검증하지 않는다.
- S3 생성 완료: `gaesup-character-assets-960243570517-apne2`, `ap-northeast-2`, 기존 활성 `mogaesup` 프로파일. 공장 전용 비공개 버킷이며 Public Access Block 4개, BucketOwnerEnforced, AES256 암호화, 버전 관리, 로컬 UI GET/HEAD CORS를 설정했다. 기존 월드 `AWS_S3_BUCKET`은 보존하고 `.env`의 `ASSET_S3_*`와 `ASSET_AWS_PROFILE`로 분리했다.
- 저장 코드: `object_storage.py`에서 공장/캐릭터/blueprint의 이미지·모델·원본·제공자 응답·JSON 영수증을 S3에 직접 저장한다. 입력은 내용 해시가 고정된 S3 오브젝트와 1시간 서명 URL을 OpenAI JSON edit API에 전달한다. 요청 접수 불확실 시 재전송 금지와 기존 입력 해시 비교는 유지한다. API 파일 응답은 소유권/해시 확인 후 15분 다운로드 URL로 전달한다. 기존 로컬 데이터는 읽기 호환으로 보존하며 일괄 이관/삭제는 하지 않았다.
- Blender는 실행 중에만 필요한 파일을 내려받고, 산출물과 증거를 먼저 S3에 업로드한 후 완료 기록을 저장하고 새 임시 파일을 제거한다. 업로드 실패 시 유일한 파일을 삭제하지 않는다. 제공자 응답/전송용 참조는 Blender 작업 공간에 내려받지 않는다. S3 오류를 로컬 저장으로 우회하지 않는다.
- 실행 반영: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8025`, 로그 `data/local-runtime/e7b0762a380b482584df10eae24a8cdd/`. 프론트 타입/프로덕션 빌드와 백엔드 문법/패키지 빌드 통과. pytest·브라우저·실제 생성·샘플 업로드 검사는 실행하지 않았다. 기존 DB health degraded는 유지한다. 완료 기록 업로드 순서 보완 후 최종 실행 주소는 다음 기록을 따른다.

- 22:07 KST 병렬 생성 적용: 몸 앞/옆을 고정한 뒤 나머지 6개 파츠를 ThreadPoolExecutor로 동시에 생성한다. 같은 파츠의 측면만 정면 완료에 의존한다. 파츠별 복사본 + 저장 잠금으로 상태/수락 한도 갱신을 직렬화하고, 일부 실패 시 나머지 파츠는 끝까지 수신한다. 복구/재요청 조건도 실제 참조 의존성으로 바꿨다. 진행률은 부분 실패 중에도 활성 작업을 진행 중으로 표시하며 동시 생성 수를 저장한다.
- 실행 중: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8024`, 로그 `data/local-runtime/3580287a3e4242d99719250515763296/`. 프론트 타입/빌드, 백엔드 문법/패키지 빌드 통과. pytest·브라우저 검사는 실행하지 않았다.
- 사용자 병렬 생성 요청에 따라 `dde03adae39977208b7ed79a`의 뒷머리 측면 실패 `f003c0dd5673`을 한 번 재요청해 HTTP 202 접수. 기존 3/14 보존, 수락 한도 19회(앞선 명시 재요청 포함). 6개 파츠 모두 새 `buffered-multipart-v4`로 본문 전송을 완료하고 동시 응답 대기 중이다. 상의는 전송 전 TLS 연결 실패 후 연결 재시도 성공, 본문 POST 재전송은 하지 않았다. 실제 수신 결과는 다음 기록에서 갱신한다.

- 최신 화면 대상은 `dde03adae39977208b7ed79a`다. 몸 앞/옆과 뒷머리 정면 3/14 수신 완료. 뒷머리 측면 약 1.5MB 요청은 응답 대기 중 TLS 연결 종료 또는 업로드 중 10054로 끊겼으며 최신 실패는 `f02cf817d0f3`. 앞선 약 0.92MB 요청은 수신 성공했다. 크기 제한이라는 확정 증거는 없으며 전송 방식 개선 후 실제 수신을 확인한다.
- 전송 수정: multipart 본문을 연결 전에 완전히 인코딩하고 고정 Content-Length의 단일 바이트 스트림으로 보낸다. 실제 본문 길이·SHA-256, 첫 실패 이벤트·TLS reason·본문 전송 완료 여부를 저장한다. 같은 영수증의 미확인 요청은 네트워크 계층에서도 재전송을 차단한다. 확실히 미전송인 연결 실패만 기존 client request ID/동일 본문으로 복구한다. 백엔드 문법·패키지 빌드 통과.

- 사용자의 "다음"에 따라 실제 생성 재개: 대상 `67c8f7875f3cb4c84cb1a1d0`, 뒷머리 정면 실패 `8511ee55ad26`를 같은 작업의 retry-image로 한 번 재요청한다. 새 요청은 measured-views-v4를 사용하며 이미 받은 몸 앞/옆은 보존한다. 이후 미완료 파츠는 기존 수락 범위에서 이어간다. POST 응답 유실 시 동일 작업/실패 ID 영수증부터 조회하며 별도 작업을 만들지 않는다.
- 재요청 실행 결과: 로컬 HTTP 202 접수, 이미지 수락 한도 15회. `hairBack-front-retry-8511ee55ad26-provider`에 v4 프롬프트가 저장됐으나 전송 0.062초에 Windows socket 10054 발생. 본문 전송 완료 이벤트·응답 헤더·제공자 request ID가 없고 현재 `submission_uncertain` / 실패 `7da1bad7bf15`로 보존했다. 몸 앞/옆 2/14는 그대로이며 Meshy 제출은 없다. 별도 유료 재요청은 더 보내지 않았다.
- 연결 진단: 같은 설정의 읽기 전용 모델 조회는 HTTP 200. 프록시 환경변수 없음. 같은 작업의 약 841KB 요청은 앞서 실제 이미지 수신, 약 844KB 요청은 실제 HTTP 거부 응답을 수신했으므로 이번 약 847KB 실패를 크기 제한·인증·안전 필터 문제로 단정할 수 없다. 현재 이미지 제공자 접수 여부가 불확실해 후속 파츠 생성은 중단 상태다. 프론트/API 주소는 5273/8022 유지.

- 최신 지시에서 빌드 검증 재개. 프론트 `npm run build`(tsc + Vite), 백엔드 `uv build --package asset-3d-api`(sdist + wheel), `uv run python -m compileall -q backend/src` 통과. 프론트 기존 대형 번들 경고는 남는다. pytest·브라우저·유료 생성은 별도로 실행하지 않았다.
- 요청 거부 실제 원인: `67c8f7875f3cb4c84cb1a1d0`의 뒷머리 정면, HTTP 400 / `moderation_blocked`, 진단 `8511ee55ad26`. 몸 정면·측면은 이미 수신됐다. 기존 영수증에는 세부 입력/출력 차단 단계가 없어 어느 내용이 원인인지 확정할 수 없다.
- 수정: 모든 HTTP 거부를 한 문구로 숨기던 처리를 안전 필터·인증/권한·사용 한도·요청 제한·모델·크기·형식·서버 오류로 분리. 기존 작업도 저장 영수증에서 표시를 복구한다. 이후 응답은 공개 moderation stage/category만 보존하고 제공자 원문·비밀값은 노출하지 않는다.
- 프롬프트 `measured-views-v4`: 공통 치수 조건은 유지하며 완전히 옷을 입은 게임 피규어와 독립된 인조 헤어/의상 부품이라는 목적을 명시. 새 몸의 기본 의상은 피부와 구분되는 청록색 불투명 긴팔·긴바지로 지정. 모델·필터 설정은 유지하고 기존 실패 요청을 자동 재전송하지 않는다. 실제 재생성 성공은 아직 확인하지 않았다.
- 최종 수정 후 프론트 타입 검사/프로덕션 빌드, 백엔드 문법/패키지 빌드 모두 다시 통과. 사용자 지시의 테스트 생략과 빌드 검증을 구분한다. UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8022`에 적용했다. UI 프록시에서 기존 작업 GET 결과가 HTTP 400 / policy / moderation_blocked와 새 오류 문구를 반환한다. 작업은 실제로 여전히 paused이고 재요청 버튼은 사용 가능하다. 실행 로그: `data/local-runtime/b6706a8b0e794b5397f331b4f2bf5744/`.

- 사용자 추가 지시: 테스트 없이 프롬프트 강화. `measured-views-v3`에 미터 좌표·원점·부착점, 공통 몸 비율, 앞/옆 카메라 고정, 파츠별 빈 내부 공간·겹침 금지·원본 실루엣 유지 조건을 명시했다. 앞머리/뒷머리 영역 분담, 모자의 헤어 외부 피팅, 옷의 목/손목/허리 개구부, 신발 쌍의 발목/바닥 위치를 각각 고정한다.
- 이미 시도한 이미지 요청은 기존 프롬프트 버전·가이드·입력 해시를 그대로 재사용한다. 새 요청·명시 재요청부터 v3를 저장하며, 프롬프트 강화 때문에 기존 응답 복구가 가이드 파일명 차이로 차단되지 않도록 연결했다. 테스트·빌드·브라우저·유료 생성은 실행하지 않는다.
- v3 서버 반영 완료: UI `http://127.0.0.1:5273/`, API `http://127.0.0.1:8021`. 표준 실행 스크립트 완료, `FactoryReady=True`. 아래 8020 실행 주소는 이전 기록이다. 로그: `data/local-runtime/bbbc570c36af4841ae9a3596ca42c6a1/`.

- 이번 재개에서 테스트·빌드·브라우저·유료 생성은 실행하지 않는다. 기존 사용자 변경, 삭제된 `.codex/`, 작업 데이터는 보존한다.
- 저장된 대상 `3ed7bb665d5fb298d5889aec`는 `pipeline_paused`: 몸 정면·측면 및 뒷머리 정면 수신 후 뒷머리 측면에서 응답 불확실. 새 요청이나 자동 재시도는 제출하지 않았다.
- 실행 하네스: 로드된 소스/규격 해시와 작업공간 ID를 `/health`에 고정한다. `start-local.ps1`은 같은 코드의 API만 재사용하며 이전 프로세스는 보존하고 빈 포트를 선택한다. `data/local-runtime/current.json`에 시작 즉시 주소·프로세스·로그·리비전을 기록하고 프록시 연결 후 ready로 바꾼다.
- 상태바: 중단 사유와 단계 상태를 함께 표시, 제공자 100%와 다운로드 완료를 구분, 전체 진행률에 3D 진행률 반영. 수신 수와 처리 완료 수를 구분하고 앞·옆 이미지 모두 노출한다. Pretendard/글래스모피즘 유지, 중복 설명·미사용 스타일/import를 정리했다. 기존 단일 뷰용 피팅은 과거 작업 호환 경로로 제한했다.
- 복구: 이미지 제출 키·입력을 localStorage에 유지해 탭 종료 후 같은 요청으로 복구한다. 저장된 제공자 응답은 키나 새 POST 없이 디코딩하며 멀티뷰 재개에 단일 뷰 영수증 조건을 적용하지 않는다.
- 출고 게이트: 피팅·표면 간격 보정 후 실제 전후좌우/상하 경계와 목·손목·발목 좌표를 공통 규격과 비교한다. 불일치 시 관통 검사·출고를 통과시키지 않는다. 기존 이미지 수신 우선 정책은 보존한다. 실제 3D·관통·동작 통과를 주장하지 않는다.
- 실행 적용 완료: UI `http://127.0.0.1:5273/`, 최종 API `http://127.0.0.1:8020`. 표준 스크립트에서 소스 리비전·프록시 대상 일치를 확인했다. `FactoryReady=True`, DB health는 기존 연결 불가로 `degraded`. 최종 실행 로그는 `data/local-runtime/a6099014030b4d42ae771492c63a71fa/`, 실행 영수증은 `data/local-runtime/current.json`. 앞선 API 8018/8019 등은 종료하지 않았다.
- 관통 검사가 먼저 통과해도 GLB 내보내기·산출물 봉인까지 완료되기 전에는 전체 진행률을 100%로 표시하지 않는다. 내보내기 실패는 피팅 단계 중단으로 남긴다.
- 남은 미검증 범위: 새 변경의 pytest·프론트 빌드·Playwright, 실제 제공자 수신 및 공통 규격/관통/동작 통과. 사용자가 확인을 재개하도록 지시하기 전에는 실행하지 않는다. 현재 응답 불확실 작업은 보존했고 새 유료 호출은 없다.

- 사용자의 "처음부터 프롬프트를 똑바로 하고 요청해"에 따라 실제 재요청 실행. 대상 `3ed7bb665d5fb298d5889aec`, measured-views-v2가 첫 요청부터 저장되어 있음. 첫 재요청은 JSON 1,813,986 bytes 전송 단계에서 0.063초 ReadError. 업로드를 문서에 있는 multipart image[]로 전환하고 외형 전용 원본 참조만 1024px로 제한, 규격 가이드와 확정 시점은 해상도 유지/무손실 WebP로 전송하도록 수정했다.
- 표준 실행 스크립트로 API 8016 적용. 두 번째 재요청은 본문 121,425 bytes 전송 완료 이벤트를 남기고 응답 대기 중이다. 현재 failure ID 1aa828fded4b를 이용한 재요청 영수증은 body-front-retry-1aa828fded4b-provider. 이전 응답 불확실 시도는 모두 보존했고 수락 이미지 한도는 16회(최초14 + 명시 재요청2)다. 임의 무한 재요청은 하지 않는다. 스크립트 기본 실행은 마지막 LOCAL_BACKEND_URL 포트를 유지한다.

- 실행 적용 완료: 사용자가 다시 올린 `a86b7af32159fb2c826bbd49` 및 `fae5481c06f390eafd8b0204`도 PID 532/8014의 이전 코드로 처리되어 0.078/0.062초 ReadError. 이번에는 표준 `./start-local.ps1` 실행이 승인되어 8015 API가 시작됐고 5273 프록시가 새 API로 연결됐다. 스크립트의 로컬 연결 확인은 성공, FactoryReady=True. PostgreSQL 연결은 degraded지만 공장 준비 상태는 True다.
- 실제 UI 프록시에서 최신 작업을 한 번 조회: 오류가 새 문구로 변환되고 next_actions에 body/front retry_image 활성화, 실패 ID df3fe5292cec, 이미지 0/14가 반환됐다. 소스만 반영됐던 앞선 제한은 해소됐다. 현재 작업은 응답 미수신으로 여전히 paused이며 유료 재요청은 실행하지 않았다. 테스트/빌드/브라우저/전체 파이프라인 검증은 실행하지 않았다.

- 새 규격 실패 `07f8e01864ed019e52665ffd`: body/front 수신 PNG의 실제 경계 `[487,69,1562,1985]`, 기준 머리선/발바닥 `300/1800px`, 실패 항목 outside_slot_envelope/body_height_mismatch. 이미지에는 과도한 프레이밍과 외곽 광륜이 보인다.
- 프롬프트 수정: `avatar_image_prompts.py`의 measured-views-v2로 교체. 기존 body_prompt/_part_prompt를 멀티뷰에 덧붙이지 않는다. 시점별 카메라, 픽셀 원점·축, 관절 좌표, 머리 높이, 파츠 허용 경계를 동일 production_spec에서 계산한다. 원본은 외형만, 가이드는 배치와 비율만 담당한다. 측면에 Front A-pose 문구가 남던 문제 제거. 가이드에 기준선과 파츠 경계 표시, 출력에는 그림자/광륜/가이드 표시 금지. 직전 QC 실측값을 재요청에 포함하고 정확한 프롬프트/참조 순서/해시를 POST 전에 보존한다. API 캔버스 크기도 같은 규격에서 전달한다.
- 기존 QC 실패 영수증도 결정적 실패 ID를 얻고 해당 이미지 재요청이 가능하도록 수정했다. 응답이 저장됐다는 이유만으로 규격 실패 재요청을 차단하던 오류도 수정. 기존 수신 이미지와 provider 응답은 보존했다. 검사 허용치를 완화하지 않았고 테스트·생성·서버 재시작은 실행하지 않았다. 앞서 API 실행이 정책에 차단된 상태이므로 실행 서버 반영은 확인되지 않았다.

- 추가 장애 `e5da67dd12980aa6dc6e68cd`: body/front 첫 요청에서 0.063초 후 ReadError, 응답 헤더/본문 없음. 제한시간 초과가 아니며 기존 기록만으로 원격 접수 여부를 확정할 수 없다. 이전 작은 요청에서도 같은 유형이 있어 이미지 크기를 원인으로 단정하지 않는다.
- 추가 수정: 전송 단계별 영수증, 연결 수립 실패에만 제한된 재시도, 생성 응답 대기 시간 분리. 시점별 재요청 API/UI는 실패 ID로 중복 접수를 막고 이전 영수증과 완료된 이미지를 보존한다. 수신 개수는 14장 기준, 연결 오류·요청 거부·규격 불일치 구분. 기존 유료 요청은 재제출하지 않았다.
- 새 API 8015 시작과 프록시 전달을 시도했으나 자동 실행 정책이 명령 전체를 `blocked by policy`로 거부했다. 새 프로세스는 시작되지 않았고 `.env.local`은 기존 8014를 유지한다. 이번 오류 처리/재요청 수정은 소스에만 반영됐으며 실행 적용은 미완료다. `start-local.ps1`은 다음 실행에 8015를 사용하고 선택한 포트를 LOCAL_BACKEND_URL에 기록한다. 요청대로 테스트/빌드/브라우저 검증은 실행하지 않았다.

- UI `http://127.0.0.1:5273/`, 새 API `http://127.0.0.1:8014`. 기존 8013 종료는 실행 정책에 차단되어 보존했다. `.env.local`의 `LOCAL_BACKEND_URL`로 기존 Vite도 새 API를 사용하도록 적용했다. 5275에도 기존 UI가 있으므로 임의 종료하지 않는다.
- 기존 사용자 변경과 `.codex/` 삭제를 보존한다.
- 실제 `5fc6a2db78b275402d86846c`: 이미지 6/7 수신, bottom은 ReadError로 submission_uncertain. Meshy 제출 없음. 새 유료 요청으로 덮어쓰지 않는다.
- 실제 `abdcfb58ae6d3e7cba03d659`: 파츠 7/7, 조립 완료 기록. `c6251dc143b9cb7628e94432`는 조립 결과가 있으나 상위 진행 문구는 리깅 중으로 남아 있음.
- 확인된 수정 대상: 제한 시간 없는 fetch, 오래된 진행 문구, 숨겨진 파츠 상태, 응답 유실 복구가 최신 blueprint 조회에 의존하는 흐름.
- 구현: 요청 제한시간·취소, 중복 없는 폴링·재접속, 파츠 수신 현황, 저장된 영수증 기반 character_flow. 관련 기존 pytest 38개 및 프론트 빌드 통과. 새 회귀 검사는 추가 중.
- 사용자 추가 요구: 사진을 두 장 업로드하는 기능이 아니라 원본에서 앞·옆을 생성한다. 전후좌우·크기 공통 규격, 관통 통과 조건, 반복 생산 파이프라인을 구현한다. Pretendard+글래스모피즘, 불필요한 문구 삭제.
- 실제 시각 문제: 기존 자동 피팅은 가로폭의 고정 배율만 사용. 원본보다 몸·다리가 길며 헤어가 두피와 관통한다. 움직임 검증을 외형 통과로 취급하지 않는다.
- 추가 구현: production-v1 공통 규격, 정면·측면 영수증과 이미지 QC, Meshy multi-image 연결, 규격 실측 피팅·관통 게이트, 여섯 단계 실상태 진행률, Pretendard 로컬 폰트와 공통 글래스모피즘 UI.
- 사용자 지시에 따라 이후 테스트·브라우저·provider 검증을 중단했다. 새 구현은 실행 검증 미완료이며 실제 유료 생성도 아직 제출하지 않았다. 마지막으로 실행한 검증은 위에 기록한 변경 이전의 38개 테스트와 빌드다.
