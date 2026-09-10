# Ally 의상 교체 파이프라인

`data/image/` 캐릭터 자체를 생성하고 리깅한 뒤 별도 의상 GLB로 교체하는 경로는 [캐릭터 파이프라인](character-pipeline.md)을 참고한다.

`data/ally.glb`의 `tee.001`을 추출 → 이미지로 Meshy Retexture → 의상 GLB 다운로드 → Blender MCP에서 체형 맞춤 및 가중치 이전 → 기존 애니메이션을 포함한 GLB와 편집용 blend 저장.

기존 FastAPI/DB 변경이나 새 dependency 없이 별도 CLI로 실행한다. `uv sync --extra blender`로 기존 선택 dependency를 설치한다. `.env`의 `MESHY_API_KEY`를 사용한다.

## 실행

프로젝트 루트에서 실행한다. 작업마다 새로운 `--run` 디렉터리를 지정한다. Blender는 이 파이프라인만 사용하는 별도 인스턴스여야 한다.

```powershell
uv run python -m src.editor_cli --root data/wardrobe-runtime --port 9878 start --blender 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
uv run python -m src.wardrobe_cli --run data/wardrobe/my-A prepare --reference data/image/A.png
uv run python -m src.wardrobe_cli --run data/wardrobe/my-A submit
uv run python -m src.wardrobe_cli --run data/wardrobe/my-A status
# status가 generated일 때:
uv run python -m src.wardrobe_cli --run data/wardrobe/my-A download
uv run python -m src.wardrobe_cli --run data/wardrobe/my-A dress
```

`submit`은 유료 Meshy 작업을 한 번 생성한다. `status`는 한 번 조회하며 반복 실행해도 새 작업을 만들지 않는다. 전송 응답을 잃으면 `submission_uncertain`으로 남고 재전송을 차단한다. Meshy 대시보드에서 작업 ID를 확인한 뒤 `status --task-id ID`로 복구한다. 서명된 다운로드 URL이 만료되면 `status`로 갱신한다. 키나 업로드 본문은 저장하지 않는다.

`dress` 결과의 `model`, `source` 경로가 최종 GLB와 blend다. 각 시도는 별도 `fit-*` 폴더에 저장한다. `run.json`에는 원본 해시, Meshy 작업 ID, 최신 피팅 결과가 남는다. Blender 응답이 불확실하면 잠금을 유지한다. 전용 Blender 프로세스와 산출물을 확인한 후에만 오류에 표시된 잠금 파일을 제거한다.

## 새 실루엣과 의상 교체

Retexture는 기존 옷의 표면 스타일을 바꾼다. 후드, 치마, 모자 등 새로운 형상을 생성하지 않는다. `A.png`는 캐릭터 전신 참조이므로 얼굴/머리 특징이 옷 텍스처에 섞일 수 있다. 의상만 따로 준비한 PNG를 참조로 사용하면 이 위험을 줄일 수 있다. `typeA.png` 등 여러 캐릭터가 있는 시트는 개별 의상 이미지로 준비해야 한다.

새로운 형상은 별도로 만든 **의상만 포함한 GLB**를 다음처럼 연결한다. Meshy Image-to-3D 결과에 몸/얼굴까지 들어 있으면 Blender에서 분리한 뒤 사용한다. 자동 의미 분할은 구현 범위에 포함되지 않는다.

```powershell
uv run python -m src.wardrobe_cli --run data/wardrobe/my-A dress --garment data/custom-outfit.glb --fit bounds
```

`bounds`는 기준 의상 바운딩 박스에 축별 크기와 위치를 맞추는 초기 피팅이다. 두 모델의 방향과 포즈가 같아야 하며, 헐렁한 옷이나 치마에 정밀 피팅을 보장하지 않는다. 이미 피팅한 의상은 `--fit none`을 사용한다. 매 실행은 기준 blend에서 시작하므로 옷을 누적해서 겹치지 않는다. 원래 옷은 blend에 숨겨 보관하고 GLB에서는 제외한다.

기존 의상의 가까운 표면에서 관절 가중치를 이전하고, 정점마다 상위 4개 영향만 정규화한다. 모든 정점이 변형 관절에 연결되어야 한다. 기준의 29개 관절과 18개 애니메이션 이름이 내보낸 GLB에도 존재하는지 검사한다. 얼굴 및 기존 몸의 가중치는 변경하지 않는다. 원래 리그에 없는 팔꿈치/무릎 관절이나 천 시뮬레이션은 추가하지 않는다. Meshy Auto Rigging으로 전체 캐릭터를 다시 리깅하는 경로는 기존 world API에 있으며, 기준 리그 보존을 위한 이 경로에서는 호출하지 않는다.

`quality.json`의 통과는 구조 검사다. 다양한 포즈에서 관통, 옷의 늘어짐, 재질, 런타임 재생을 검수해야 하므로 상태는 `review_required`다. 원본 `ally.glb`는 덮어쓰지 않는다.

## 외부 규격

- [Meshy Retexture API](https://docs.meshy.ai/en/api/retexture): 모델 data URI와 이미지 스타일 입력, 작업 생성/조회.
- [Meshy Image-to-3D](https://docs.meshy.ai/en/api/image-to-3d): 새 의상 형상을 만드는 상류 도구로 사용 가능.
- [Meshy Rigging](https://docs.meshy.ai/en/api/rigging): 새 캐릭터 전체 리깅용. 기존 Ally 뼈대 보존과는 목적이 다르다.

테스트: `uv run pytest backend/tests/services/test_wardrobe.py` 및 전체 `uv run pytest`.
