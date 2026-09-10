# Character Wardrobe backend

FastAPI와 캐릭터·의상 CLI를 제공하는 uv workspace 패키지다. 실행법은 [저장소 README](../README.md), 제어 API와 상태 계약은 [제어 설계](../docs/character-control-plane.md)를 참고한다.

이 디렉터리에서도 `uv run asset-api`, `uv run pytest -q`, `uv run python -m src.character_cli --help`를 사용할 수 있다. 기본 데이터와 `.env`는 저장소 루트에서 읽는다. 배포 패키지는 `ASSET_DATA_ROOT`를 절대 경로로 지정한다.
