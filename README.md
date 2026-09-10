# gaesup-character

Meshy 캐릭터의 소스 등록, 기본 리깅, Blender 재질 경계 분리, 3D 미리보기와 버전별 검수를 관리합니다.

코드는 `backend/`(FastAPI·CLI·테스트·migration)와 `frontend/`(TypeScript·Vite·Three.js)로 나뉩니다. 운영 지침은 [AGENTS.md](AGENTS.md), 상태·복구·지원 범위는 [제어 계약](docs/character-control-plane.md)에 있습니다.

Ally 기준 의상 교체와 기존 리깅 재사용은 [의상 파이프라인](docs/wardrobe-pipeline.md)을 참고하세요.

기존 `/api/world/*`의 생성·GLB 후처리·애니메이션 병합·저장·프록시 API도 유지합니다.

## 시작하기

Python 3.11과 [uv](https://docs.astral.sh/uv/)를 사용합니다.

```bash
cp .env.example .env
uv sync
uv run asset-api
```

개발 중 자동 재시작은 다음 명령을 사용합니다.

```bash
uv run asset-dev
```

서버 기본 주소는 `http://localhost:8000`이며 상태 확인 경로는 `/health`와 `/api/health`입니다.

다른 터미널에서 프론트엔드를 실행합니다. UI는 **http://127.0.0.1:5273/** 입니다.

```powershell
cd frontend
npm ci
npm run dev
```

Vite의 로컬 `/api` 프록시가 8000 포트로 연결하고 서버 측에서 개발 사용자와 `API_KEY` 헤더를 설정합니다. 키는 브라우저 번들에 넣지 않습니다. 로컬 개발 서버는 loopback으로만 실행하며 공개 배포용 인증 프록시가 아닙니다. 제어 서버는 단일 worker로 실행하세요.

화면에서 캐릭터 등록 → 이미지/리깅 GLB 업로드 → 모델 검사 → 가능한 분리 작업 → 파츠 역할·몸의 coverage 지정 → 검수 기록 순으로 진행합니다. 생성·리깅은 별도의 **유료** 버튼이며 등록이나 새로고침으로 제출하지 않습니다. 이미 리깅된 파일을 가져오면 provider 이력이 없는 상태로 보존합니다.

재질 경계가 있는 모델은 Blender에서 분리해 새 GLB·`.blend`·기본 자세 렌더를 만듭니다. 몸과 의상이 한 재질로 붙은 경우 영역별 편집이 필요합니다. 원래 옷 아래 몸이 없는 모델은 `partial`로 기록하며, 승인에는 외형·동작 확인이 필요합니다.

`/api/world/*`는 JWT 인증이 필요합니다. 로컬호스트에서 개발할 때는 요청에 `X-User-Id: 1` 헤더를 넣어 개발 사용자로 호출할 수 있습니다.

## API 범위

- `POST /api/world/textures/generate`
- `POST /api/world/generate`
- `GET /api/world/jobs/{job_id}`
- `GET /api/world/jobs/{job_id}/stream`
- `GET /api/world/animations/catalog`
- `GET /api/world/assets`
- `PATCH /api/world/assets/{asset_id}`
- `DELETE /api/world/assets/{asset_id}`
- `GET /api/world/assets/{asset_id}/model`
- `GET /api/world/assets/{asset_id}/animations/{clip_index}/model`
- `POST /api/world/placements`
- `GET /api/world/placements/latest`

Swagger UI는 `/docs`, OpenAPI 문서는 `/openapi.json`에서 확인할 수 있습니다.

## 선택 구성

- `WORLD_3D_PROVIDER=meshy`와 `MESHY_API_KEY`: Meshy 3D 생성. 설정하지 않으면 구조화된 월드 계획만 반환합니다.
- `DATABASE_URL` 또는 PostgreSQL용 `DB_HOST` 계열 변수: job, asset, placement 영속화. 없으면 프로세스 메모리를 사용합니다.
- AWS S3 변수: 생성 모델과 참조 이미지의 안정적인 저장 URL을 제공합니다.
- Gemini 변수는 기본 참조 이미지 생성에 사용합니다. OpenAI는 요청이나 DB 모델 설정에서 OpenAI 이미지 모델을 명시했을 때 사용합니다.
- `WORLD_SKIN_WASM_PATH`: 얼굴 스킨 가중치 후처리용 `gaesup_core.wasm` 경로입니다. 파일이 없으면 해당 단계는 `no_change`로 건너뜁니다.

PostgreSQL 스키마는 `backend/migrations/001_postgresql_3d_schema.up.sql`에 있습니다. DB를 사용할 때 서버 시작 전에 적용하세요.

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f backend/migrations/001_postgresql_3d_schema.up.sql
```

테이블 구조, 인덱스, 외래키, 롤백 영향은 `docs/postgresql-schema.md`에 정리되어 있습니다. API 요청 중에는 스키마를 자동 생성하지 않습니다. `sync=true` 애니메이션 카탈로그 요청은 migration으로 생성된 테이블의 데이터만 갱신합니다. 미디어 업로드 API는 제거되었으므로 새 입력은 `reference_image_url` 같은 URL 기반 필드를 사용하세요.

## 테스트와 빌드

이미지 캐릭터의 별도 의상 교체와 리깅은 [캐릭터 파이프라인](docs/character-pipeline.md)을 참고하세요. `data/image/A.png`로 생성·리깅·의상 GLB 교체·포즈 검증까지 실행한 샘플을 포함합니다.

```bash
uv run pytest
uv build --package asset-3d-api
docker build -f backend/Dockerfile -t asset-3d-api .
docker run --rm -p 8000:8000 --env-file .env asset-3d-api
```

프론트 검증은 `frontend/`에서 `npm run build`, `npx playwright install chromium`, `npm run test:e2e`를 실행합니다. E2E는 임시 데이터와 별도 API(8012)·UI(5274)를 사용하며 Meshy를 호출하지 않습니다. Three.js는 GLB·애니메이션 미리보기, Vite는 개발 서버·빌드, Playwright는 브라우저 동작 검증에 사용합니다.

Blender 분리 변경 시 `backend/`에서 `uv run python tests/run_blender_parts_check.py`로 임시 rig fixture의 실제 분리·원본 보존·스킨·출력을 검사합니다. 이 검사는 실제 캐릭터의 외형 승인이 아닙니다.

`ASSET_DATA_ROOT`는 기본 루트 `data/`를 바꾸고, `CHARACTER_OWNER_ID`는 기존 manifest의 소유자(기본 1), `BLENDER_EXECUTABLE`은 독립 분리 작업용 Blender 경로를 지정합니다. 미지정 시 PATH와 Windows 기본 설치 위치를 탐색합니다. 기존 CLI/MCP 포트는 `BLENDER_PORT`로 구분합니다.
