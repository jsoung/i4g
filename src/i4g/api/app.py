"""FastAPI app factory for i4g Analyst Review API."""

from fastapi import FastAPI
from i4g.api.review import router as review_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(title="i4g Analyst Review API", version="0.1")
    app.include_router(review_router, prefix="/reviews", tags=["reviews"])
    return app


# For uvicorn, expose `app` at module level
app = create_app()
