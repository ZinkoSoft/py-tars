from __future__ import annotations

import asyncio
from functools import partial
from typing import Optional

from .events import DatasetEvent, DatasetEventType, EventHub
from .jobs import JobStorage, TrainingJob, TrainingJobStatus
from .storage import DatasetStorage
from .models import DatasetMetrics


class TrainingJobRunner:
    """In-process executor that simulates training job lifecycle transitions.

    Real GPU training will replace the `_run_job` stub. For now we immediately
    transition queued jobs to running and then completed while emitting
    WebSocket events and persisting status updates.
    """

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
            task.add_done_callback(partial(self._tasks.pop, job.id, None))
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

            # Placeholder for GPU fine-tune: insert actual training pipeline here.
            await asyncio.sleep(0)

            job = self._job_storage.update_status(job_id, TrainingJobStatus.completed)
            await self._log(job_id, "Job completed successfully", dataset=job.dataset)
            metrics = self._storage.get_metrics(job.dataset)
            await self._event_hub.publish(
                DatasetEvent(
                    type=DatasetEventType.job_completed,
                    dataset=job.dataset,
                    job_id=job.id,
                    metrics=metrics,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            job: Optional[TrainingJob] = None
            try:
                job = self._job_storage.update_status(
                    job_id,
                    TrainingJobStatus.failed,
                    error=str(exc),
                )
                await self._log(job_id, f"Job failed: {exc}", dataset=job.dataset)
            except FileNotFoundError:
                pass

            dataset_name = job.dataset if job else "unknown"
            metrics = None
            if job:
                try:
                    metrics = self._storage.get_metrics(dataset_name)
                except FileNotFoundError:
                    metrics = None

            await self._event_hub.publish(
                DatasetEvent(
                    type=DatasetEventType.job_failed,
                    dataset=dataset_name,
                    job_id=job_id,
                    metrics=metrics,
                )
            )
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