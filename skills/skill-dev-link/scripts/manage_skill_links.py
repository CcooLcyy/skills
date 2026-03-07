#!/usr/bin/env python3
"""管理 Codex skill 与 Git 仓库之间的单技能或批量软链。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

STATE_FILE_NAME = ".dev-links.json"
BACKUP_DIR_NAME = ".dev-link-backups"
DEFAULT_REPO = "CcooLcyy/skills"
DEFAULT_REF = "main"


class SkillLinkError(Exception):
    pass


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser().resolve()


def _skills_root() -> Path:
    return _codex_home() / "skills"


def _state_path(skills_root: Path) -> Path:
    return skills_root / STATE_FILE_NAME


def _backup_root(skills_root: Path) -> Path:
    return skills_root / BACKUP_DIR_NAME


def _default_repo_dir(repo: str) -> Path:
    return _codex_home() / "skill-repos" / repo.replace("/", "-")


def _build_repo_url(repo: str) -> str:
    return f"https://github.com/{repo}.git"


def _expand_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_state(path: Path) -> dict:
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


def _save_state(path: Path, data: dict) -> None:
    _ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")


def _run_git(args: list[str], cwd: Path | None = None) -> str:
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


def _is_git_repo(path: Path) -> bool:
    try:
        output = _run_git(["-C", str(path), "rev-parse", "--is-inside-work-tree"])
    except SkillLinkError:
        return False
    return output == "true"


def _validate_relative_path(path: str) -> None:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise SkillLinkError("skill 路径必须是仓库内相对路径")


def _validate_skill_dir(path: Path) -> None:
    if not path.is_dir():
        raise SkillLinkError(f"skill 目录不存在: {path}")
    if not (path / "SKILL.md").is_file():
        raise SkillLinkError(f"SKILL.md 不存在: {path}")


def _timestamp() -> str:
    return time.strftime("%Y%m%d%H%M%S")


def _next_backup_path(skills_root: Path, name: str) -> Path:
    backup_root = _backup_root(skills_root)
    _ensure_dir(backup_root)
    base = backup_root / f"{name}-{_timestamp()}"
    if not base.exists():
        return base
    index = 1
    while True:
        candidate = backup_root / f"{name}-{_timestamp()}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def _repo_source_path(repo_dir: Path, skill_path: str) -> Path:
    repo_root = repo_dir.resolve()
    candidate = (repo_root / skill_path).resolve()
    repo_prefix = str(repo_root) + os.sep
    if str(candidate) != str(repo_root) and not str(candidate).startswith(repo_prefix):
        raise SkillLinkError("skill 路径超出了仓库目录")
    return candidate


def _same_symlink_target(link_path: Path, source_path: Path) -> bool:
    if not link_path.is_symlink():
        return False
    return os.path.realpath(str(link_path)) == str(source_path.resolve())


def _resolve_default_repo_dir(args: argparse.Namespace, state: dict) -> Path:
    repo_dir = getattr(args, "repo_dir", None)
    if repo_dir:
        return _expand_path(repo_dir)
    default_repo = state.get("default_repo") or {}
    saved_repo_dir = default_repo.get("repo_dir")
    if saved_repo_dir:
        return _expand_path(saved_repo_dir)
    candidate = _default_repo_dir(DEFAULT_REPO)
    if _is_git_repo(candidate):
        return candidate
    raise SkillLinkError("未找到已登记的技能仓库，请先执行 setup 或通过 --repo-dir 指定仓库")


def _collect_default_repo_record(repo: str, repo_dir: Path, ref: str, fallback_url: str) -> dict:
    repo_url = fallback_url
    try:
        origin = _run_git(["-C", str(repo_dir), "remote", "get-url", "origin"])
        if origin:
            repo_url = origin
    except SkillLinkError:
        pass
    return {
        "repo": repo,
        "repo_url": repo_url,
        "repo_dir": str(repo_dir),
        "ref": ref,
        "updated_at": _timestamp(),
    }


def _iter_repo_skills(repo_dir: Path) -> list[tuple[str, str]]:
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


def _link_skill(state: dict, repo_dir: Path, name: str, skill_path: str) -> dict:
    skills_root = _skills_root()
    _ensure_dir(skills_root)
    _validate_relative_path(skill_path)
    source_path = _repo_source_path(repo_dir, skill_path)
    _validate_skill_dir(source_path)
    target_path = skills_root / name
    links = state.setdefault("links", {})
    old_entry = links.get(name, {})
    backup_path = old_entry.get("backup_path", "")
    new_backup_path = ""
    status = "created"

    if target_path.is_symlink():
        if _same_symlink_target(target_path, source_path):
            status = "already_linked"
        else:
            if old_entry:
                target_path.unlink()
                status = "relinked"
            else:
                raise SkillLinkError(f"目标已是未托管软链，停止覆盖: {target_path}")
    elif target_path.exists():
        backup_target = _next_backup_path(skills_root, name)
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
        "linked_at": old_entry.get("linked_at", _timestamp()),
        "updated_at": _timestamp(),
    }
    return {
        "name": name,
        "status": status,
        "target_path": str(target_path),
        "source_path": str(source_path),
        "backup_path": backup_path,
        "new_backup_path": new_backup_path,
    }


def _print_link_result(result: dict) -> None:
    name = result["name"]
    target_path = result["target_path"]
    source_path = result["source_path"]
    if result["status"] == "already_linked":
        print(f"{name}: 已链接 -> {source_path}")
        return
    if result["new_backup_path"]:
        print(f"{name}: 已备份原目录 -> {result['new_backup_path']}")
    if result["status"] == "relinked":
        print(f"{name}: 已更新软链 -> {target_path} -> {source_path}")
    else:
        print(f"{name}: 已创建软链 -> {target_path} -> {source_path}")


def _link_many(state: dict, state_path: Path, repo_dir: Path, names: list[str] | None = None) -> tuple[list[dict], list[tuple[str, str]]]:
    repo_skills = dict(_iter_repo_skills(repo_dir))
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
            result = _link_skill(state, repo_dir, name, skill_path)
            results.append(result)
            _save_state(state_path, state)
        except SkillLinkError as exc:
            errors.append((name, str(exc)))
    return results, errors


def _cmd_setup(args: argparse.Namespace) -> int:
    repo = args.repo or DEFAULT_REPO
    repo_url = args.repo_url or _build_repo_url(repo)
    repo_dir = _expand_path(args.repo_dir) if args.repo_dir else _default_repo_dir(repo)
    skills_root = _skills_root()
    state_path = _state_path(skills_root)
    _ensure_dir(skills_root)
    if repo_dir.exists():
        if not repo_dir.is_dir():
            raise SkillLinkError(f"仓库路径不是目录: {repo_dir}")
        if not _is_git_repo(repo_dir):
            raise SkillLinkError(f"现有目录不是 Git 仓库: {repo_dir}")
        action = "已登记现有仓库"
    else:
        _ensure_dir(repo_dir.parent)
        _run_git([
            "clone",
            "--depth",
            "1",
            "--single-branch",
            "--branch",
            args.ref,
            repo_url,
            str(repo_dir),
        ])
        action = "已克隆并登记仓库"

    state = _load_state(state_path)
    state["default_repo"] = _collect_default_repo_record(repo, repo_dir, args.ref, repo_url)
    _save_state(state_path, state)

    print(action)
    print(f"repo: {repo}")
    print(f"repo_dir: {repo_dir}")
    print(f"state: {state_path}")

    if args.no_link_all:
        print("已跳过默认全量链接")
        return 0

    print("开始链接仓库中的全部 skill...")
    results, errors = _link_many(state, state_path, repo_dir)
    for result in results:
        _print_link_result(result)
    for name, message in errors:
        print(f"{name}: 链接失败 - {message}", file=sys.stderr)
    return 1 if errors else 0


def _cmd_link(args: argparse.Namespace) -> int:
    skills_root = _skills_root()
    state_path = _state_path(skills_root)
    _ensure_dir(skills_root)
    state = _load_state(state_path)
    repo_dir = _resolve_default_repo_dir(args, state)
    if not _is_git_repo(repo_dir):
        raise SkillLinkError(f"仓库目录不是 Git 仓库: {repo_dir}")

    if args.all:
        results, errors = _link_many(state, state_path, repo_dir)
        for result in results:
            _print_link_result(result)
        for name, message in errors:
            print(f"{name}: 链接失败 - {message}", file=sys.stderr)
        return 1 if errors else 0

    skill_path = args.skill_path or f"skills/{args.name}"
    result = _link_skill(state, repo_dir, args.name, skill_path)
    _save_state(state_path, state)
    _print_link_result(result)
    return 0


def _link_status(target_path: Path, source_path: Path) -> str:
    if target_path.is_symlink():
        if not source_path.exists():
            return "源目录缺失"
        if _same_symlink_target(target_path, source_path):
            return "已链接"
        return "软链目标不匹配"
    if target_path.exists():
        return "目标被普通目录或文件占用"
    return "目标缺失"


def _print_status_line(name: str, entry: dict) -> None:
    target_path = Path(entry.get("target_path") or (_skills_root() / name))
    source_path_text = entry.get("source_path", "")
    source_path = Path(source_path_text) if source_path_text else Path()
    status = _link_status(target_path, source_path) if source_path_text else "无源目录记录"
    print(f"{name}: {status}")
    print(f"  target: {target_path}")
    if source_path_text:
        print(f"  source: {source_path}")
    backup_path = entry.get("backup_path")
    if backup_path:
        backup_exists = Path(backup_path).exists()
        print(f"  backup: {backup_path} ({'存在' if backup_exists else '缺失'})")


def _cmd_status(args: argparse.Namespace) -> int:
    skills_root = _skills_root()
    state_path = _state_path(skills_root)
    state = _load_state(state_path)
    default_repo = state.get("default_repo") or {}
    if default_repo:
        print("默认仓库:")
        print(f"  repo: {default_repo.get('repo', '')}")
        print(f"  repo_dir: {default_repo.get('repo_dir', '')}")
        print(f"  repo_url: {default_repo.get('repo_url', '')}")
        print(f"  ref: {default_repo.get('ref', '')}")
    else:
        print("默认仓库: 未登记")
    links = state.get("links", {})
    if args.name:
        entry = links.get(args.name)
        if entry:
            _print_status_line(args.name, entry)
            return 0
        target_path = skills_root / args.name
        if target_path.is_symlink():
            print(f"{args.name}: 未记录，但当前是软链 -> {os.path.realpath(str(target_path))}")
        elif target_path.exists():
            print(f"{args.name}: 未记录，当前是普通目录或文件")
        else:
            print(f"{args.name}: 未记录，目标不存在")
        return 0
    if not links:
        print("暂无链接记录")
        return 0
    print("链接记录:")
    for name in sorted(links.keys()):
        _print_status_line(name, links[name])
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    skills_root = _skills_root()
    state_path = _state_path(skills_root)
    state = _load_state(state_path)
    links = state.get("links", {})
    entry = links.get(args.name)
    if not entry:
        raise SkillLinkError(f"未找到链接记录: {args.name}")
    target_path = Path(entry.get("target_path") or (skills_root / args.name))
    backup_path_text = entry.get("backup_path", "")
    if target_path.is_symlink():
        target_path.unlink()
    elif target_path.exists():
        raise SkillLinkError(f"当前目标不是软链，拒绝恢复以免覆盖现有内容: {target_path}")
    restored = False
    if backup_path_text:
        backup_path = Path(backup_path_text)
        if backup_path.exists():
            shutil.move(str(backup_path), str(target_path))
            restored = True
    links.pop(args.name, None)
    _save_state(state_path, state)
    if restored:
        print(f"已恢复备份: {target_path}")
    else:
        print(f"未找到备份，仅移除软链记录: {args.name}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理 Codex skill 与 Git 仓库的单技能或批量软链")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser("setup", help="初始化或登记技能仓库，并默认链接全部 skill")
    setup_parser.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub 仓库，默认 {DEFAULT_REPO}")
    setup_parser.add_argument("--repo-url", help="显式指定克隆 URL")
    setup_parser.add_argument("--repo-dir", help="本地仓库目录")
    setup_parser.add_argument("--ref", default=DEFAULT_REF, help=f"分支或标签，默认 {DEFAULT_REF}")
    setup_parser.add_argument("--no-link-all", action="store_true", help="仅登记仓库，不自动链接全部 skill")

    link_parser = subparsers.add_parser("link", help="创建单个 skill 软链，或用 --all 批量链接全部 skill")
    link_target_group = link_parser.add_mutually_exclusive_group(required=True)
    link_target_group.add_argument("--name", help="skill 名称")
    link_target_group.add_argument("--all", action="store_true", help="链接仓库中的全部 skill")
    link_parser.add_argument("--repo-dir", help="本地仓库目录，默认读状态文件")
    link_parser.add_argument("--skill-path", help="仓库内 skill 相对路径，默认 skills/<name>")

    status_parser = subparsers.add_parser("status", help="查看当前登记与链接状态")
    status_parser.add_argument("--name", help="只查看某个 skill")

    restore_parser = subparsers.add_parser("restore", help="移除软链并恢复备份")
    restore_parser.add_argument("--name", required=True, help="skill 名称")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            return _cmd_setup(args)
        if args.command == "link":
            return _cmd_link(args)
        if args.command == "status":
            return _cmd_status(args)
        if args.command == "restore":
            return _cmd_restore(args)
        parser.print_help()
        return 1
    except SkillLinkError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
