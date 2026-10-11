"""FastAPI application entry point."""

from fastapi import FastAPI

from job_copilot_api.cv.routes import router as cv_router

app = FastAPI(title="AI Job Copilot")
app.include_router(cv_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
