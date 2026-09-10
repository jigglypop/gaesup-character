# 간결한 Codex 하네스

실행 코드는 `backend/`와 `frontend/`로 분리되어 있다. 현재 지원 기능과 남은 경계는 [제어 계약](../docs/character-control-plane.md), 실행 명령은 [README](../README.md)를 따른다.

- [루트 AGENTS.md](../AGENTS.md): 작업 범위·권한·호환성·검증 기준.
- [backend/AGENTS.md](../backend/AGENTS.md): 상태·실행·복구·API 경계. [backend/src/AGENTS.md](../backend/src/AGENTS.md)는 이 지침으로 연결한다.
- [frontend/AGENTS.md](../frontend/AGENTS.md): 화면·비동기 요청·미리보기·검수.
- [공유 제어 계약](../docs/character-control-plane.md): 현재 구현과 목표 API, 소스 등록, 상태·idempotency, 구현 순서와 통과 증거.

작업 영역의 지침과 필요한 참조만 읽는다. 문구·스타일 수정에 provider 감사나 에셋 렌더를 요구하지 않는다.

모델과 선택적 작업자 기본값은 [config.toml](config.toml), 역할은 [worker.toml](agents/worker.toml)에 있다. 사용자가 선택한 현재 세션 모델과 실행 지시가 우선이며 이 문서는 위임을 요구하지 않는다.

스킬 [meshy-character-wardrobe](skills/meshy-character-wardrobe/SKILL.md)는 제어 API/화면, 실제 Meshy 작업, Blender 분리, 품질 판정으로 필요한 문서를 안내한다. 업무 실행기는 백엔드 서비스에 구현하며 에이전트 스킬을 서버 dependency로 쓰지 않는다.

현재 저장소 루트에서 배치 감사기 코드를 바꾼 경우 관련 테스트를 실행한다. 아래 명령은 API/UI 구현 완료를 검증하지 않는다.

```powershell
uv run pytest -q backend/tests/test_character_batch_harness.py
uv run python .codex/skills/meshy-character-wardrobe/scripts/audit_batch.py data/characters/batch.json
```
