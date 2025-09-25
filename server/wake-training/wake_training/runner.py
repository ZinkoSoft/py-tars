from __future__ import annotations

import asyncio
import concurrent.futures
from functools import partial
from typing import Any, Optional, TYPE_CHECKING

from .events import DatasetEvent, DatasetEventType, EventHub
from .jobs import JobStorage, TrainingJob, TrainingJobStatus
from .models import DatasetMetrics
from .storage import DatasetStorage

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .trainer import TrainingResult
else:  # pragma: no cover - runtime fallback type
    TrainingResult = Any  # type: ignore[misc]

try:
    from .trainer import TrainingError, run_training_job
except ModuleNotFoundError as exc:  # pragma: no cover - missing optional dependency
    TRAINING_PIPELINE_AVAILABLE = False

    class TrainingError(RuntimeError):
        """Raised when the wake-word trainer cannot be imported."""

        pass

    def run_training_job(*args: Any, **kwargs: Any) -> Any:
        raise TrainingError(
            "Wake training requires PyTorch (torch==2.2.2). Install the dependency to enable training.",
        ) from exc

else:
    TRAINING_PIPELINE_AVAILABLE = True


class TrainingJobRunner:
    """In-process executor that orchestrates wake-word training jobs."""

    def __init__(
        self,
        storage: DatasetStorage,
        job_storage: JobStorage,
        event_hub: EventHub,
    ) -> None:
        self._storage = storage
        self._job_storage = job_storage
        self._event_hub = event_hub
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    def update_handles(
        self,
        storage: DatasetStorage,
        job_storage: JobStorage,
        event_hub: EventHub,
    ) -> None:
        self._storage = storage
        self._job_storage = job_storage
        self._event_hub = event_hub

    async def resume_queued_jobs(self) -> None:
        jobs = self._job_storage.list_jobs()
        for job in jobs:
            if job.status == TrainingJobStatus.queued:
                await self.enqueue(job)

    async def enqueue(self, job: TrainingJob) -> None:
        async with self._lock:
            if job.id in self._tasks:
                return
            task = asyncio.create_task(self._run_job(job.id))
            def _drop_task(_: asyncio.Task[None]) -> None:
                self._tasks.pop(job.id, None)

            task.add_done_callback(_drop_task)
            self._tasks[job.id] = task

    async def _run_job(self, job_id: str) -> None:
        try:
            job = self._job_storage.update_status(job_id, TrainingJobStatus.running)
            await self._log(job_id, "Job started; transitioning to running", dataset=job.dataset)
            metrics = self._storage.get_metrics(job.dataset)
            await self._event_hub.publish(
                DatasetEvent(
                    type=DatasetEventType.job_running,
                    dataset=job.dataset,
                    job_id=job.id,
                    metrics=metrics,
                )
            )

            if not TRAINING_PIPELINE_AVAILABLE:
                raise TrainingError(
                    "Wake training pipeline unavailable. Install PyTorch to enable training.",
                )

            dataset_detail = self._storage.get_dataset(job.dataset)
            job_dir = self._job_storage.jobs_root / job_id
            loop = asyncio.get_running_loop()
            log_futures: list[concurrent.futures.Future[None]] = []

            def log_callback(message: str) -> None:
                future = asyncio.run_coroutine_threadsafe(
                    self._log(job_id, message, dataset=job.dataset),
                    loop,
                )
                log_futures.append(future)

            try:
                training_result: TrainingResult = await asyncio.to_thread(
                    run_training_job,
                    dataset_dir=dataset_detail.path,
                    job_dir=job_dir,
                    dataset_name=job.dataset,
                    overrides=job.config or {},
                    log=log_callback,
                )
            except Exception:
                await _drain_futures(log_futures)
                raise
            else:
                await _drain_futures(log_futures)

            metadata_update = training_result.metadata()
            job = self._job_storage.update_status(
                job_id,
                TrainingJobStatus.completed,
                metadata=metadata_update,
            )

            await self._log(
                job_id,
                f"Job completed successfully. Artifacts stored at {training_result.export_dir}",
                dataset=job.dataset,
            )

            summary = ", ".join(
                f"{key}={value:.3f}" for key, value in sorted(training_result.metrics.items())
            )
            if summary:
                await self._log(
                    job_id,
                    f"Validation metrics: {summary}",
                    dataset=job.dataset,
                )

            metrics = self._storage.get_metrics(job.dataset)
            await self._event_hub.publish(
                DatasetEvent(
                    type=DatasetEventType.job_completed,
                    dataset=job.dataset,
                    job_id=job.id,
                    metrics=metrics,
                )
            )
        except TrainingError as exc:
            await self._handle_failure(job_id, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            await self._handle_failure(job_id, str(exc))
            raise

    async def _log(self, job_id: str, message: str, *, dataset: Optional[str] = None) -> None:
        try:
            chunk = self._job_storage.append_log(job_id, message)
        except FileNotFoundError:  # pragma: no cover - defensive
            return

        dataset_name = dataset
        if dataset_name is None:
            try:
                job = self._job_storage.get_job(job_id)
            except FileNotFoundError:  # pragma: no cover - defensive
                return
            dataset_name = job.dataset

        try:
            metrics = self._storage.get_metrics(dataset_name)
        except FileNotFoundError:  # pragma: no cover - defensive
            metrics = DatasetMetrics(name=dataset_name)

        await self._event_hub.publish(
            DatasetEvent(
                type=DatasetEventType.job_log,
                dataset=dataset_name,
                job_id=job_id,
                metrics=metrics,
                log_chunk=chunk,
            )
        )

    async def _handle_failure(self, job_id: str, error: str) -> None:
        job: Optional[TrainingJob] = None
        try:
            job = self._job_storage.update_status(
                job_id,
                TrainingJobStatus.failed,
                error=error,
            )
        except FileNotFoundError:  # pragma: no cover - defensive
            job = None

        dataset_name = job.dataset if job else "unknown"
        await self._log(job_id, f"Job failed: {error}", dataset=dataset_name if job else None)

        try:
            metrics = self._storage.get_metrics(dataset_name)
        except FileNotFoundError:  # pragma: no cover - defensive
            metrics = DatasetMetrics(name=dataset_name)

        await self._event_hub.publish(
            DatasetEvent(
                type=DatasetEventType.job_failed,
                dataset=dataset_name,
                job_id=job_id,
                metrics=metrics,
            )
        )


async def _drain_futures(
    futures: list[concurrent.futures.Future[None]],
) -> None:
    for future in futures:
        try:
            await asyncio.wrap_future(future)
        except Exception:  # pragma: no cover - defensive
            pass