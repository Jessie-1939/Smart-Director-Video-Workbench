from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

from project_models import Task, TaskError


@dataclass
class QueueStats:
    queued: int
    running: int
    succeeded: int
    failed: int
    cancelled: int


class TaskQueue:
    def __init__(self, max_running: int = 1):
        if max_running < 1:
            raise ValueError("max_running 必须 >= 1")
        self.max_running = max_running
        self._queued: Deque[Task] = deque()
        self._running: Dict[str, Task] = {}
        self._done: Dict[str, Task] = {}

    def enqueue(self, task: Task) -> None:
        task.state = "queued"
        self._queued.append(task)

    def start_next(self) -> Optional[Task]:
        if len(self._running) >= self.max_running:
            return None
        if not self._queued:
            return None
        task = self._queued.popleft()
        task.state = "running"
        self._running[task.id] = task
        return task

    def mark_success(self, task_id: str) -> Optional[Task]:
        task = self._running.pop(task_id, None)
        if not task:
            return None
        task.state = "succeeded"
        self._done[task.id] = task
        return task

    def mark_failed(self, task_id: str, error: TaskError) -> Optional[Task]:
        task = self._running.pop(task_id, None)
        if not task:
            return None
        task.state = "failed"
        task.error = error
        self._done[task.id] = task
        return task

    def cancel(self, task_id: str) -> bool:
        for idx, task in enumerate(self._queued):
            if task.id == task_id:
                task.state = "cancelled"
                self._queued.remove(task)
                self._done[task.id] = task
                return True
        task = self._running.pop(task_id, None)
        if task:
            task.state = "cancelled"
            self._done[task.id] = task
            return True
        return False

    def stats(self) -> QueueStats:
        queued = len(self._queued)
        running = len(self._running)
        succeeded = len([t for t in self._done.values() if t.state == "succeeded"])
        failed = len([t for t in self._done.values() if t.state == "failed"])
        cancelled = len([t for t in self._done.values() if t.state == "cancelled"])
        return QueueStats(
            queued=queued,
            running=running,
            succeeded=succeeded,
            failed=failed,
            cancelled=cancelled,
        )
