#!/usr/bin/env python3
"""技能仓库接入、软链维护与链接状态管理。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

STATE_FILE_NAME = ".dev-links.json"
BACKUP_DIR_NAME = ".dev-link-backups"
DEFAULT_REPO = "CcooLcyy/skills"
DEFAULT_REF = "main"


class SkillLinkError(Exception):
    pass


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser().resolve()


def skills_root(default_root: Path | None = None) -> Path:
    return default_root or (codex_home() / "skills")


def state_path(skills_root_path: Path | None = None) -> Path:
    return skills_root(skills_root_path) / STATE_FILE_NAME


def backup_root(skills_root_path: Path | None = None) -> Path:
    return skills_root(skills_root_path) / BACKUP_DIR_NAME


def default_repo_dir(repo: str) -> Path:
    return codex_home() / "skill-repos" / repo.replace("/", "-")


def build_repo_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


def expand_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "default_repo": {}, "links": {}}
    with path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    if not isinstance(data, dict):
        raise SkillLinkError("状态文件格式错误：顶层必须是对象")
    data.setdefault("version", 1)
    default_repo = data.get("default_repo")
    if default_repo is None:
        data["default_repo"] = {}
    elif not isinstance(default_repo, dict):
        raise SkillLinkError("状态文件格式错误：default_repo 必须是对象")
    links = data.get("links")
    if links is None:
        data["links"] = {}
    elif not isinstance(links, dict):
        raise SkillLinkError("状态文件格式错误：links 必须是对象")
    return data


def save_state(path: Path, data: dict) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")


def run_git(args: list[str], cwd: Path | None = None) -> str:
    cmd = ["git"] + args
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git 命令执行失败"
        raise SkillLinkError(message)
    return result.stdout.strip()


def is_git_repo(path: Path) -> bool:
    try:
        output = run_git(["-C", str(path), "rev-parse", "--is-inside-work-tree"])
    except SkillLinkError:
        return False
    return output == "true"


def validate_relative_path(path: str) -> None:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise SkillLinkError("skill 路径必须是仓库内相对路径")


def validate_skill_dir(path: Path) -> None:
    if not path.is_dir():
        raise SkillLinkError(f"skill 目录不存在: {path}")
    if not (path / "SKILL.md").is_file():
        raise SkillLinkError(f"SKILL.md 不存在: {path}")


def timestamp() -> str:
    return time.strftime("%Y%m%d%H%M%S")


def next_backup_path(skills_root_path: Path, name: str) -> Path:
    current_backup_root = backup_root(skills_root_path)
    ensure_dir(current_backup_root)
    base = current_backup_root / f"{name}-{timestamp()}"
    if not base.exists():
        return base
    index = 1
    while True:
        candidate = current_backup_root / f"{name}-{timestamp()}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def repo_source_path(repo_dir: Path, skill_path: str) -> Path:
    repo_root = repo_dir.resolve()
    candidate = (repo_root / skill_path).resolve()
    repo_prefix = str(repo_root) + os.sep
    if str(candidate) != str(repo_root) and not str(candidate).startswith(repo_prefix):
        raise SkillLinkError("skill 路径超出了仓库目录")
    return candidate


def same_symlink_target(link_path: Path, source_path: Path) -> bool:
    if not link_path.is_symlink():
        return False
    return os.path.realpath(str(link_path)) == str(source_path.resolve())


def resolve_default_repo_dir(repo_dir_text: str | None, state: dict) -> Path:
    if repo_dir_text:
        return expand_path(repo_dir_text)
    default_repo = state.get("default_repo") or {}
    saved_repo_dir = default_repo.get("repo_dir")
    if saved_repo_dir:
        return expand_path(saved_repo_dir)
    candidate = default_repo_dir(DEFAULT_REPO)
    if is_git_repo(candidate):
        return candidate
    raise SkillLinkError("未找到已登记的技能仓库，请先执行 connect 或通过 --repo-dir 指定仓库")


def collect_default_repo_record(repo: str, repo_dir: Path, ref: str, fallback_url: str) -> dict:
    repo_url = fallback_url
    try:
        origin = run_git(["-C", str(repo_dir), "remote", "get-url", "origin"])
        if origin:
            repo_url = origin
    except SkillLinkError:
        pass
    return {
        "repo": repo,
        "repo_url": repo_url,
        "repo_dir": str(repo_dir),
        "ref": ref,
        "updated_at": timestamp(),
    }


def iter_repo_skills(repo_dir: Path) -> list[tuple[str, str]]:
    skills_dir = repo_dir / "skills"
    if not skills_dir.is_dir():
        raise SkillLinkError(f"仓库中未找到 skills 目录: {skills_dir}")
    result = []
    for child in sorted(skills_dir.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        if (child / "SKILL.md").is_file():
            result.append((child.name, f"skills/{child.name}"))
    if not result:
        raise SkillLinkError(f"仓库中未找到可链接的 skill: {skills_dir}")
    return result


def link_skill(
    state: dict,
    repo_dir: Path,
    name: str,
    skill_path: str,
    skills_root_path: Path | None = None,
) -> dict:
    current_skills_root = skills_root(skills_root_path)
    ensure_dir(current_skills_root)
    validate_relative_path(skill_path)
    source_path = repo_source_path(repo_dir, skill_path)
    validate_skill_dir(source_path)
    target_path = current_skills_root / name
    links = state.setdefault("links", {})
    old_entry = links.get(name, {})
    backup_path = old_entry.get("backup_path", "")
    new_backup_path = ""
    status = "created"

    if target_path.is_symlink():
        if same_symlink_target(target_path, source_path):
            status = "already_linked"
        else:
            if old_entry:
                target_path.unlink()
                status = "relinked"
            else:
                raise SkillLinkError(f"目标已是未托管软链，停止覆盖: {target_path}")
    elif target_path.exists():
        backup_target = next_backup_path(current_skills_root, name)
        shutil.move(str(target_path), str(backup_target))
        backup_path = str(backup_target)
        new_backup_path = str(backup_target)

    if status != "already_linked":
        try:
            os.symlink(str(source_path), str(target_path))
        except Exception as exc:
            if new_backup_path and not os.path.lexists(target_path):
                backup_candidate = Path(new_backup_path)
                if backup_candidate.exists():
                    shutil.move(str(backup_candidate), str(target_path))
            raise SkillLinkError(f"创建软链失败: {exc}")

    links[name] = {
        "name": name,
        "repo_dir": str(repo_dir),
        "skill_path": skill_path,
        "source_path": str(source_path),
        "target_path": str(target_path),
        "backup_path": backup_path,
        "linked_at": old_entry.get("linked_at", timestamp()),
        "updated_at": timestamp(),
    }
    return {
        "name": name,
        "status": status,
        "target_path": str(target_path),
        "source_path": str(source_path),
        "backup_path": backup_path,
        "new_backup_path": new_backup_path,
    }


def link_many(
    state: dict,
    state_file: Path,
    repo_dir: Path,
    skills_root_path: Path | None = None,
    names: list[str] | None = None,
) -> tuple[list[dict], list[tuple[str, str]]]:
    repo_skills = dict(iter_repo_skills(repo_dir))
    if names:
        selected = []
        errors = []
        for name in names:
            skill_path = repo_skills.get(name)
            if not skill_path:
                errors.append((name, f"仓库中未找到 skill: skills/{name}"))
                continue
            selected.append((name, skill_path))
    else:
        selected = sorted(repo_skills.items())
        errors = []

    results = []
    for name, skill_path in selected:
        try:
            result = link_skill(
                state,
                repo_dir,
                name,
                skill_path,
                skills_root_path=skills_root_path,
            )
            results.append(result)
            save_state(state_file, state)
        except SkillLinkError as exc:
            errors.append((name, str(exc)))
    return results, errors


def link_status(target_path: Path, source_path: Path) -> str:
    if target_path.is_symlink():
        if not source_path.exists():
            return "源目录缺失"
        if same_symlink_target(target_path, source_path):
            return "已链接"
        return "软链目标不匹配"
    if target_path.exists():
        return "目标被普通目录或文件占用"
    return "目标缺失"


def status_snapshot(name: str, entry: dict, skills_root_path: Path | None = None) -> dict:
    current_skills_root = skills_root(skills_root_path)
    target_path = Path(entry.get("target_path") or (current_skills_root / name))
    source_path_text = entry.get("source_path", "")
    source_path = Path(source_path_text) if source_path_text else Path()
    backup_path = entry.get("backup_path", "")
    return {
        "name": name,
        "status": link_status(target_path, source_path) if source_path_text else "无源目录记录",
        "target_path": str(target_path),
        "source_path": source_path_text,
        "backup_path": backup_path,
        "backup_exists": Path(backup_path).exists() if backup_path else None,
    }


def restore_link(
    state: dict,
    state_file: Path,
    name: str,
    skills_root_path: Path | None = None,
) -> dict:
    current_skills_root = skills_root(skills_root_path)
    links = state.get("links", {})
    entry = links.get(name)
    if not entry:
        raise SkillLinkError(f"未找到链接记录: {name}")
    target_path = Path(entry.get("target_path") or (current_skills_root / name))
    backup_path_text = entry.get("backup_path", "")
    if target_path.is_symlink():
        target_path.unlink()
    elif target_path.exists():
        raise SkillLinkError(f"当前目标不是软链，拒绝恢复以免覆盖现有内容: {target_path}")
    restored = False
    if backup_path_text:
        backup_path_value = Path(backup_path_text)
        if backup_path_value.exists():
            shutil.move(str(backup_path_value), str(target_path))
            restored = True
    links.pop(name, None)
    save_state(state_file, state)
    return {
        "name": name,
        "target_path": str(target_path),
        "restored": restored,
        "backup_path": backup_path_text,
    }
