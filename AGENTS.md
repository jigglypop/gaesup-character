# AGENTS.md

## 목표와 경로

메이플풍 3D SD 캐릭터의 몸·얼굴·헤어·의상·무기·장비를 생산하고, Blender 조립과 브라우저 검수를 연결한다. 기존 Meshy 리깅 캐릭터의 보존 분리 경로도 유지한다.
기본 책임자는 GPT-6 Astra다. 설계 판단, 작업 분해, 결과 통합, 실제 커넥톰의 근거 판단과 최종 완료 판정은 Astra가 맡는다. 경계가 분명한 구현·테스트·데이터 정리 작업은 GPT-5.6 Sol의 `medium` 추론 강도로 위임할 수 있다.

- 목표 경계는 `backend/`와 `frontend/`다. 백엔드는 작업·파일·Meshy·Blender를, 프론트는 화면과 API 소비를 소유한다.
- Python 구현은 `backend/src/`, 테스트는 `backend/tests/`, 브라우저 앱은 `frontend/src/`에 있다. Python 패키지 이름 `src.*`와 루트 `uv` 명령을 유지한다. `.env`, `uv.lock`, 기본 `data/`는 저장소 루트가 기준이다.
- 프론트 3D는 사용자가 지정한 React Three Fiber·WebGPU·gaesup-world 조합을 사용한다. 호환 버전과 검증 기준은 `frontend/AGENTS.md`를 따른다.
- 새 생성은 Meshy 7의 현재 공식 계약을 사용한다
- 새 공장 파츠 이미지 생성은 OpenAI `gpt-image-2.5-sunburst`를 기본으로 사용한다.  


## 변경과 완료
- 기존 `/api/world/*`, CLI, 데이터와 외부 응답의 호환성을 유지한다. 요청한 제어 기능에 필요한 API 추가와 폴더 분리는 범위 안에서 진행한다. DB schema 변경은 명시 요청이 있어야 하며 forward·rollback·데이터 영향을 설명하고 destructive migration은 하지 않는다.
- 작은 diff와 기존 스타일을 우선한다. 전체 재작성·프레임워크 교체·무관한 rename을 피하고 dependency는 필요와 이유가 있을 때만 추가한다.
- 검증은 변경에 비례한다. 문서만 고치면 링크·지시 충돌을, 코드면 관련 테스트를, UI 기능이면 실제 API 연결·재접속·오류 표시를 확인한다. 통과한 검사를 이유 없이 반복하지 않는다.
- 로컬 검증 명령은 루트 `uv run pytest -q`, `frontend/`의 `npm run build`와 `npm run test:e2e`다. 브라우저 테스트는 임시 데이터와 비어 있는 provider 설정을 쓴다. Blender 레시피 변경은 `backend/`에서 `uv run python tests/run_blender_parts_check.py`로 폐기 가능한 fixture를 확인한다. 이 검증과 발생한 실패 수정은 별도 승인 없이 진행한다.
- 분리 기능의 완료는 원본 보존, 동일 rig/weights 유지, 버전별 GLB·Blender 파일, 실제 화면과 관련 동작 확인을 포함한다. 재질 분리는 후보 생성이며 의상 의미 판정·숨겨진 몸 복원·시각 승인을 대신하지 않는다.
- 파츠 선택은 모델 SHA-256과 glTF node/primitive/face ID에 묶는다. 머리·헤어·모자·상의·바지·치마를 이름만 바꾸어 분절 완료로 처리하지 않는다. 원본에 없는 파츠를 만들거나 누락된 몸을 복원했다고 표시하지 않는다.
- 캐릭터 PostgreSQL은 `CHARACTER_DATABASE_URL`과 migration `002`를 사용한다. 파일 작업 일지가 실행·복구의 기준이며 DB는 버전·작업·검수 조회 인덱스다. DB 동기화 실패 시 일지를 재색인하고 Meshy POST를 다시 보내지 않는다.
- 에셋의 기술 통과와 시각 승인은 별개다. 실제 출처·파츠·동작·외형 증거 없이 완료로 표시하지 않는다. 배치 제외는 사용자 결정으로 기록하고 승인 수에 합산하지 않는다.
- 수정 전 문제를 짧게 알리고 마지막에는 변경·검증·미구현 범위를 명확히 보고한다.
