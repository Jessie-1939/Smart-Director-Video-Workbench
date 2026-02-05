from __future__ import annotations

import json
import os
from typing import List, Optional

from project_models import (
    Asset,
    Candidate,
    Project,
    ProjectDefaults,
    Scene,
    Sequence,
    Shot,
    Task,
    new_project,
)


PROJECT_FILE = "project.json"


class ProjectStore:
    def __init__(self) -> None:
        pass

    def create_project(self, root_dir: str, name: str, defaults: Optional[ProjectDefaults] = None) -> Project:
        root_dir = os.path.abspath(root_dir)
        project_path = self._project_file_path(root_dir)
        if os.path.exists(project_path):
            raise FileExistsError(f"项目已存在: {project_path}")

        self._ensure_structure(root_dir)

        project = new_project(name=name, root_path=root_dir, defaults=defaults)
        self.save_project(project)
        return project

    def load_project(self, root_dir: str) -> Project:
        root_dir = os.path.abspath(root_dir)
        project_path = self._project_file_path(root_dir)
        if not os.path.exists(project_path):
            raise FileNotFoundError(f"未找到项目文件: {project_path}")

        with open(project_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        project = Project.from_dict(data)
        project.root_path = root_dir
        return project

    def save_project(self, project: Project) -> None:
        if not project.root_path:
            raise ValueError("project.root_path 不能为空")

        self._ensure_structure(project.root_path)
        project.touch()
        project_path = self._project_file_path(project.root_path)
        with open(project_path, "w", encoding="utf-8") as f:
            json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)

    def add_sequence(self, project: Project, sequence: Sequence) -> Sequence:
        self.save_sequence(project, sequence)
        if sequence.id not in project.sequence_ids:
            project.sequence_ids.append(sequence.id)
            self.save_project(project)
        return sequence

    def add_scene(self, project: Project, scene: Scene) -> Scene:
        self.save_scene(project, scene)
        if scene.id not in project.scene_ids:
            project.scene_ids.append(scene.id)
            self.save_project(project)
        return scene

    def add_shot(self, project: Project, shot: Shot) -> Shot:
        self.save_shot(project, shot)
        if shot.id not in project.shot_ids:
            project.shot_ids.append(shot.id)
            self.save_project(project)
        return shot

    def add_asset(self, project: Project, asset: Asset) -> Asset:
        self.save_asset(project, asset)
        if asset.id not in project.asset_ids:
            project.asset_ids.append(asset.id)
            self.save_project(project)
        return asset

    def add_candidate(self, project: Project, candidate: Candidate) -> Candidate:
        self.save_candidate(project, candidate)
        if candidate.id not in project.candidate_ids:
            project.candidate_ids.append(candidate.id)
            self.save_project(project)
        return candidate

    def add_task(self, project: Project, task: Task) -> Task:
        self.save_task(project, task)
        if task.id not in project.task_ids:
            project.task_ids.append(task.id)
            self.save_project(project)
        return task

    def save_sequence(self, project: Project, sequence: Sequence) -> None:
        sequence.touch()
        self._save_entity(project.root_path, "sequences", sequence.id, sequence.to_dict())

    def save_scene(self, project: Project, scene: Scene) -> None:
        scene.touch()
        self._save_entity(project.root_path, "scenes", scene.id, scene.to_dict())

    def save_shot(self, project: Project, shot: Shot) -> None:
        shot.touch()
        self._save_entity(project.root_path, "shots", shot.id, shot.to_dict())

    def save_asset(self, project: Project, asset: Asset) -> None:
        self._save_entity(project.root_path, "assets", asset.id, asset.to_dict())

    def save_candidate(self, project: Project, candidate: Candidate) -> None:
        self._save_entity(project.root_path, "candidates", candidate.id, candidate.to_dict())

    def save_task(self, project: Project, task: Task) -> None:
        task.touch()
        self._save_entity(project.root_path, "tasks", task.id, task.to_dict())

    def load_sequence(self, project: Project, sequence_id: str) -> Sequence:
        data = self._load_entity(project.root_path, "sequences", sequence_id)
        return Sequence.from_dict(data)

    def load_scene(self, project: Project, scene_id: str) -> Scene:
        data = self._load_entity(project.root_path, "scenes", scene_id)
        return Scene.from_dict(data)

    def load_shot(self, project: Project, shot_id: str) -> Shot:
        data = self._load_entity(project.root_path, "shots", shot_id)
        return Shot.from_dict(data)

    def load_asset(self, project: Project, asset_id: str) -> Asset:
        data = self._load_entity(project.root_path, "assets", asset_id)
        return Asset.from_dict(data)

    def load_candidate(self, project: Project, candidate_id: str) -> Candidate:
        data = self._load_entity(project.root_path, "candidates", candidate_id)
        return Candidate.from_dict(data)

    def load_task(self, project: Project, task_id: str) -> Task:
        data = self._load_entity(project.root_path, "tasks", task_id)
        return Task.from_dict(data)

    def list_entity_ids(self, project: Project, entity_type: str) -> List[str]:
        path = os.path.join(project.root_path, entity_type)
        if not os.path.exists(path):
            return []
        ids = []
        for name in os.listdir(path):
            if name.endswith(".json"):
                ids.append(name[:-5])
        return sorted(ids)

    def rebuild_index(self, project: Project) -> Project:
        """Rebuild project ID indexes by scanning entity folders on disk."""
        project.sequence_ids = self.list_entity_ids(project, "sequences")
        project.scene_ids = self.list_entity_ids(project, "scenes")
        project.shot_ids = self.list_entity_ids(project, "shots")
        project.asset_ids = self.list_entity_ids(project, "assets")
        project.candidate_ids = self.list_entity_ids(project, "candidates")
        project.task_ids = self.list_entity_ids(project, "tasks")
        self.save_project(project)
        return project

    def _project_file_path(self, root_dir: str) -> str:
        return os.path.join(root_dir, PROJECT_FILE)

    def _ensure_structure(self, root_dir: str) -> None:
        os.makedirs(root_dir, exist_ok=True)
        for sub in ["sequences", "scenes", "shots", "assets", "candidates", "tasks", "cache", "logs"]:
            os.makedirs(os.path.join(root_dir, sub), exist_ok=True)

    def _save_entity(self, root_dir: str, entity_dir: str, entity_id: str, data: dict) -> None:
        self._ensure_structure(root_dir)
        path = os.path.join(root_dir, entity_dir, f"{entity_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_entity(self, root_dir: str, entity_dir: str, entity_id: str) -> dict:
        path = os.path.join(root_dir, entity_dir, f"{entity_id}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"未找到 {entity_dir} 记录: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
