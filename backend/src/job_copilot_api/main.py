"""FastAPI application entry point."""

from fastapi import FastAPI

from job_copilot_api.cv.routes import router as cv_router
from job_copilot_api.jobs.routes import router as jobs_router
from job_copilot_api.matching.routes import router as matching_router
from job_copilot_api.valorization.routes import router as valorization_router

app = FastAPI(title="AI Job Copilot")
app.include_router(cv_router)
app.include_router(jobs_router)
app.include_router(matching_router)
app.include_router(valorization_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
