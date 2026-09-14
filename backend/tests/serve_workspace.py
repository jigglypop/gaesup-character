"""Isolated real API for browser tests. No provider credentials or production files."""

import os
from pathlib import Path
import tempfile

import uvicorn
from fastapi import FastAPI

from api.test_characters import rigged_glb


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="wardrobe-browser-") as directory:
        os.environ.update(ASSET_DATA_ROOT=directory, API_KEY="", MESHY_API_KEY="", GEMINI_API_KEY="", OPENAI_API_KEY="",
                          JWT_SECRET_KEY="", BLENDER_PORT="62129", CHARACTER_OWNER_ID="1", CHARACTER_DATABASE_URL="")
        from src.api.characters import router, pipeline_error_handler
        from src.api.avatars import router as avatar_router
        from src.api.avatar_factory import router as factory_router
        from src.api.avatar_blueprints import router as blueprint_router
        from src.services.character_pipeline import CharacterPipeline, PipelineError

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.include_router(avatar_router, prefix="/api")
        app.include_router(factory_router, prefix="/api")
        app.include_router(blueprint_router, prefix="/api")
        app.add_exception_handler(PipelineError, pipeline_error_handler)

        @app.get('/health')
        def health():
            return {"status": "ok"}

        pipeline = CharacterPipeline(Path(directory), port=62129)
        value = pipeline.create("Browser Fixture", 1.7, 1)
        pipeline.upload(value["id"], 1, rigged_glb(), "model", value["revision"])
        uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("WORKSPACE_TEST_API_PORT", "8012")), log_level="warning")
