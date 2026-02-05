from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid


SCHEMA_VERSION = "1.0.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class ProjectDefaults:
    aspect_ratio: str = "16:9"
    fps: int = 24
    resolution_preset: str = "1080p"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "ProjectDefaults":
        return ProjectDefaults(
            aspect_ratio=str(data.get("aspect_ratio", "16:9")),
            fps=int(data.get("fps", 24)),
            resolution_preset=str(data.get("resolution_preset", "1080p")),
        )


@dataclass
class Project:
    id: str
    schema_version: str
    name: str
    root_path: str
    created_at: str
    updated_at: str
    defaults: ProjectDefaults = field(default_factory=ProjectDefaults)
    sequence_ids: List[str] = field(default_factory=list)
    scene_ids: List[str] = field(default_factory=list)
    shot_ids: List[str] = field(default_factory=list)
    asset_ids: List[str] = field(default_factory=list)
    candidate_ids: List[str] = field(default_factory=list)
    task_ids: List[str] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "schema_version": self.schema_version,
            "name": self.name,
            "root_path": self.root_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "defaults": self.defaults.to_dict(),
            "sequence_ids": list(self.sequence_ids),
            "scene_ids": list(self.scene_ids),
            "shot_ids": list(self.shot_ids),
            "asset_ids": list(self.asset_ids),
            "candidate_ids": list(self.candidate_ids),
            "task_ids": list(self.task_ids),
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Project":
        defaults = ProjectDefaults.from_dict(data.get("defaults", {}) or {})
        return Project(
            id=str(data.get("id", new_id())),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            name=str(data.get("name", "Untitled Project")),
            root_path=str(data.get("root_path", "")),
            created_at=str(data.get("created_at", _now_iso())),
            updated_at=str(data.get("updated_at", _now_iso())),
            defaults=defaults,
            sequence_ids=list(data.get("sequence_ids", []) or []),
            scene_ids=list(data.get("scene_ids", []) or []),
            shot_ids=list(data.get("shot_ids", []) or []),
            asset_ids=list(data.get("asset_ids", []) or []),
            candidate_ids=list(data.get("candidate_ids", []) or []),
            task_ids=list(data.get("task_ids", []) or []),
        )


def new_project(name: str, root_path: str, defaults: Optional[ProjectDefaults] = None) -> Project:
    now = _now_iso()
    return Project(
        id=new_id(),
        schema_version=SCHEMA_VERSION,
        name=name,
        root_path=root_path,
        created_at=now,
        updated_at=now,
        defaults=defaults or ProjectDefaults(),
    )


@dataclass
class Sequence:
    id: str
    project_id: str
    name: str
    order: int
    fps: int
    aspect_ratio: str
    clip_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "order": self.order,
            "fps": self.fps,
            "aspect_ratio": self.aspect_ratio,
            "clip_ids": list(self.clip_ids),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Sequence":
        return Sequence(
            id=str(data.get("id", new_id())),
            project_id=str(data.get("project_id", "")),
            name=str(data.get("name", "Untitled Sequence")),
            order=int(data.get("order", 0)),
            fps=int(data.get("fps", 24)),
            aspect_ratio=str(data.get("aspect_ratio", "16:9")),
            clip_ids=list(data.get("clip_ids", []) or []),
            created_at=str(data.get("created_at", _now_iso())),
            updated_at=str(data.get("updated_at", _now_iso())),
        )


@dataclass
class Scene:
    id: str
    project_id: str
    sequence_id: str
    name: str
    order: int
    synopsis: str = ""
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "sequence_id": self.sequence_id,
            "name": self.name,
            "order": self.order,
            "synopsis": self.synopsis,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Scene":
        return Scene(
            id=str(data.get("id", new_id())),
            project_id=str(data.get("project_id", "")),
            sequence_id=str(data.get("sequence_id", "")),
            name=str(data.get("name", "Untitled Scene")),
            order=int(data.get("order", 0)),
            synopsis=str(data.get("synopsis", "")),
            created_at=str(data.get("created_at", _now_iso())),
            updated_at=str(data.get("updated_at", _now_iso())),
        )


@dataclass
class ShotParams:
    shot_type: str = ""
    camera_motion: str = ""
    lighting: str = ""
    style: str = ""
    duration_sec: float = 4.0
    resolution_preset: str = "1080p"
    seed: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "shot_type": self.shot_type,
            "camera_motion": self.camera_motion,
            "lighting": self.lighting,
            "style": self.style,
            "duration_sec": self.duration_sec,
            "resolution_preset": self.resolution_preset,
            "seed": self.seed,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "ShotParams":
        return ShotParams(
            shot_type=str(data.get("shot_type", "")),
            camera_motion=str(data.get("camera_motion", "")),
            lighting=str(data.get("lighting", "")),
            style=str(data.get("style", "")),
            duration_sec=float(data.get("duration_sec", 4.0)),
            resolution_preset=str(data.get("resolution_preset", "1080p")),
            seed=data.get("seed"),
        )


@dataclass
class Shot:
    id: str
    project_id: str
    sequence_id: str
    scene_id: str
    order: int
    prompt: str
    params: ShotParams = field(default_factory=ShotParams)
    reference_asset_ids: List[str] = field(default_factory=list)
    selected_candidate_id: str = ""
    status: str = "draft"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "sequence_id": self.sequence_id,
            "scene_id": self.scene_id,
            "order": self.order,
            "prompt": self.prompt,
            "params": self.params.to_dict(),
            "reference_asset_ids": list(self.reference_asset_ids),
            "selected_candidate_id": self.selected_candidate_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Shot":
        params = ShotParams.from_dict(data.get("params", {}) or {})
        return Shot(
            id=str(data.get("id", new_id())),
            project_id=str(data.get("project_id", "")),
            sequence_id=str(data.get("sequence_id", "")),
            scene_id=str(data.get("scene_id", "")),
            order=int(data.get("order", 0)),
            prompt=str(data.get("prompt", "")),
            params=params,
            reference_asset_ids=list(data.get("reference_asset_ids", []) or []),
            selected_candidate_id=str(data.get("selected_candidate_id", "")),
            status=str(data.get("status", "draft")),
            created_at=str(data.get("created_at", _now_iso())),
            updated_at=str(data.get("updated_at", _now_iso())),
        )


@dataclass
class Asset:
    id: str
    project_id: str
    type: str
    local_uri: str
    sha256: str = ""
    tags: List[str] = field(default_factory=list)
    width: int = 0
    height: int = 0
    duration_sec: float = 0.0
    source: str = "imported"
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "type": self.type,
            "local_uri": self.local_uri,
            "sha256": self.sha256,
            "tags": list(self.tags),
            "width": self.width,
            "height": self.height,
            "duration_sec": self.duration_sec,
            "source": self.source,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Asset":
        return Asset(
            id=str(data.get("id", new_id())),
            project_id=str(data.get("project_id", "")),
            type=str(data.get("type", "image")),
            local_uri=str(data.get("local_uri", "")),
            sha256=str(data.get("sha256", "")),
            tags=list(data.get("tags", []) or []),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            duration_sec=float(data.get("duration_sec", 0.0)),
            source=str(data.get("source", "imported")),
            created_at=str(data.get("created_at", _now_iso())),
        )


@dataclass
class Candidate:
    id: str
    project_id: str
    shot_id: str
    type: str
    model: str
    task_id: str
    local_uri: str
    prompt_snapshot: str
    params_snapshot: Dict[str, object] = field(default_factory=dict)
    seed: Optional[int] = None
    score: float = 0.0
    status: str = "ready"
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "shot_id": self.shot_id,
            "type": self.type,
            "model": self.model,
            "task_id": self.task_id,
            "local_uri": self.local_uri,
            "prompt_snapshot": self.prompt_snapshot,
            "params_snapshot": dict(self.params_snapshot),
            "seed": self.seed,
            "score": self.score,
            "status": self.status,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Candidate":
        return Candidate(
            id=str(data.get("id", new_id())),
            project_id=str(data.get("project_id", "")),
            shot_id=str(data.get("shot_id", "")),
            type=str(data.get("type", "image")),
            model=str(data.get("model", "")),
            task_id=str(data.get("task_id", "")),
            local_uri=str(data.get("local_uri", "")),
            prompt_snapshot=str(data.get("prompt_snapshot", "")),
            params_snapshot=dict(data.get("params_snapshot", {}) or {}),
            seed=data.get("seed"),
            score=float(data.get("score", 0.0)),
            status=str(data.get("status", "ready")),
            created_at=str(data.get("created_at", _now_iso())),
        )


@dataclass
class TaskError:
    code: str
    message: str
    retryable: bool = False
    provider: str = ""
    model: str = ""
    trace_id: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "provider": self.provider,
            "model": self.model,
            "trace_id": self.trace_id,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "TaskError":
        return TaskError(
            code=str(data.get("code", "")),
            message=str(data.get("message", "")),
            retryable=bool(data.get("retryable", False)),
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            trace_id=str(data.get("trace_id", "")),
        )


@dataclass
class Task:
    id: str
    project_id: str
    type: str
    model: str
    state: str
    input_refs: Dict[str, object]
    request_payload: Dict[str, object] = field(default_factory=dict)
    provider_task_id: str = ""
    progress: float = 0.0
    retry_count: int = 0
    priority: str = "P1"
    error: Optional[TaskError] = None
    output_refs: Dict[str, object] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "type": self.type,
            "model": self.model,
            "state": self.state,
            "input_refs": dict(self.input_refs),
            "request_payload": dict(self.request_payload),
            "provider_task_id": self.provider_task_id,
            "progress": self.progress,
            "retry_count": self.retry_count,
            "priority": self.priority,
            "error": self.error.to_dict() if self.error else None,
            "output_refs": dict(self.output_refs),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Task":
        error_raw = data.get("error")
        error = TaskError.from_dict(error_raw) if isinstance(error_raw, dict) else None
        return Task(
            id=str(data.get("id", new_id())),
            project_id=str(data.get("project_id", "")),
            type=str(data.get("type", "")),
            model=str(data.get("model", "")),
            state=str(data.get("state", "queued")),
            input_refs=dict(data.get("input_refs", {}) or {}),
            request_payload=dict(data.get("request_payload", {}) or {}),
            provider_task_id=str(data.get("provider_task_id", "")),
            progress=float(data.get("progress", 0.0)),
            retry_count=int(data.get("retry_count", 0)),
            priority=str(data.get("priority", "P1")),
            error=error,
            output_refs=dict(data.get("output_refs", {}) or {}),
            created_at=str(data.get("created_at", _now_iso())),
            updated_at=str(data.get("updated_at", _now_iso())),
        )


def new_sequence(project_id: str, name: str, order: int, defaults: ProjectDefaults) -> Sequence:
    return Sequence(
        id=new_id(),
        project_id=project_id,
        name=name,
        order=order,
        fps=defaults.fps,
        aspect_ratio=defaults.aspect_ratio,
    )


def new_scene(project_id: str, sequence_id: str, name: str, order: int) -> Scene:
    return Scene(
        id=new_id(),
        project_id=project_id,
        sequence_id=sequence_id,
        name=name,
        order=order,
    )


def new_shot(project_id: str, sequence_id: str, scene_id: str, order: int, prompt: str) -> Shot:
    return Shot(
        id=new_id(),
        project_id=project_id,
        sequence_id=sequence_id,
        scene_id=scene_id,
        order=order,
        prompt=prompt,
    )


def new_asset(project_id: str, asset_type: str, local_uri: str) -> Asset:
    return Asset(
        id=new_id(),
        project_id=project_id,
        type=asset_type,
        local_uri=local_uri,
    )


def new_candidate(
    project_id: str,
    shot_id: str,
    candidate_type: str,
    model: str,
    task_id: str,
    local_uri: str,
    prompt_snapshot: str,
) -> Candidate:
    return Candidate(
        id=new_id(),
        project_id=project_id,
        shot_id=shot_id,
        type=candidate_type,
        model=model,
        task_id=task_id,
        local_uri=local_uri,
        prompt_snapshot=prompt_snapshot,
    )


def new_task(project_id: str, task_type: str, model: str, input_refs: Dict[str, object]) -> Task:
    return Task(
        id=new_id(),
        project_id=project_id,
        type=task_type,
        model=model,
        state="queued",
        input_refs=input_refs,
    )
