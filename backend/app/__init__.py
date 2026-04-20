from fastapi import FastAPI

from .routers import requirement, spec, provider, system


def create_app(lifespan=None) -> FastAPI:
    app = FastAPI(
        title="RPA 需求规格说明书自动生成系统",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(requirement.router)
    app.include_router(spec.router)
    app.include_router(provider.router)
    app.include_router(system.router)
    return app
