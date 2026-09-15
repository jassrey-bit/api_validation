"""Job store en memoria + ThreadPoolExecutor + persistencia en disco, mismo
patrón que playwright-pytest-pom/api/jobs.py (el backend de "Validación de
documentos"): sin Celery ni Redis, solo stdlib, con metadata.json por job
para sobrevivir a un reinicio del proceso."""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Literal

from src.orchestrator import run_batch
from src.utils.data_loader import load_test_cases

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)
_jobs: dict[str, "Job"] = {}
_lock = Lock()

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage" / "runs"

# Igual que en el backend de validación de documentos: no tiene sentido
# acumular ejecuciones viejas indefinidamente.
RETENTION_PERIOD = timedelta(days=5)
_PURGE_CHECK_INTERVAL = timedelta(hours=1)
_last_purge_at: datetime | None = None


def _purge_expired_jobs() -> None:
    global _last_purge_at
    now = datetime.now(timezone.utc)

    with _lock:
        if _last_purge_at is not None and now - _last_purge_at < _PURGE_CHECK_INTERVAL:
            return
        _last_purge_at = now
        cutoff = now - RETENTION_PERIOD
        expired = [job for job in _jobs.values() if job.created_at < cutoff]
        for job in expired:
            del _jobs[job.id]

    for job in expired:
        shutil.rmtree(job.dir, ignore_errors=True)


@dataclass
class Job:
    id: str
    mode: Literal["regression", "comparison"]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"  # pending | done | error
    result: list[dict] | None = None
    error: str | None = None

    @property
    def dir(self) -> Path:
        return STORAGE_DIR / self.id

    @property
    def metadata_path(self) -> Path:
        return self.dir / "metadata.json"

    @property
    def resolved_cases_path(self) -> Path:
        return self.dir / "resolved_cases.json"

    @property
    def summary(self) -> dict:
        if self.result is None:
            return {"total": 0, "passed": 0, "failed": 0}
        total = len(self.result)
        passed = sum(1 for c in self.result if c.get("passed"))
        return {"total": total, "passed": passed, "failed": total - passed}

    @property
    def status_label(self) -> str:
        """PASSED/FAILED derivado del resultado, usado para filtrar el historial."""
        if self.status != "done":
            return ""
        return "PASSED" if self.summary["failed"] == 0 else "FAILED"


def _write_metadata(job: Job) -> None:
    data = {
        "id": job.id,
        "mode": job.mode,
        "created_at": job.created_at.isoformat(),
        "status": job.status,
        "error": job.error,
        "result": job.result,
    }
    try:
        job.metadata_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        logger.exception("No se pudo guardar metadata.json para el job %s", job.id)


def _job_from_metadata(data: dict) -> Job:
    job = Job(
        id=data["id"],
        mode=data["mode"],
        created_at=datetime.fromisoformat(data["created_at"]),
        status=data["status"],
        error=data.get("error"),
        result=data.get("result"),
    )
    if job.status == "pending":
        # El worker que lo procesaba murió junto con el proceso anterior.
        job.status = "error"
        job.error = "Ejecución interrumpida por un reinicio del servicio."
    return job


def load_persisted_jobs() -> None:
    """Reconstruye en memoria los jobs guardados en disco. Se llama una sola
    vez al arrancar la API (lifespan)."""
    if not STORAGE_DIR.exists():
        return

    now = datetime.now(timezone.utc)
    cutoff = now - RETENTION_PERIOD
    loaded: dict[str, Job] = {}

    for job_dir in STORAGE_DIR.iterdir():
        if not job_dir.is_dir():
            continue
        metadata_path = job_dir / "metadata.json"
        if not metadata_path.exists():
            continue

        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            job = _job_from_metadata(data)
        except Exception:
            logger.exception("metadata.json inválido en %s, se omite", job_dir)
            continue

        if job.created_at < cutoff:
            shutil.rmtree(job_dir, ignore_errors=True)
            continue

        loaded[job.id] = job

    with _lock:
        _jobs.update(loaded)


def _resolve_cases(
    mode: Literal["regression", "comparison"],
    case_ids: list[str] | None,
    custom_cases: list[dict] | None,
) -> list[dict]:
    cases: list[dict] = []

    if case_ids is None and custom_cases is None:
        return load_test_cases()

    if case_ids:
        by_id = {c["case_id"]: c for c in load_test_cases()}
        missing = [cid for cid in case_ids if cid not in by_id]
        if missing:
            raise ValueError(f"Casos no encontrados en los fixtures: {', '.join(missing)}")
        cases.extend(by_id[cid] for cid in case_ids)

    if custom_cases:
        for cc in custom_cases:
            if mode == "regression" and cc.get("expected_response") is None:
                raise ValueError(
                    f"El caso personalizado '{cc.get('case_id', 'personalizado')}' "
                    "requiere 'expected_response' en modo regresión."
                )
            cases.append(cc)

    if not cases:
        raise ValueError("No hay casos para ejecutar: selecciona fixtures o agrega un payload personalizado.")

    return cases


def _create_and_submit(mode: Literal["regression", "comparison"], cases: list[dict]) -> str:
    job = Job(id=uuid.uuid4().hex, mode=mode)
    with _lock:
        _jobs[job.id] = job

    job.dir.mkdir(parents=True, exist_ok=True)
    job.resolved_cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    _write_metadata(job)

    _executor.submit(_run_job, job, cases)
    return job.id


def submit_run_job(
    mode: Literal["regression", "comparison"],
    case_ids: list[str] | None = None,
    custom_cases: list[dict] | None = None,
) -> str:
    _purge_expired_jobs()
    cases = _resolve_cases(mode, case_ids, custom_cases)
    return _create_and_submit(mode, cases)


def _run_job(job: Job, cases: list[dict]) -> None:
    try:
        job.result = asyncio.run(run_batch(job.mode, cases))
        job.status = "done"
    except Exception as e:
        logger.exception("Error ejecutando el job %s", job.id)
        job.status = "error"
        job.error = f"Error inesperado: {e}"
    _write_metadata(job)


def get_job(job_id: str) -> Job | None:
    _purge_expired_jobs()
    with _lock:
        return _jobs.get(job_id)


def list_jobs(
    *,
    mode: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    case_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Job], int]:
    _purge_expired_jobs()
    with _lock:
        jobs = list(_jobs.values())

    completed = [j for j in jobs if j.status == "done" and j.result is not None]

    if mode:
        completed = [j for j in completed if j.mode == mode]
    if status:
        completed = [j for j in completed if j.status_label.upper() == status.upper()]
    if date_from:
        completed = [j for j in completed if j.created_at.date() >= date_from]
    if date_to:
        completed = [j for j in completed if j.created_at.date() <= date_to]
    if case_id:
        needle = case_id.lower()
        completed = [j for j in completed if any(needle in c.get("case_id", "").lower() for c in j.result)]

    completed.sort(key=lambda j: j.created_at, reverse=True)

    total = len(completed)
    start = max(page - 1, 0) * page_size
    page_items = completed[start : start + page_size]
    return page_items, total


def rerun_job(job_id: str) -> str | None:
    original = get_job(job_id)
    if original is None or not original.resolved_cases_path.exists():
        return None

    cases = json.loads(original.resolved_cases_path.read_text(encoding="utf-8"))
    return _create_and_submit(original.mode, cases)
