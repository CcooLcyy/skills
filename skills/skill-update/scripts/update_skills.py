#!/usr/bin/env python3
"""统一管理已安装 Codex 技能的更新、接入与同步。"""

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
from pathlib import Path

import link_ops
import repo_ops

DEFAULT_SOURCES_NAME = ".skill-sources.json"
DEFAULT_REPO = link_ops.DEFAULT_REPO
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


def _remove_path(path: str) -> None:
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=True)
        return
    if os.path.lexists(path):
        os.remove(path)


def _replace_skill(dest_root: str, name: str, new_path: str, keep_backup: bool) -> None:
    os.makedirs(dest_root, exist_ok=True)
    dest_path = os.path.join(dest_root, name)
    backup_path = None
    if os.path.lexists(dest_path):
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
        _remove_path(backup_path)


def _is_linked_skill(dest_root: str, name: str) -> bool:
    dest_path = os.path.join(dest_root, name)
    return os.path.islink(dest_path)


def _installed_skill_state(dest_root: str, name: str) -> dict:
    dest_path = Path(dest_root) / name
    if dest_path.is_symlink():
        return {
            "state": "软链",
            "path": str(dest_path),
            "target": os.path.realpath(str(dest_path)),
        }
    if dest_path.is_dir():
        return {"state": "已安装", "path": str(dest_path)}
    if dest_path.exists():
        return {"state": "路径被文件占用", "path": str(dest_path)}
    return {"state": "未安装", "path": str(dest_path)}


def _format_source_entry(name: str, entry: dict) -> str:
    if "local_path" in entry:
        return f"{name}: 本地 {entry['local_path']}"
    if "url" in entry:
        ref = entry.get("ref", "")
        method = entry.get("method", "")
        suffix = " ".join([item for item in [ref, method] if item])
        line = f"{name}: GitHub URL {entry['url']}"
        if suffix:
            line = f"{line} ({suffix})"
        return line
    ref = entry.get("ref", "")
    method = entry.get("method", "")
    suffix = " ".join([item for item in [ref, method] if item])
    line = f"{name}: GitHub {entry.get('repo')} {entry.get('path')}"
    if suffix:
        line = f"{line} ({suffix})"
    return line


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


def _print_source_details(name: str, entry: dict, dest_root: str) -> None:
    print("来源记录:")
    print(f"  { _format_source_entry(name, entry) }")
    install_state = _installed_skill_state(dest_root, name)
    print("当前安装状态:")
    print(f"  state: {install_state['state']}")
    print(f"  path: {install_state['path']}")
    if install_state.get("target"):
        print(f"  target: {install_state['target']}")


def _update_one(name: str, entry: dict, dest_root: str, args: argparse.Namespace) -> bool:
    dest_path = os.path.join(dest_root, name)
    if _is_linked_skill(dest_root, name):
        raise ValueError(
            f"技能当前是软链，不能执行覆盖更新: {dest_path}；请改用 status/sync/pull/push，如软链丢失可再用 connect 重新连接"
        )
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
        if _is_same_skill(dest_path, new_path):
            return False
        _replace_skill(dest_root, name, new_path, args.keep_backup)
        return True
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def _cmd_source_add(args: argparse.Namespace, dest_root: str) -> int:
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


def _cmd_source_list(args: argparse.Namespace, dest_root: str) -> int:
    sources_path = args.sources or _default_sources(dest_root)
    data = _load_sources(sources_path)
    skills = data.get("skills", {})
    if not skills:
        print("暂无来源记录")
        return 0
    for name in sorted(skills.keys()):
        print(_format_source_entry(name, skills[name]))
    return 0


def _cmd_source_remove(args: argparse.Namespace, dest_root: str) -> int:
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
        print("来源文件不存在，请先使用 source-add 写入来源记录", file=sys.stderr)
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


def _cmd_connect(args: argparse.Namespace, dest_root: str) -> int:
    skills_root_path = Path(dest_root)
    link_ops.ensure_dir(skills_root_path)
    state_file = link_ops.state_path(skills_root_path)
    repo = args.repo or link_ops.DEFAULT_REPO
    repo_url = args.repo_url or link_ops.build_repo_url(repo)
    repo_dir = link_ops.expand_path(args.repo_dir) if args.repo_dir else link_ops.default_repo_dir(repo)

    if repo_dir.exists():
        if not repo_dir.is_dir():
            raise link_ops.SkillLinkError(f"仓库路径不是目录: {repo_dir}")
        if not link_ops.is_git_repo(repo_dir):
            raise link_ops.SkillLinkError(f"现有目录不是 Git 仓库: {repo_dir}")
        action = "已登记现有仓库"
    else:
        link_ops.ensure_dir(repo_dir.parent)
        link_ops.run_git(
            [
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--branch",
                args.ref,
                repo_url,
                str(repo_dir),
            ]
        )
        action = "已克隆并登记仓库"

    state = link_ops.load_state(state_file)
    state["default_repo"] = link_ops.collect_default_repo_record(repo, repo_dir, args.ref, repo_url)
    link_ops.save_state(state_file, state)

    print(action)
    print(f"repo: {repo}")
    print(f"repo_dir: {repo_dir}")
    print(f"state: {state_file}")

    if args.no_link:
        print("已跳过链接")
        return 0

    selected_names = [args.name] if args.name else None
    if args.name:
        print(f"开始链接 skill: {args.name}")
    else:
        print("开始链接仓库中的全部 skill...")
    results, errors = link_ops.link_many(
        state,
        state_file,
        repo_dir,
        skills_root_path=skills_root_path,
        names=selected_names,
    )
    for result in results:
        _print_link_result(result)
    for name, message in errors:
        print(f"{name}: 链接失败 - {message}", file=sys.stderr)
    return 1 if errors else 0


def _cmd_status(args: argparse.Namespace, dest_root: str) -> int:
    skills_root_path = Path(dest_root)
    state = link_ops.load_state(link_ops.state_path(skills_root_path))
    sources = _load_sources(args.sources or _default_sources(dest_root))
    links = state.get("links", {})
    source_skills = sources.get("skills", {})

    if args.name:
        entry = links.get(args.name)
        if entry:
            snapshot = link_ops.status_snapshot(args.name, entry, skills_root_path=skills_root_path)
            print("接入记录:")
            print(f"  skill: {args.name}")
            print(f"  status: {snapshot['status']}")
            print(f"  target: {snapshot['target_path']}")
            if snapshot["source_path"]:
                print(f"  source: {snapshot['source_path']}")
            if snapshot["backup_path"]:
                backup_state = "存在" if snapshot["backup_exists"] else "缺失"
                print(f"  backup: {snapshot['backup_path']} ({backup_state})")
            try:
                repo_snapshot = repo_ops.repo_status(
                    args.name,
                    args.repo_dir,
                    skills_root_path=skills_root_path,
                )
                print("git status:")
                if repo_snapshot["git_status"]:
                    print(repo_snapshot["git_status"])
            except repo_ops.RepoSyncError as exc:
                print("git status:")
                print(f"错误: {exc}")
            if args.name in source_skills:
                _print_source_details(args.name, source_skills[args.name], dest_root)
            return 0

        source_entry = source_skills.get(args.name)
        if source_entry:
            _print_source_details(args.name, source_entry, dest_root)
            return 0

        print(f"未找到接入记录或来源记录: {args.name}", file=sys.stderr)
        return 1

    default_repo = state.get("default_repo") or {}
    if default_repo:
        print("默认仓库:")
        print(f"  repo: {default_repo.get('repo', '')}")
        print(f"  repo_dir: {default_repo.get('repo_dir', '')}")
        print(f"  repo_url: {default_repo.get('repo_url', '')}")
        print(f"  ref: {default_repo.get('ref', '')}")
    else:
        print("默认仓库: 未登记")

    if links:
        print("接入记录:")
        for name in sorted(links.keys()):
            snapshot = link_ops.status_snapshot(name, links[name], skills_root_path=skills_root_path)
            print(f"  {name}: {snapshot['status']}")
    else:
        print("接入记录: 暂无记录")

    if source_skills:
        print("来源记录:")
        for name in sorted(source_skills.keys()):
            print(f"  {_format_source_entry(name, source_skills[name])}")
    else:
        print("来源记录: 暂无记录")
    return 0


def _cmd_restore(args: argparse.Namespace, dest_root: str) -> int:
    skills_root_path = Path(dest_root)
    state_file = link_ops.state_path(skills_root_path)
    state = link_ops.load_state(state_file)
    result = link_ops.restore_link(
        state,
        state_file,
        args.name,
        skills_root_path=skills_root_path,
    )
    if result["restored"]:
        print(f"已恢复备份: {result['target_path']}")
    else:
        print(f"未找到备份，仅移除软链记录: {args.name}")
    return 0


def _cmd_pull(args: argparse.Namespace, dest_root: str) -> int:
    result = repo_ops.pull_repo(
        args.name,
        args.repo_dir,
        rebase=args.rebase,
        autostash=args.autostash,
        skills_root_path=Path(dest_root),
    )
    print(f"已拉取仓库: {result['repo_dir']}")
    if result["output"]:
        print(result["output"])
    return 0


def _cmd_push(args: argparse.Namespace, dest_root: str) -> int:
    result = repo_ops.push_repo(
        args.name,
        args.repo_dir,
        set_upstream=args.set_upstream,
        remote=args.remote,
        skills_root_path=Path(dest_root),
    )
    if result["dirty_warning"]:
        print("警告: 仓库仍有未提交改动，本次只会推送已提交内容", file=sys.stderr)
    print(f"已推送仓库: {result['repo_dir']}")
    if result["output"]:
        print(result["output"])
    return 0


def _cmd_sync(args: argparse.Namespace, dest_root: str) -> int:
    result = repo_ops.sync_repo(
        args.name,
        args.repo_dir,
        rebase=args.rebase,
        autostash=args.autostash,
        set_upstream=args.set_upstream,
        remote=args.remote,
        skills_root_path=Path(dest_root),
    )
    pull_result = result["pull"]
    print(f"已拉取仓库: {pull_result['repo_dir']}")
    if pull_result["output"]:
        print(pull_result["output"])
    push_result = result["push"]
    if push_result["dirty_warning"]:
        print("警告: 仓库仍有未提交改动，本次只会推送已提交内容", file=sys.stderr)
    print(f"已推送仓库: {push_result['repo_dir']}")
    if push_result["output"]:
        print(push_result["output"])
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="统一管理已安装 Codex 技能的更新、接入与同步")
    parser.add_argument("--dest", help="技能目录，默认 $CODEX_HOME/skills")
    parser.add_argument("--sources", help="来源配置文件，默认 <dest>/.skill-sources.json")

    subparsers = parser.add_subparsers(dest="command", required=True)

    connect_parser = subparsers.add_parser("connect", help="登记技能仓库并链接 skill")
    connect_parser.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub 仓库，默认 {DEFAULT_REPO}")
    connect_parser.add_argument("--repo-url", help="显式指定克隆 URL")
    connect_parser.add_argument("--repo-dir", help="本地仓库目录")
    connect_parser.add_argument("--ref", default=link_ops.DEFAULT_REF, help=f"分支或标签，默认 {link_ops.DEFAULT_REF}")
    connect_target_group = connect_parser.add_mutually_exclusive_group(required=False)
    connect_target_group.add_argument("--name", help="仅链接指定 skill")
    connect_target_group.add_argument("--all", action="store_true", help="链接仓库中的全部 skill")
    connect_target_group.add_argument("--no-link", action="store_true", help="仅登记仓库，不创建软链")

    status_parser = subparsers.add_parser("status", help="查看技能来源、接入与仓库状态")
    status_parser.add_argument("--name", help="指定 skill 名称")
    status_parser.add_argument("--repo-dir", help="显式指定仓库目录，仅对已接入 skill 生效")

    sync_parser = subparsers.add_parser("sync", help="同步已接入 skill 所在仓库（先拉取再推送）")
    sync_parser.add_argument("--name", required=True, help="skill 名称")
    sync_parser.add_argument("--repo-dir", help="本地仓库目录，默认从接入记录解析")
    sync_parser.add_argument("--rebase", action="store_true", help="使用 rebase 方式拉取")
    sync_parser.add_argument("--autostash", action="store_true", help="拉取前自动暂存未提交改动")
    sync_parser.add_argument("--set-upstream", action="store_true", help="推送时为当前分支设置上游分支")
    sync_parser.add_argument("--remote", default=repo_ops.DEFAULT_REMOTE, help=f"推送远程名，默认 {repo_ops.DEFAULT_REMOTE}")

    pull_parser = subparsers.add_parser("pull", help="拉取已接入 skill 所在仓库")
    pull_parser.add_argument("--name", required=True, help="skill 名称")
    pull_parser.add_argument("--repo-dir", help="本地仓库目录，默认从接入记录解析")
    pull_parser.add_argument("--rebase", action="store_true", help="使用 rebase 方式拉取")
    pull_parser.add_argument("--autostash", action="store_true", help="拉取前自动暂存未提交改动")

    push_parser = subparsers.add_parser("push", help="推送已接入 skill 所在仓库")
    push_parser.add_argument("--name", required=True, help="skill 名称")
    push_parser.add_argument("--repo-dir", help="本地仓库目录，默认从接入记录解析")
    push_parser.add_argument("--set-upstream", action="store_true", help="为当前分支设置上游分支")
    push_parser.add_argument("--remote", default=repo_ops.DEFAULT_REMOTE, help=f"推送远程名，默认 {repo_ops.DEFAULT_REMOTE}")

    restore_parser = subparsers.add_parser("restore", help="移除软链并恢复备份")
    restore_parser.add_argument("--name", required=True, help="skill 名称")

    source_add_parser = subparsers.add_parser("source-add", help="添加或更新来源记录")
    source_add_parser.add_argument("--name", required=True, help="技能名称")
    source_group = source_add_parser.add_mutually_exclusive_group(required=False)
    source_group.add_argument("--local-path", help="本地技能目录路径")
    source_group.add_argument("--repo", help=f"GitHub 仓库，格式 owner/repo（默认 {DEFAULT_REPO}）")
    source_group.add_argument("--url", help="GitHub URL，指向 skill 目录")
    source_add_parser.add_argument("--path", help="仓库内路径，用于 --repo 或默认仓库")
    source_add_parser.add_argument("--ref", default="main", help="分支或标签")
    source_add_parser.add_argument(
        "--method",
        default="auto",
        choices=["auto", "download", "git"],
        help="安装方式",
    )

    subparsers.add_parser("source-list", help="列出来源记录")

    source_remove_parser = subparsers.add_parser("source-remove", help="移除来源记录")
    source_remove_parser.add_argument("--name", nargs="+", required=True, help="技能名称")

    update_parser = subparsers.add_parser("update", help="更新普通安装型技能")
    update_parser.add_argument("--all", action="store_true", help="更新全部记录")
    update_parser.add_argument("--name", nargs="+", help="指定技能名称")
    update_parser.add_argument("--installer", help="install-skill-from-github.py 路径")
    update_parser.add_argument("--keep-backup", action="store_true", help="保留旧版本备份")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    dest_root = _expand_path(args.dest) if args.dest else _default_dest()

    try:
        if args.command == "connect":
            return _cmd_connect(args, dest_root)
        if args.command == "status":
            return _cmd_status(args, dest_root)
        if args.command == "sync":
            return _cmd_sync(args, dest_root)
        if args.command == "pull":
            return _cmd_pull(args, dest_root)
        if args.command == "push":
            return _cmd_push(args, dest_root)
        if args.command == "restore":
            return _cmd_restore(args, dest_root)
        if args.command == "source-add":
            return _cmd_source_add(args, dest_root)
        if args.command == "source-list":
            return _cmd_source_list(args, dest_root)
        if args.command == "source-remove":
            return _cmd_source_remove(args, dest_root)
        if args.command == "update":
            return _cmd_update(args, dest_root)
        parser.print_help()
        return 1
    except (link_ops.SkillLinkError, repo_ops.RepoSyncError, ValueError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"错误: 命令执行失败（退出码 {exc.returncode}）", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
