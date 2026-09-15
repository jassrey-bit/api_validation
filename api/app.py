"""Servicio FastAPI que expone src/orchestrator.py (regresión de amortización
+ comparación PROD vs DEV) a un frontend, con el mismo contrato de job
pending/done/error por polling que usa el backend de Validación de
documentos (playwright-pytest-pom/api/app.py)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.jobs import get_job, list_jobs, load_persisted_jobs, rerun_job, submit_run_job
from api.schemas import CreateRunRequest
from src.utils.data_loader import load_test_cases

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_persisted_jobs()
    yield


app = FastAPI(title="API Validation Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # El puerto del dev server de Vite cambia seguido, así que se permite
    # cualquier puerto en localhost/127.0.0.1 en vez de fijar uno solo.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


@app.get("/fixtures")
def list_fixtures() -> list[dict]:
    return [{"case_id": c["case_id"], "description": c.get("description", "")} for c in load_test_cases()]


@app.post("/runs")
def create_run(body: CreateRunRequest) -> dict:
    custom_cases = [c.model_dump() for c in body.custom_cases] if body.custom_cases else None
    try:
        job_id = submit_run_job(body.mode, case_ids=body.case_ids, custom_cases=custom_cases)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"job_id": job_id, "status": "pending"}


@app.get("/runs")
def list_runs(
    mode: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    case_id: str | None = None,
    page: int = 1,
) -> dict:
    jobs, total = list_jobs(
        mode=mode,
        status=status,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        case_id=case_id,
        page=page,
        page_size=PAGE_SIZE,
    )
    return {
        "items": [
            {
                "job_id": job.id,
                "mode": job.mode,
                "created_at": job.created_at.isoformat(),
                "status": job.status_label,
                "summary": job.summary,
            }
            for job in jobs
        ],
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
    }


@app.get("/runs/{job_id}")
def get_run(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job no encontrado")

    if job.status == "pending":
        return {"job_id": job.id, "status": "pending"}
    if job.status == "error":
        return {"job_id": job.id, "status": "error", "error": job.error}

    return {
        "job_id": job.id,
        "status": "done",
        "mode": job.mode,
        "summary": job.summary,
        "result": job.result,
    }


@app.post("/runs/{job_id}/rerun")
def rerun_run(job_id: str) -> dict:
    new_job_id = rerun_job(job_id)
    if new_job_id is None:
        raise HTTPException(status_code=404, detail="job o casos originales no encontrados")
    return {"job_id": new_job_id, "status": "pending"}
