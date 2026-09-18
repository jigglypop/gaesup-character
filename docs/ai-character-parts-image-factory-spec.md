# AI 캐릭터 파츠 이미지 공장 명세 v1

상태: 구현 기준 명세. 작성일: 2026-09-18. PNG 생산과 검수 계약을 정의하며, 아래 기능 전체가 구현되었다는 뜻은 아니다. 현재 코드와의 차이는 §14에 기록한다.

제품의 최종 목표는 **사진에서 만든 파츠를 조합한 캐릭터 전체가 함께 움직이는 것**이다. 이 이미지 명세는 중간 단계이며 몸의 A-pose나 PNG 출력만으로 제품 완료를 판정하지 않는다. 현재 단일 화면과 자동 조립 연결은 [사진 → 캐릭터 실행 계약](photo-character-flow.md)을 따른다.

## 1. 목적과 완료 경계

캐릭터 레퍼런스 한 장에서 디자인을 분석하고, 승인한 기준 몸의 좌표계에 맞는 독립 파츠 PNG 세트를 생산한다. 원본에서 가려진 두피·옷의 뒷면·헤어 안쪽도 재구성한다. 원본 시트를 잘라낸 이미지와 신규 파츠 생성물을 구별한다.

입력은 레퍼런스, 몸 프로필, 생산할 파츠와 시점이다. 출력은 고정된 blueprint, 기준 몸 렌더, 파츠별 canonical canvas·tight crop·provider 이미지, 좌표 변환, QC 보고서와 패키지 manifest다.

이 명세의 완료 조건은 **같은 몸에 착용할 위치가 보존되고, 검수를 통과한 이미지 패키지**다. Meshy 형상 생성, 3D 피팅, 스키닝과 런타임 교체는 이후 단계다. 이미지의 정렬 통과만으로 3D 착용·변형 성공을 표시하지 않는다.

```text
레퍼런스 → 디자인 blueprint → 기준 몸 준비·승인 → 고정 렌더·앵커
                                                ↓
           파츠 재생성 → 배경 제거 → 정렬 → crop → QC → 이미지 패키지
                                                        ↓
                                              별도 Meshy 작업 → 3D 피팅
```

## 2. 첨부 레퍼런스의 생산 범위

기본 캐릭터는 갈색 웨이브 포니테일, 붉은 리본, 적갈색 눈, 크림색 카디건, 붉은 체크 치마, 흰 양말, 갈색 메리제인, 토끼 장식 가방으로 해석한다. 표정과 착용 위치는 동일한 캐릭터에 귀속한다.

| 레퍼런스 요소 | 기본 생산 항목 | 분리 원칙 |
|---|---|---|
| 머리와 몸 | `body` | 완전한 대머리 두피·귀·손·발, 중립 표정과 불투명한 단색 기본복 |
| 눈·눈썹·입·볼 | `face` | 같은 머리의 표정 텍스처 8종 |
| 앞머리·옆머리 / 뒤통수 / 포니테일 | `hair.front` / `hair.back` / `hair.extension` | 세 물체, 같은 두피 기준 |
| 큰 리본·하트핀·X핀 | `accessory.hair`의 개별 item | 헤어에 합치지 않고 부착 위치 기록 |
| 카디건 / 목 리본 | `clothes.top` / `accessory.neck` | 교체 가능한 리본을 상의 출력에 중복 생성하지 않음 |
| 체크 치마 | `clothes.bottom` | 허리와 안감을 완성, 다리 제외 |
| 양말·메리제인 | `feet.left` / `feet.right` | v1은 같은 쪽 양말과 신발을 한 제작 단위로 취급, 피부·종아리 제외 |
| 가방 / 토끼 키링 | `accessory.bag`의 별도 item | 키링은 가방 item의 socket에 연결 |
| 야구모자·비행모·토끼모자·꽃관 | `head.hat`의 선택 variant | 한 번에 하나를 착용, 기본 생산에는 미선택 |
| 지팡이 | `accessory.hand`의 선택 item | 손 없이 완성된 소품, 기본 생산에는 미선택 |

시트에 있는 여분 장식과 모자를 모두 기본 복장으로 해석하지 않는다. 옆·뒤 모습이 실제로 보이는 항목은 `observed`, 가려진 구조에 관한 설계는 `inferred`로 blueprint에 구별한다. 표정·시점별 반복 그림은 새로운 상품으로 세지 않는다.

## 3. 몸·캔버스·카메라 계약

| 항목 | v1 값 |
|---|---|
| 제작 이미지 | 2048 × 2048 PNG, 8-bit RGBA, sRGB, straight alpha |
| 이미지 좌표 | 원점 좌상단, x 오른쪽 증가, y 아래쪽 증가, 픽셀 경계 좌표 |
| 몸의 중심 / 대머리 정수리 / 발바닥 | x=1024 / y=300 / y=1800 |
| 정수리~발바닥 | 1500px = 1.20m, 1250px/m |
| 카메라 | 정사영, 세 시점 동일 배율·높이·몸 원점 |
| 정사영 세로 범위 | 1.6384m = 2048 / 1250 |
| 기본 외형 | premium 3D chibi, 큰 머리·짧은 팔다리·단순화한 손 |
| 등신 목표 | 약 1.6등신; 실제 승인한 몸의 치수를 프로필에 기록 |
| 자세 | 중립 A-pose, 상완이 몸의 아래 방향 수직축에서 30–35° 벌어짐 |

등신 목표는 첨부 이미지에서 정밀 측정한 값이 아니다. 외형과 손·발 분리 상태를 확인해 몸 프로필을 승인하고, 이후 모델이 비율을 다시 결정하지 못하게 한다. 머리카락·모자·소품의 높이를 몸 높이 측정에 포함하지 않는다.

몸은 완전한 두피, 귀, 얼굴, 목, 어깨, 팔, 손, 골반, 다리, 발을 가진다. 기본복은 목~손목, 몸통~발목을 덮는 얇고 불투명한 단색 fitted bodysuit다. 양손과 몸통, 양다리 사이에 간격이 있고, 발은 바닥에 평평하게 놓이며 머리는 기울이지 않는다.

### 시점과 좌우

기준 공간은 glTF의 X 오른쪽, Y 위, Z 정면을 사용한다. 캐릭터의 해부학적 왼쪽은 +X, 오른쪽은 -X로 고정한다. `left`/`right`는 화면의 좌우가 아니다.

| 저장 시점 | 카메라 위치 | 의미 |
|---|---|---|
| `front` | 몸의 +Z | 얼굴 정면, 캐릭터 왼쪽이 화면 오른쪽 |
| `side` | 몸의 +X | 캐릭터의 왼쪽 측면, 코가 화면 왼쪽 |
| `back` | 몸의 -Z | 뒤통수와 등, 캐릭터 왼쪽이 화면 왼쪽 |

세 카메라 모두 +Y를 화면 위로 사용하고 동일한 몸 중심을 본다. 런타임에 반대쪽 측면이 필요하면 별도 버전 계약으로 추가하며 `side`의 의미를 바꾸지 않는다. 비대칭 리본·가방·신발은 시점을 바꿀 때 거울 복제하지 않는다.

### 기준 몸의 고정

`bodyProfileId`, 프로필 revision·해시, 몸 artifact 해시, pose·카메라·앵커 세트 해시와 승인 기록을 함께 고정한다. 3D 기준 몸이 있으면 승인한 동일 메시·자세에서 세 시점과 랜드마크를 투영한다. 새 몸이 필요하면 먼저 후보를 제작·승인하고 이 템플릿을 확정한다.

이미지만 있고 투영 가능한 기준 몸이 없으면 `body_review_required`다. 임의로 찍은 좌표를 몸에서 계산한 앵커라고 기록하지 않는다. 몸 또는 카메라가 바뀌면 새 프로필 revision을 만들고 종전 파츠의 QC를 새 몸에 재사용하지 않는다.

## 4. Blueprint: 모든 생성의 설계 원본

분석 단계는 reference hash, 몸 프로필, 색상·재질, 파츠 목록, 부착 관계, 디자인 근거와 추론을 구조화한다. 이미지를 매번 새롭게 해석하는 대신 같은 blueprint revision을 사용한다.

필수 필드:

- `schemaVersion`, `characterId`, `revision`, `reference.sha256`, `bodyProfile`과 기준 몸 해시.
- `parts[]`: `itemId`, canonical `slot`, `design`, `views`, `selected`, `evidence`, `attachment`, `occupies`.
- `face`: 표정 목록, 고정 head·UV template 식별자와 revision.
- `generation`: provider, 모델, prompt template revision, 선택 항목과 호출 상한.
- `review`: 대상 해시, 상태, 검수자·시각, 수정 사유. 초안의 누락 해시는 `null`이며 생산 수락 시 필수다.

첨부 그림을 읽어 작성한 [blueprint 예시](examples/modular-image-factory/blueprint.example.json)는 설계 예제다. 자동 분석 또는 실제 생성 완료의 영수증이 아니다. 원본 파일 해시, 기준 몸과 UV 해시를 연결하기 전에는 실행 입력으로 수락하지 않는다.

분석 내용이 바뀌면 새 revision을 만들고 영향받는 항목의 생성·검수 결과를 무효화한다. 전혀 다른 캐릭터를 만들지 않도록 공통 눈 색·헤어 색·직물 패턴은 blueprint에서 참조한다.

## 5. 제작 슬롯과 기존 런타임 변환

Canonical slot은 점으로 구분한 문자열이다. `itemId`는 개별 물체 식별자다. 같은 슬롯에 여러 상품과 부착물이 존재할 수 있다.

| 제작 슬롯 | 기존 이미지 명칭 | 기존 표준 옷장 대상으로의 변환 |
|---|---|---|
| `body` | `body` | 기준 몸, 교체 의상 슬롯 아님 |
| `face` | `face` | 같은 head의 재질·UV 경로, 별도 머리 생성 금지 |
| `hair.front` | `hairFront` | `hair` 호환 그룹의 구성 요소 |
| `hair.back` | `hairBack` | `hair` 호환 그룹의 구성 요소 |
| `hair.extension` | `hair_tail` alias | `hair` 호환 그룹의 구성 요소 |
| `head.hat` | `hat` | `hat` |
| `clothes.top` / `clothes.bottom` | `top` / `bottom` | `top` / `bottom` |
| `clothes.onepiece` | 신규 | 상·하의를 함께 점유; 기존 옷장 직접 지원 없음 |
| `feet.left` / `feet.right` | `shoes`의 쌍 구성원 | `shoeLeft` / `shoeRight` |
| `accessory.hair` / `.face` / `.neck` / `.back` / `.hand` / `.bag` | 신규 세분화 | `accessory` 대상 후보; 복수 장착과 socket 계약 필요 |

`hair_tail`, `hair_extension`은 입력에서 `hair.extension`으로 정규화하며 출력에는 canonical 명칭만 저장한다. 통합 `hair`·`shoes`를 이름만 바꾸어 분리된 것으로 표시하지 않는다.

기존 런타임 어댑터가 합쳐진 hair를 요구하면 명시적인 그룹 변환으로 전달하고 원래 item 목록을 보존한다. `onepiece`나 복수 액세서리를 지원하지 않는 어댑터는 `unsupported_mapping`으로 멈춘다. 슬롯을 몰래 합치거나 일부를 버리지 않는다.

리본·키링은 `attachment.parentItemId`와 socket으로 소속을 지정한다. onepiece는 `occupies=[clothes.top, clothes.bottom]`이며 이 둘과 동시 착용하지 않는다. 양말과 신발의 독립 교체는 후속 슬롯 확장 범위다.

## 6. 파츠 이미지 생성 계약

각 `(itemId, view)` 생성은 다음 입력을 고정한다.

1. 해당 시점의 기준 몸 렌더와 카메라·앵커 정보.
2. 원본 레퍼런스와 해시.
3. blueprint의 공통 디자인 및 해당 item 설계.
4. 같은 item의 승인된 이전 시점 이미지가 있으면 그 이미지와 해시.
5. 생성 모델·provider 설정·prompt template revision.

새 공장 파츠의 기본 모델은 저장소 지침대로 `gpt-image-2.5-sunburst`다. 모델 접근 가능 여부와 실제 출력 해상도는 실행 시 확인하고 요청값·응답값을 각각 기록한다. 실패 시 다른 모델로 자동 대체하지 않는다.

정면으로 디자인을 고정하고 측면·후면을 같은 revision에서 만든다. 한 이미지에 물체 여러 개나 턴어라운드 시트를 요청하지 않는다. 같은 몸의 위치와 배율에서 **해당 파츠만** 출력한다. 의상 속 피부·손·발·머리, 바닥 그림자, 글자, 프레임, 자는 출력하지 않는다. 전체 캐릭터를 다시 생성해서 잘라내는 방식은 파츠 생산의 대체 경로가 아니다.

상의 프롬프트 템플릿:

```text
Input A is the locked canonical body render for {view}; use it only as a fitting guide.
Input B is the original character design reference.
Reconstruct only item {itemId} from blueprint revision {revision}.
Preserve its design, colors, seams and attachment openings, completing occluded geometry.
Keep its worn position and scale relative to Input A. Do not center or enlarge the garment.
Keep sleeves in the canonical A-pose. Output one isolated garment on transparent background.
Exclude the body, skin, head, hands, other garments, detachable accessories, text and shadows.
The detachable neck bow belongs to a separate item and must not appear in this garment.
```

프롬프트는 품질 보증이 아니다. 다른 크기로 응답한 이미지는 전체 캔버스를 기준으로 동일 배율 확대·축소와 투명 여백만 허용하고 원본→canvas 변환을 기록한다. 물체 bbox를 몸 크기로 강제 확대하거나 축별로 늘리지 않는다. 정규화 후 §9 검수를 반드시 수행한다.

## 7. 얼굴과 헤어의 특별 규칙

표정은 `neutral`, `smile`, `happy`, `wink_left`, `wink_right`, `sad`, `angry`, `surprised` 8종이다. wink의 좌우도 캐릭터 기준이다.

얼굴은 같은 head mesh·UV를 사용한다. 생성한 2D 얼굴 그림은 곧바로 UV 텍스처가 아니다. 고정된 face projection mask와 UV template을 사용해 매핑하고, 같은 머리에 입힌 렌더로 눈·입 위치와 경계를 검수한다. `face/<expression>.canvas.png`와 `face/<expression>.uv.png`를 구별하고 mask·UV 해시를 기록한다. 템플릿이 없으면 `face_mapping_required`로 남긴다.

얼굴 canvas는 2048px 제작 규격을 따른다. v1 UV 출력은 1024 × 1024 RGBA PNG·sRGB로 고정하며, 얼굴 overlay용 alpha와 UV island 여백은 승인한 템플릿의 mask를 따른다. 다른 UV 레이아웃·해상도는 템플릿 새 revision으로 관리한다.

얼굴의 front/side/back 완성 이미지나 새 머리 Meshy 작업을 표정마다 생성하지 않는다. 얼굴 QC가 승인된 결과만 `ready_for_texture`이며 Meshy 입력에는 포함하지 않는다. morph target은 v1 이후 범위다.

헤어 세 파츠는 두피와의 접합 범위를 공유하되 얼굴·두피 픽셀을 포함하지 않는다. 포니테일 연결부와 nape의 가려진 형상을 완성하고 리본은 독립 item으로 만든다. 단단한 헤어 파츠의 부착과 포니테일 보조 본은 이후 3D 계약에서 다룬다.

## 8. 앵커 계약

**목표 앵커는 기준 몸에서 계산한다. 생성 이미지에서 관찰한 앵커는 별도로 측정한다.** 둘을 같은 값으로 복사해 오차 0을 만들지 않는다.

| 종류 | 의미상 목표 앵커 |
|---|---|
| top | neck_center, shoulder_left/right, wrist_left/right, waist_center |
| bottom | waist_left/right, hip_center, crotch, ankle_left/right |
| hair | crown, forehead_center, temple_left/right, nape |
| hat | crown, temple_left/right, forehead_center |
| feet | 해당 쪽 ankle, heel, toe |
| accessory | 부모 몸 또는 item에서 정의한 socket과 방향 기준점 |

프로필은 각 view·garment type에서 실제로 비교 가능한 앵커와 목표 offset을 정의한다. 치마의 발목, 정면 신발의 가려진 뒤꿈치처럼 존재하지 않는 관찰점을 필수 입력으로 강제하지 않는다. 의상 두께와 여유분은 프로필의 offset에 포함한다.

관찰값에는 `method`(검수자 측정 또는 검출기), confidence, `visible`, 원본 해시를 저장한다. 앵커 누락·저신뢰·관찰 불가능 상태는 `unknown`으로 남기며 자동 통과시키지 않는다.

측정 가능한 독립 앵커가 3개 이상이고 분포가 충분한 경우 이동·회전·등방 배율의 similarity 정렬을 허용한다. 퇴화된 배치, 반사, 축별 비균등 확대, 자유 워핑은 자동 정렬에서 제외한다. 앵커가 부족한 소품은 별도 socket 템플릿·overlay 검수로 승인한다.

오차는 canonical canvas에서 앵커별 유클리드 거리의 **최댓값**이다. 정렬 전 오차와 정렬 후 잔차를 모두 보존한다.

| 최초 최대 오차 | 처리 |
|---|---|
| ≤ 8px | 기하 통과 후보; 나머지 QC가 필요 |
| 8px 초과, 20px 이하 | 한 번 similarity 정렬 후 재측정·overlay 검수; 최종 ≤ 8px 필요 |
| > 20px | `regeneration_required`, Meshy 전달 금지 |
| 측정 없음·신뢰 부족 | `review_required`, 자동 통과 금지 |

최종 잔차가 8px를 초과하거나 정렬 때문에 파츠가 잘리면 실패다. target 앵커를 옷에 맞춰 움직여서는 안 된다. 현재 코드의 `max_error_px`는 정렬 후 잔차 제한이므로, 위의 정렬 전 분기와 같은 검사라고 간주하지 않는다.

## 9. 배경 제거·Crop·좌표 복원

원본 provider 응답과 원본 PNG를 보존한다. 투명 출력이면 alpha를 검증하고, 불투명 배경이면 배경 제거 결과·도구 버전·입출력 해시를 별도 기록한다. 흰 옷이나 옅은 머리 끝을 배경색과 같다는 이유만으로 지우지 않는다.

각 view는 세 이미지를 저장한다.

- `{view}.canvas.png`: 2048 × 2048, 착용 위치 보존. 이 파일을 tight crop으로 덮어쓰지 않는다.
- `{view}.crop.png`: alpha bbox에 여백을 둔 1024 × 1024 정사각 이미지, 개별 확인용.
- `{view}.provider.png`: 1024 × 1024, 다중 시점 간 동일 배율을 유지한 Meshy 입력.

### 정확한 crop 계산

alpha가 8을 초과하는 픽셀의 bbox를 `[x, y, width, height]`로 구한다. 오른쪽·아래 경계는 exclusive다. 원본의 부드러운 alpha는 유지하며 bbox 계산을 위해 이진화한 마스크로 원본 alpha를 덮어쓰지 않는다.

각 view에서 `m=max(width,height)`, `paddingPx=ceil(0.10*m)`, `L=m+2*paddingPx`다. padding은 각 변에 적용한다. 정사각형 원점은 `x0=x-floor((L-width)/2)`, `y0=y-floor((L-height)/2)`다. 캔버스 밖 여백은 투명하게 채우며 물체를 잘라내지 않는다.

crop 파일은 이 정사각형을 1024px로 리샘플링한다. provider 파일은 **같은 item의 모든 시점에서 가장 큰 L**을 공통 한 변으로 사용하고 각 bbox 중심에 배치한다. 시점마다 물체를 제각각 확대하지 않는다. 두 파일은 같을 수도 있지만 변환을 각각 기록한다.

좌표 변환은 픽셀 경계 기준으로 다음과 같다. provider 정사각형의 원점·한 변을 `x0,y0,Lp`라고 할 때:

```text
s = 1024 / Lp
provider_x = (canvas_x - x0) * s
provider_y = (canvas_y - y0) * s
canvas_x = provider_x / s + x0
canvas_y = provider_y / s + y0
```

manifest에는 alpha bbox, padding 비율·픽셀, square 원점·크기, 출력 크기, 정·역행렬과 각 이미지 해시를 저장한다. 예를 들어 bbox `[612,655,824,621]`은 padding=83, L=990, 원점 `(529,471)`이다. 다른 시점이 더 큰 L을 요구하지 않을 때 `s=1024/990`이다. 행렬 왕복 오차는 0.5 canonical px 이하로 확인한다.

투명 배경을 받지 않는 provider 어댑터는 별도 합성본과 배경색을 기록한다. Meshy 이미지가 완전히 중앙 crop이어도 canvas 원본은 보존한다. 복원 메타데이터는 2D 위치·배율의 근거이며, Meshy가 만든 깊이·원점·물체 크기는 실제 3D 측정과 피팅으로 다시 확인해야 한다.

## 10. QC와 전달 차단

각 검사는 `pass`, `fail`, `unknown` 중 하나와 근거를 가진다. 검사를 실행하지 않은 상태는 `pass`가 아니다. `alpha` 채널이 있다는 사실만으로 배경 제거 성공으로 보지 않는다.

| 검사 | 판정 방식과 차단 조건 |
|---|---|
| 파일 규격 | PNG·RGBA·sRGB·2048 정사각, 유효한 decode·해시 |
| 유효 전경·투명 배경 | alpha>8인 픽셀과 실제 투명 여백 모두 존재; 빈 이미지·전면 불투명은 실패 |
| 프레임 절단 | 유효 전경이 캔버스 가장자리 1px 띠에 닿으면 실패 |
| 물체 구성 | item별 허용 구성과 component 확인; 소매 등 분리 투영은 곧바로 다중 물체로 판정하지 않음 |
| 혼입 | 피부·손·얼굴·다른 의상·문자·그림자 검수; 검출기 없는 경우 수동 검수 대기 |
| 앵커·실루엣 | §8 오차, 착용 overlay, 목·소매·허리·발목의 형태 보존 |
| 시점 일관성 | 동일 item·몸·blueprint, 색·패턴·봉제선·장식 개수·좌우 일치 |
| 원본 디자인 | 관찰된 색상·실루엣 비교, 가려진 구조에 대한 추론 검수 |
| 접합 여유 | 프로필별 접합 mask·최소 overlap 확인; 기준 mask가 없으면 검수 대기 |
| crop 복원 | 전경 손실 없음, 공통 provider 배율, 정·역행렬 왕복 검사 |
| 얼굴 | 고정 head에 UV 텍스처 적용 후 8표정의 위치·경계 확인 |

component 수·색상 분포만으로 디자인 일치나 피부 혼입을 확정하지 않는다. 의미 검수는 초기에 사람이 맡을 수 있다. 이후 검출기를 붙여도 판정 근거와 버전을 남긴다.

다음 조건을 모두 충족할 때만 물체에 `ready_for_meshy`를 부여한다.

1. 기준 몸·blueprint가 고정되고 각 해시가 현재 파일과 일치한다.
2. 필수 시점이 모두 존재하며 정면이 첫 입력이다. 기본 물체는 front/side/back 세 장이다.
3. 모든 필수 QC가 pass 또는 해당 artifact 해시에 묶인 검수 승인이다.
4. 이미지·좌표·변환·생성 이력·QC manifest가 완전하다.
5. 파일·디자인 변경 이후의 오래된 검수 결과가 없다.

실패 항목을 수동 승인으로 덮지 않는다. 잘못된 검출을 정정할 때는 사유·새 측정과 QC revision을 남긴다. body는 `template_ready`, face는 `ready_for_texture`로 분류하며 일반 파츠 Meshy 배치에서 제외한다. 부분 패키지는 내려받을 수 있지만 누락·검수 대기와 `partial` 상태를 명시한다.

## 11. 패키지와 Manifest

아래는 외부 전달 구조이며 현재 내부 저장소 폴더를 즉시 이전하라는 뜻은 아니다.

```text
character/char_0001/
  reference/original.png
  blueprint.json
  body/profile.json
  body/anchors.json
  body/{front,side,back}.canvas.png
  face/{neutral,smile,happy,wink_left,wink_right,sad,angry,surprised}.canvas.png
  face/{expression}.uv.png
  face/manifest.json
  parts/{canonical-slot}/{item-id}/
    raw/{view}.png
    {front,side,back}.canvas.png
    {front,side,back}.crop.png
    {front,side,back}.provider.png
    manifest.json
    qc.json
  manifest.json
  review/contact-sheet.png
```

contact sheet는 검수용이며 Meshy 입력이 아니다. 물체 하나의 여러 시점을 하나의 이미지로 합쳐 제출하지 않는다.

각 part manifest의 필수 계약:

| 그룹 | 필드 |
|---|---|
| 식별 | schemaVersion, characterId, itemId, slot, itemRevision, objectKey |
| 기준 | referenceSha256, blueprintSha256, bodyProfileId/revision/hash, bodySha256, poseHash, cameraHash, anchorsHash |
| 설계 | garmentType, attachment, occupies, inferredDetails |
| view별 이미지 | 파일명·sha256·크기·원본 응답 연결·raw→canvas 변환 |
| view별 crop | alphaBbox, paddingRatio/Px, cropSquare, providerSquare, canvasToProvider, providerToCanvas |
| view별 정렬 | 목표·관찰 앵커, 가시성·신뢰·측정 방법, 정렬 전 오차·정렬행렬·최종 잔차 |
| 실행 | provider/model, prompt/template 해시, 입력 이미지 해시, attemptId, taskId 또는 응답 receipt, 실행 시각 |
| 검수 | qcRevision, 검사별 상태·근거, 검수 대상 해시, reviewedBy/At, 최종 readiness |

루트 manifest는 실제 포함 파일의 경로·sha256, 항목별 readiness, 누락 항목, 계획 대비 완료 수, `complete`/`partial`을 기록한다. 패키지 내부 상대 경로만 허용한다. 해시 목록에 루트 manifest 자신의 해시를 넣는 순환 구조는 사용하지 않는다. API 키·개인 서버 경로·인증 헤더는 패키지에 포함하지 않는다.

## 12. 작업·복구·UI 계약

UI의 기본 동작은 레퍼런스 → 몸 유형 → 파츠 선택 → 시점 선택 → **이미지 규격 생산**이다. 몸·얼굴·헤어·상의·하의·신발·액세서리는 그룹 선택으로 제공하고 내부 item별 진행 상태를 보여준다. 원본 시트의 모자와 지팡이는 선택 항목으로 표시한다.

생산 전에 실제 생성할 `(item, view)`와 얼굴 표정 수, 이미 승인되어 재사용할 수량, 최대 이미지 호출 수를 계산한다. 기본 상한은 이미지 1개당 새 생성 요청 1회다. QC 실패 항목만 새 revision으로 재생성할 수 있고 이미 승인된 항목을 다시 생성하지 않는다.

단계별 상태:

```text
draft → analyzed → body_review_required → body_locked → planned
planned → generating → processing → qc_pending
qc_pending → ready_for_meshy | ready_for_texture | template_ready
qc_pending → review_required | regeneration_required
generating → provider_paused | failed
```

승인된 몸을 선택하면 `body_review_required`를 재사용 승인으로 통과한다. 검수자는 overlay·원본 비교·시점 일관성을 확인하며 실패 이유와 해당 파츠 재생성 동작을 볼 수 있다. 얼굴 템플릿 누락은 `face_mapping_required`로 표시한다.

요청 수락 시 소유자·idempotency key·입력 fingerprint·상한을 영속 저장한다. 같은 key와 다른 입력은 충돌로 거절한다. provider 호출 전 의도를 저장하고 응답 원문을 로컬 후처리보다 먼저 보존한다. 시간 초과·응답 유실 때 새 POST를 자동 반복하지 않는다. 기존 task 조회 또는 저장된 바이트 후처리로 복구하고, 확인할 수 없는 요청은 `provider_paused`로 남긴다.

새로고침·서버 재시작은 승인 결과와 작업 이력을 복원해야 한다. 한 항목 실패는 다른 완료 항목을 지우지 않는다. 완료 화면은 파츠별 세 시점, 투명 배경, overlay, crop, QC 상태와 패키지 다운로드를 제공한다. 사용자는 이미지 패키지를 확인한 뒤 별도 **3D 생성** 동작으로 진행한다. 이미지 생산 버튼은 Meshy를 호출하지 않는다.

## 13. 인수 기준

| 시나리오 | 기대 결과 |
|---|---|
| 첨부 레퍼런스 분석 | 기본 복장과 선택 모자·지팡이 구별, 헤어 3종·리본·신발 좌우·가방/키링 분리 |
| 새 몸 또는 기존 몸 선택 | 같은 몸·카메라·A-pose·앵커 해시로 세 시점 고정 |
| 카디건 생성 | 착용 위치 보존, 손·피부·목 리본 제외, 가려진 후면 완성 |
| 8px / 20px 경계 | 8은 후보, 20은 정렬 대상, 20 초과는 전달 차단; 재측정 8 초과 실패 |
| 앵커 누락·옅은 배경 잔존·빈 alpha·프레임 절단 | 검수 대기 또는 실패, 자동 ready 금지 |
| 좌우 비대칭과 여러 시점 | 가방·리본 위치 일치, 신발 명명은 캐릭터 기준, 공통 provider 배율 |
| crop·복원 | 원 canvas 보존, 변환 왕복 오차 ≤0.5px, 전경 손실 없음 |
| 얼굴 8종 | 동일 head·UV에서 표정만 변화, 새 head Meshy 요청 0회 |
| 입력 파일 교체·새 blueprint | 해시 불일치 또는 revision 변경으로 종전 승인 무효 |
| 응답 유실·재시작·동일 key 재전송 | 유료 요청 중복 없음, 완료 이미지·검수 복구 |
| 부분 실패 | 성공 항목 보존, 부분 패키지에 누락·대기 명시 |
| 이미지 패키지 완료 | manifest·QC·이미지 해시 일치; Meshy 호출 0회 |

로컬 fixture는 좌표·상태·복구 계약의 증거다. 실제 레퍼런스 기반 생성 품질은 실제 provider 출력과 시각 검수로 따로 확인한다. 이 문서를 작성한 것만으로 위 인수 기준을 통과한 것으로 표시하지 않는다.

## 14. 현재 코드와 구현 순서

2026-09-18 작업 트리의 읽기 검토 기준이다. 이번 명세 작업에서 provider 실행이나 전체 테스트는 수행하지 않았다.

| 확인한 코드 | 재사용할 기반 | v1에서 추가·변경할 것 |
|---|---|---|
| `backend/src/services/avatar_standard_models.py::image_spec` | 2048px, 300/1800, center=1024, 몸 높이 기반 배율, 세 시점 | 현재 `source_rest_pose`; A-pose 검증·프로필 고정 필요 |
| 같은 파일의 입력 모델 | hair/hat/top/bottom/shoeLeft/shoeRight/accessory, crop, 기본 8px | canonical slot 어댑터, 세부 slot·blueprint·QC 계약 |
| `avatar_standard_design.py::similarity/align` | similarity 변환과 최종 잔차 제한, 원본 버전 확인 | 정렬 전 8/20px 분기, 관찰 근거, alpha crop·전체 QC; 현재 align은 full-canvas crop 등록 |
| `avatar_image_pipeline.py::WARDROBE_BODY_PROMPT` | 대머리·불투명 기본복·35° A-pose 지시 | 실제 결과 검증과 동일 몸의 세 시점 고정 |
| 같은 파일의 `DESCRIPTIONS` | 분리 파츠 지시 | 현재 face는 별도 머리 형상을 지시함; 고정 head·UV 표정 경로로 분리 |
| `avatar_blueprints.py::SLOTS` | body/face/hairBack/hairFront/hat/top/bottom/shoes | extension·액세서리·좌우 신발·설계 원본 확장 |
| `avatar_openai_images.py::DEFAULT_MODEL` | 기본 Sunburst 모델 식별자 | 모델 이름과 실제 생산 성공 증거를 구별 |
| `avatar_standard_provider.py` | 몸·object·시점 일치, 정면 우선, 해시·제출 이력·복구 | `ready_for_meshy` 전체 QC gate와 패키지 계약 검사 |

구현은 다음 순서로 진행한다.

1. **계약:** backend의 blueprint·slot·manifest 모델, 프로필/해시 불변성, 프론트 API 타입.
2. **좌표:** 승인 몸 렌더·앵커 고정, alpha bbox, crop/provider 공통 배율, 변환 영수증.
3. **생산:** 원본+몸+blueprint 입력, item/view별 작업 기록과 재개, 독립 얼굴 UV 경로.
4. **검수:** 측정·overlay·시점 일관성, 실패 차단과 해시 기반 승인, Meshy gate.
5. **화면·패키지:** 단순 생산 폼, 파츠별 결과/재생성, 완전·부분 패키지 다운로드.
6. **실생산 확인:** 첨부 캐릭터 한 세트의 실제 이미지 생산·시각 검수. 그 후 별도 3D 생성·피팅 검증.

책임 경계는 그대로 유지한다. Python 구현은 `backend/src/`, 테스트는 `backend/tests/`, 브라우저 화면과 API 소비는 `frontend/src/`다. 루트 `uv`, `src.*`, `.env`, `uv.lock`, 기본 `data/` 기준은 변경하지 않는다.
