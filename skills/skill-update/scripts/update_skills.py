#!/usr/bin/env python3
"""更新已安装的 Codex 技能。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

DEFAULT_SOURCES_NAME = ".skill-sources.json"
DEFAULT_REPO = "CcooLcyy/skills"
IGNORED_DIRS = {".git", "__pycache__"}
IGNORED_FILES = {".DS_Store"}
IGNORED_SUFFIXES = {".pyc"}


def _codex_home() -> str:
    return os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex"))


def _default_dest() -> str:
    return os.path.join(_codex_home(), "skills")


def _default_sources(dest_root: str) -> str:
    return os.path.join(dest_root, DEFAULT_SOURCES_NAME)


def _expand_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def _load_sources(path: str) -> dict:
    if not os.path.exists(path):
        return {"version": 1, "skills": {}}
    with open(path, "r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    if not isinstance(data, dict):
        raise ValueError("来源文件格式错误：顶层必须是对象")
    skills = data.get("skills")
    if skills is None:
        data["skills"] = {}
    elif not isinstance(skills, dict):
        raise ValueError("来源文件格式错误：skills 必须是对象")
    if "version" not in data:
        data["version"] = 1
    return data


def _save_sources(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")


def _validate_skill_dir(path: str) -> None:
    if not os.path.isdir(path):
        raise ValueError(f"技能目录不存在: {path}")
    skill_md = os.path.join(path, "SKILL.md")
    if not os.path.isfile(skill_md):
        raise ValueError(f"SKILL.md 不存在: {path}")


def _validate_repo_path(path: str) -> None:
    if os.path.isabs(path) or os.path.normpath(path).startswith(".."):
        raise ValueError("仓库路径必须是仓库内相对路径")


def _hash_directory(path: str) -> str:
    hasher = hashlib.sha256()
    for root, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        dirnames.sort()
        rel_root = os.path.relpath(root, path)
        if rel_root != ".":
            hasher.update(b"D")
            hasher.update(rel_root.encode("utf-8"))
        filtered = []
        for name in filenames:
            if name in IGNORED_FILES:
                continue
            if any(name.endswith(suffix) for suffix in IGNORED_SUFFIXES):
                continue
            filtered.append(name)
        for name in sorted(filtered):
            file_path = os.path.join(root, name)
            rel_path = os.path.relpath(file_path, path)
            hasher.update(b"F")
            hasher.update(rel_path.encode("utf-8"))
            if os.path.islink(file_path):
                hasher.update(b"L")
                hasher.update(os.readlink(file_path).encode("utf-8"))
                continue
            with open(file_path, "rb") as file_handle:
                while True:
                    chunk = file_handle.read(8192)
                    if not chunk:
                        break
                    hasher.update(chunk)
    return hasher.hexdigest()


def _is_same_skill(dest_path: str, new_path: str) -> bool:
    if not os.path.isdir(dest_path):
        return False
    return _hash_directory(dest_path) == _hash_directory(new_path)


def _resolve_installer_path(user_path: str | None) -> str:
    if user_path:
        installer_path = _expand_path(user_path)
    else:
        installer_path = os.path.join(
            _codex_home(),
            "skills",
            ".system",
            "skill-installer",
            "scripts",
            "install-skill-from-github.py",
        )
    if not os.path.isfile(installer_path):
        raise FileNotFoundError(
            "未找到安装脚本，请使用 --installer 指定 install-skill-from-github.py"
        )
    return installer_path


def _install_from_github(entry: dict, name: str, stage_root: str, installer_path: str) -> None:
    cmd = [sys.executable, installer_path, "--dest", stage_root, "--name", name]
    if "url" in entry:
        cmd += ["--url", entry["url"]]
    else:
        repo = entry.get("repo")
        repo_path = entry.get("path")
        if isinstance(repo_path, list):
            if len(repo_path) != 1:
                raise ValueError("来源记录的 path 只能包含一个路径")
            repo_path = repo_path[0]
        if not repo or not repo_path:
            raise ValueError("来源记录缺少 repo/path 或 url")
        _validate_repo_path(repo_path)
        cmd += ["--repo", repo, "--path", repo_path]
    ref = entry.get("ref")
    method = entry.get("method")
    if ref:
        cmd += ["--ref", ref]
    if method:
        cmd += ["--method", method]
    subprocess.run(cmd, check=True)


def _replace_skill(dest_root: str, name: str, new_path: str, keep_backup: bool) -> None:
    os.makedirs(dest_root, exist_ok=True)
    dest_path = os.path.join(dest_root, name)
    backup_path = None
    if os.path.exists(dest_path):
        timestamp = time.strftime("%Y%m%d%H%M%S")
        backup_path = f"{dest_path}.bak-{timestamp}"
        shutil.move(dest_path, backup_path)
    try:
        shutil.move(new_path, dest_path)
    except Exception:
        if backup_path and os.path.exists(backup_path) and not os.path.exists(dest_path):
            shutil.move(backup_path, dest_path)
        raise
    if backup_path and not keep_backup:
        shutil.rmtree(backup_path, ignore_errors=True)


def _update_one(name: str, entry: dict, dest_root: str, args: argparse.Namespace) -> bool:
    tmp_root = tempfile.mkdtemp(prefix="skill-update-")
    try:
        stage_root = os.path.join(tmp_root, "stage")
        os.makedirs(stage_root, exist_ok=True)
        if "local_path" in entry:
            local_path = _expand_path(entry["local_path"])
            _validate_skill_dir(local_path)
            shutil.copytree(local_path, os.path.join(stage_root, name))
        else:
            installer_path = _resolve_installer_path(args.installer)
            _install_from_github(entry, name, stage_root, installer_path)
        new_path = os.path.join(stage_root, name)
        _validate_skill_dir(new_path)
        dest_path = os.path.join(dest_root, name)
        if _is_same_skill(dest_path, new_path):
            return False
        _replace_skill(dest_root, name, new_path, args.keep_backup)
        return True
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def _cmd_add(args: argparse.Namespace, dest_root: str) -> int:
    sources_path = args.sources or _default_sources(dest_root)
    data = _load_sources(sources_path)
    skills = data.setdefault("skills", {})
    if args.local_path:
        local_path = _expand_path(args.local_path)
        _validate_skill_dir(local_path)
        entry = {"local_path": local_path}
    elif args.url:
        entry = {"url": args.url, "ref": args.ref, "method": args.method}
    else:
        repo = args.repo or DEFAULT_REPO
        if not args.path:
            if args.repo:
                raise ValueError("使用 --repo 时必须提供 --path")
            raise ValueError(f"使用默认仓库时必须提供 --path（默认: {DEFAULT_REPO}）")
        _validate_repo_path(args.path)
        entry = {
            "repo": repo,
            "path": args.path,
            "ref": args.ref,
            "method": args.method,
        }
    skills[args.name] = entry
    _save_sources(sources_path, data)
    print(f"已写入来源记录: {args.name}")
    return 0


def _cmd_list(args: argparse.Namespace, dest_root: str) -> int:
    sources_path = args.sources or _default_sources(dest_root)
    data = _load_sources(sources_path)
    skills = data.get("skills", {})
    if not skills:
        print("暂无来源记录")
        return 0
    for name in sorted(skills.keys()):
        entry = skills[name]
        if "local_path" in entry:
            print(f"{name}: 本地 {entry['local_path']}")
        elif "url" in entry:
            ref = entry.get("ref", "")
            method = entry.get("method", "")
            suffix = " ".join([item for item in [ref, method] if item])
            line = f"{name}: GitHub URL {entry['url']}"
            if suffix:
                line = f"{line} ({suffix})"
            print(line)
        else:
            ref = entry.get("ref", "")
            method = entry.get("method", "")
            suffix = " ".join([item for item in [ref, method] if item])
            line = f"{name}: GitHub {entry.get('repo')} {entry.get('path')}"
            if suffix:
                line = f"{line} ({suffix})"
            print(line)
    return 0


def _cmd_remove(args: argparse.Namespace, dest_root: str) -> int:
    sources_path = args.sources or _default_sources(dest_root)
    data = _load_sources(sources_path)
    skills = data.get("skills", {})
    removed = []
    for name in args.name:
        if name in skills:
            skills.pop(name)
            removed.append(name)
    if removed:
        _save_sources(sources_path, data)
        for name in removed:
            print(f"已移除来源记录: {name}")
    else:
        print("未找到可移除的来源记录")
    return 0


def _cmd_update(args: argparse.Namespace, dest_root: str) -> int:
    sources_path = args.sources or _default_sources(dest_root)
    if not os.path.exists(sources_path):
        print("来源文件不存在，请先使用 add 写入来源记录", file=sys.stderr)
        return 1
    data = _load_sources(sources_path)
    skills = data.get("skills", {})
    if args.all:
        targets = sorted(skills.keys())
    else:
        targets = args.name or []
    if not targets:
        print("请使用 --all 或 --name 指定更新范围", file=sys.stderr)
        return 1
    missing = [name for name in targets if name not in skills]
    for name in missing:
        print(f"来源记录缺失，跳过: {name}", file=sys.stderr)
    errors = False
    for name in targets:
        entry = skills.get(name)
        if not entry:
            continue
        try:
            updated = _update_one(name, entry, dest_root, args)
            if updated:
                print(f"更新完成: {name}")
            else:
                print(f"已是最新: {name}")
        except Exception as exc:
            errors = True
            print(f"更新失败: {name} - {exc}", file=sys.stderr)
    return 1 if errors else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="更新已安装的 Codex 技能")
    parser.add_argument(
        "--dest",
        help="技能目录，默认 $CODEX_HOME/skills",
    )
    parser.add_argument(
        "--sources",
        help="来源配置文件，默认 <dest>/.skill-sources.json",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="添加或更新来源记录")
    add_parser.add_argument("--name", required=True, help="技能名称")
    source_group = add_parser.add_mutually_exclusive_group(required=False)
    source_group.add_argument("--local-path", help="本地技能目录路径")
    source_group.add_argument(
        "--repo",
        help=f"GitHub 仓库，格式 owner/repo（默认 {DEFAULT_REPO}）",
    )
    source_group.add_argument("--url", help="GitHub URL，指向 skill 目录")
    add_parser.add_argument("--path", help="仓库内路径，用于 --repo 或默认仓库")
    add_parser.add_argument("--ref", default="main", help="分支或标签")
    add_parser.add_argument(
        "--method",
        default="auto",
        choices=["auto", "download", "git"],
        help="安装方式",
    )

    list_parser = subparsers.add_parser("list", help="列出来源记录")
    list_parser.set_defaults(command="list")

    remove_parser = subparsers.add_parser("remove", help="移除来源记录")
    remove_parser.add_argument("--name", nargs="+", required=True, help="技能名称")

    update_parser = subparsers.add_parser("update", help="更新技能")
    update_parser.add_argument("--all", action="store_true", help="更新全部记录")
    update_parser.add_argument("--name", nargs="+", help="指定技能名称")
    update_parser.add_argument(
        "--installer",
        help="install-skill-from-github.py 路径",
    )
    update_parser.add_argument(
        "--keep-backup",
        action="store_true",
        help="保留旧版本备份",
    )

    return parser


def main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    dest_root = _expand_path(args.dest) if args.dest else _default_dest()

    try:
        if args.command == "add":
            return _cmd_add(args, dest_root)
        if args.command == "list":
            return _cmd_list(args, dest_root)
        if args.command == "remove":
            return _cmd_remove(args, dest_root)
        if args.command == "update":
            return _cmd_update(args, dest_root)
        parser.print_help()
        return 1
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
