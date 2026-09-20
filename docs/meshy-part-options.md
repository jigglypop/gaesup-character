# Meshy 7.1 파츠 생성 설정

상의·하의·헤어·모자/장식·신발·무기·도구·안경의 생성 화면에서 `Meshy 7.1 설정`을 펼친다. 설정은 파츠 종류별로 브라우저에 저장된다. 사진 전체 생성은 해당 화면의 공통 설정을 새로 생성하는 파츠에 적용한다. 접수한 작업의 설정과 프롬프트는 고정하며, 재개할 때 현재 초안으로 바꾸지 않는다.

2026-09-20 [Meshy Multi-Image to 3D 공식 문서](https://docs.meshy.ai/en/api/multi-image-to-3d)를 기준으로 구현했다. 입력 원화는 기존 정면·측면·후면 파이프라인을 유지한다.

| 화면 입력 | API 필드 | 선택 범위 / 새 요청 기본값 |
|---|---|---|
| 모델 | `ai_model` | `meshy-7.1` 고정 |
| 형상 해상도 | `geometry_resolution` | `standard`, `2k` / Ultra 2K |
| 자세 | `pose_mode` | 원본, T, A / 원본 |
| 리메시 | `should_remesh` | 켬·끔 / 끔 |
| 면 구성 | `topology` | triangle, quad / triangle |
| 목표 폴리곤 | `target_polycount` | 100~300,000 정수 / 30,000; 실제 결과 수는 달라질 수 있음 |
| 자동 폴리곤 | `decimation_mode` | 직접 입력 또는 1 Ultra, 2 High, 3 Medium, 4 Low / 직접 입력 |
| 리메시 전 GLB 저장 | `save_pre_remeshed_model` | 켬·끔 / 끔 |
| 텍스처 생성 | `should_texture` | 켬·끔 / 켬 |
| 텍스처 해상도 | `texture_resolution` | 2K, 4K, 8K / 4K |
| PBR 맵 | `enable_pbr` | 켬·끔 / 켬 |
| 텍스처 명암 제거 | `remove_lighting` | 켬·끔 / 켬 |
| 텍스처 기준 | `texture_mode` (앱 입력) | 원화, 관리 프롬프트, 이미지 1장, 이미지 1~4장 / 원화 |
| 관리 프롬프트 | `texture_prompt` | 프롬프트 관리 → 3D 텍스처 → 파츠별 문장, 1~800자 |
| 텍스처 참조 | `texture_image_url` 또는 `texture_image_urls` | PNG/JPEG 업로드; 첫 장 정면, 최대 4장; 파일당 32MiB·3,200만 픽셀 이하 |
| 입력 이미지 자동 보정 | `image_enhancement` | 켬·끔 / 끔 |
| 입력 콘텐츠 검사 | `moderation` | 켬·끔 / 끔 |
| AI 크기 추정 | `auto_size` | 켬·끔 / 끔 |
| 원점 | `origin_at` | bottom, center / bottom |
| 출력 형식 | `target_formats` | GLB 필수 + OBJ, FBX, STL, USDZ, 3MF 선택 / GLB |
| 투명 배경 미리보기 | `alpha_thumbnail` | 켬·끔 / 끔 |
| 앞·오른쪽·뒤·왼쪽 미리보기 | `multi_view_thumbnails` | 켬·끔 / 끔 |

리메시를 꺼두면 면 구성·목표 수·자동 단계·리메시 전 저장을 전송하지 않는다. 자동 단계 선택 시 목표 수를 전송하지 않는다. 텍스처를 끄면 텍스처 전용 옵션과 참조를 전송하지 않는다. 프롬프트·단일 참조·다중 참조는 동시에 전송하지 않는다. AI 크기 추정을 켰을 때만 원점을 전송한다. 크기·원점은 생성 원본에 적용되며 착용용 결과는 기존 공통 몸 좌표에 피팅한다.

새 설정을 접수한 파츠는 후처리에서 기존의 파츠 면 수 제한·512px 텍스처 축소를 적용하지 않는다. 의상 피팅·골격 연결은 유지된다. Meshy 자체 리메시나 피팅으로 실제 면 수는 달라질 수 있다.

추가 출력은 S3에 저장하고 파츠 결과에 다운로드 링크를 표시한다. 기본 GLB와 추가 파일의 저장 영수증을 별도로 보존하므로 다운로드 재개 시 저장된 결과를 재사용한다. 만료된 출력 URL은 기존 작업 ID의 GET으로 갱신한다. 새 유료 생성 POST를 만들지 않는다.

## 현재 경계

- 다중 이미지 API는 형상 해상도 4K를 지원하지 않아 Standard/Ultra 2K만 제공한다. 텍스처 4K/8K와는 별개다.
- `image_urls`는 파이프라인이 준비한 뷰로 구성한다. 대체 입력인 Meshy 이미지 생성 작업 `input_task_id` 지정이나 임의 URL 입력은 이 화면에 포함하지 않았다.
- 폐기된 `ultra_mode`, `hd_texture`, `is_a_t_pose`는 각각 현대 필드로 제공한다. 출력에 영향을 주지 않는 `symmetry_mode`는 추가하지 않았다.
- 독립 Remesh/Retexture/Rigging API 전체 편집 및 기본몸 이미지 업로드 화면의 옵션 편집은 이 파츠 설정 범위에 포함하지 않는다. GLB 바로 등록/새 리깅 경로는 유지한다.
- 검증은 프론트 빌드, 백엔드 문법·패키지 빌드, 실행 API 조회와 수동 브라우저 화면 확인이다. 실제 유료 생성·추가 형식 다운로드·Blender 실행 검사는 수행하지 않았다.

API: `GET /api/avatar-factory/meshy-options`에서 기본값·입력 스키마를 조회한다. 이미지 참조는 `POST /api/avatar-factory/meshy-options/texture-assets`로 업로드한 소유자 에셋 ID를 `texture_image_assets`에 전달한다. 생성 입력 `meshy_options`는 `/variants/single-part`, `/variants`, 다중 이미지 `/image-jobs`에서 받는다.
