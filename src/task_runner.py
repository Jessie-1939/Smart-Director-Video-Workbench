from __future__ import annotations

import os
from typing import Optional

from project_models import Candidate, TaskError, new_candidate
from project_store import ProjectStore
from provider_base import ImageProvider, VideoProvider
from task_queue import TaskQueue


class TaskRunner:
    def __init__(
        self,
        store: ProjectStore,
        queue: TaskQueue,
        image_provider: ImageProvider,
        video_provider: VideoProvider,
    ) -> None:
        self._store = store
        self._queue = queue
        self._image_provider = image_provider
        self._video_provider = video_provider

    def run_next(self, project_root: str) -> Optional[Candidate]:
        task = self._queue.start_next()
        if not task:
            return None

        try:
            project = self._store.load_project(project_root)
            if task.type == "image":
                candidate = self._handle_image_task(project, task)
            elif task.type == "video":
                candidate = self._handle_video_task(project, task)
            else:
                raise ValueError(f"不支持的任务类型: {task.type}")

            self._queue.mark_success(task.id)
            task.state = "succeeded"
            task.output_refs = {"candidate_id": candidate.id}
            self._store.save_task(project, task)
            return candidate
        except Exception as exc:  # pragma: no cover - defensive
            error = TaskError(code="TASK_FAILED", message=str(exc), retryable=False)
            self._queue.mark_failed(task.id, error)
            try:
                project = self._store.load_project(project_root)
                task.error = error
                task.state = "failed"
                self._store.save_task(project, task)
            except Exception:
                pass
            return None

    def _handle_image_task(self, project, task) -> Candidate:
        shot_id = str(task.input_refs.get("shot_id", ""))
        shot = self._store.load_shot(project, shot_id)
        prompt = shot.prompt
        output_dir = os.path.join(project.root_path, "candidates", task.id)
        result = self._image_provider.generate_image(prompt, output_dir)
        candidate = new_candidate(
            project_id=project.id,
            shot_id=shot.id,
            candidate_type="image",
            model=result.model,
            task_id=task.id,
            local_uri=result.local_path,
            prompt_snapshot=prompt,
        )
        self._store.add_candidate(project, candidate)
        return candidate

    def _handle_video_task(self, project, task) -> Candidate:
        shot_id = str(task.input_refs.get("shot_id", ""))
        shot = self._store.load_shot(project, shot_id)
        prompt = shot.prompt
        reference_path = str(task.input_refs.get("reference_path", "")) or None
        output_dir = os.path.join(project.root_path, "candidates", task.id)
        result = self._video_provider.generate_video(prompt, output_dir, reference_path)
        candidate = new_candidate(
            project_id=project.id,
            shot_id=shot.id,
            candidate_type="video",
            model=result.model,
            task_id=task.id,
            local_uri=result.local_path,
            prompt_snapshot=prompt,
        )
        self._store.add_candidate(project, candidate)
        return candidate
