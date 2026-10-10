"""
FastAPI application entry point.

Run (from the project root):

    venv\\Scripts\\python.exe -m uvicorn app.main:app ^
        --app-dir web\\backend --host 127.0.0.1 --port 8000

or double-click run_web.bat. When web/frontend/dist exists it is
served as the SPA from the same origin; otherwise run the Vite dev
server (npm run dev in web/frontend) which proxies /api here.
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import auth, settings
from .routes_auth import router as auth_router
from .routes_ops import router as ops_router
from .routes_public import router as public_router

logger = logging.getLogger(__name__)


def create_app():

    app = FastAPI(
        title="City-Wide AI Traffic Engine API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    auth.init_db()

    app.include_router(public_router)
    app.include_router(auth_router)
    app.include_router(ops_router)

    dist = settings.FRONTEND_DIST

    if (dist / "assets").is_dir():

        app.mount(
            "/assets",
            StaticFiles(directory=dist / "assets"),
            name="assets"
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):

        if full_path.startswith("api"):

            raise HTTPException(status_code=404, detail="Not found.")

        if not dist.is_dir():

            raise HTTPException(
                status_code=404,
                detail=(
                    "Frontend not built. Run: "
                    "cd web/frontend && npm install && npm run build"
                )
            )

        if full_path:

            candidate = (dist / full_path).resolve()

            if (
                candidate.is_file()
                and candidate.is_relative_to(dist.resolve())
            ):

                return FileResponse(candidate)

        return FileResponse(dist / "index.html")

    return app


app = create_app()


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )
