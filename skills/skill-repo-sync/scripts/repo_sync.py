#!/usr/bin/env python3
"""同步由 skill-dev-link 接入的 skill 所在 Git 仓库。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

STATE_FILE_NAME = ".dev-links.json"
DEFAULT_REMOTE = "origin"


class RepoSyncError(Exception):
    pass


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser().resolve()


def _skills_root() -> Path:
    return _codex_home() / "skills"


def _state_path() -> Path:
    return _skills_root() / STATE_FILE_NAME


def _expand_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "default_repo": {}, "links": {}}
    with path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    if not isinstance(data, dict):
        raise RepoSyncError("链接状态文件格式错误：顶层必须是对象")
    links = data.get("links")
    if links is None:
        data["links"] = {}
    elif not isinstance(links, dict):
        raise RepoSyncError("链接状态文件格式错误：links 必须是对象")
    return data


def _run_git(args: list[str], cwd: Path) -> str:
    cmd = ["git"] + args
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git 命令执行失败"
        raise RepoSyncError(message)
    return result.stdout.strip()


def _is_git_repo(path: Path) -> bool:
    try:
        output = _run_git(["rev-parse", "--is-inside-work-tree"], path)
    except RepoSyncError:
        return False
    return output == "true"


def _resolve_repo(args: argparse.Namespace) -> tuple[Path, dict]:
    entry = {}
    if args.repo_dir:
        repo_dir = _expand_path(args.repo_dir)
    else:
        state = _load_state(_state_path())
        entry = state.get("links", {}).get(args.name)
        if not entry:
            raise RepoSyncError(f"未找到 skill-dev-link 记录: {args.name}")
        repo_dir_text = entry.get("repo_dir", "")
        if not repo_dir_text:
            raise RepoSyncError(f"链接记录缺少 repo_dir: {args.name}")
        repo_dir = _expand_path(repo_dir_text)
    if not repo_dir.is_dir():
        raise RepoSyncError(f"仓库目录不存在: {repo_dir}")
    if not _is_git_repo(repo_dir):
        raise RepoSyncError(f"目录不是 Git 仓库: {repo_dir}")
    return repo_dir, entry


def _has_uncommitted_changes(repo_dir: Path) -> bool:
    output = _run_git(["status", "--porcelain"], repo_dir)
    return bool(output.strip())


def _cmd_status(args: argparse.Namespace) -> int:
    repo_dir, entry = _resolve_repo(args)
    print(f"skill: {args.name}")
    print(f"repo_dir: {repo_dir}")
    if entry:
        if entry.get("target_path"):
            print(f"target: {entry['target_path']}")
        if entry.get("source_path"):
            print(f"source: {entry['source_path']}")
    print("git status:")
    output = _run_git(["status", "-sb"], repo_dir)
    if output:
        print(output)
    return 0


def _cmd_pull(args: argparse.Namespace) -> int:
    repo_dir, _entry = _resolve_repo(args)
    dirty = _has_uncommitted_changes(repo_dir)
    if dirty and not args.autostash:
        raise RepoSyncError("仓库存在未提交改动，请先提交或暂存，或显式使用 --autostash")
    cmd = ["pull"]
    if args.rebase:
        cmd.append("--rebase")
    if args.autostash:
        cmd.append("--autostash")
    output = _run_git(cmd, repo_dir)
    print(f"已拉取仓库: {repo_dir}")
    if output:
        print(output)
    return 0


def _build_push_cmd(args: argparse.Namespace, repo_dir: Path) -> list[str]:
    if args.set_upstream:
        branch = _run_git(["branch", "--show-current"], repo_dir)
        if not branch:
            raise RepoSyncError("无法识别当前分支，不能设置上游分支")
        return ["push", "--set-upstream", args.remote, branch]
    return ["push", args.remote]


def _cmd_push(args: argparse.Namespace) -> int:
    repo_dir, _entry = _resolve_repo(args)
    if _has_uncommitted_changes(repo_dir):
        print("警告: 仓库仍有未提交改动，本次只会推送已提交内容", file=sys.stderr)
    output = _run_git(_build_push_cmd(args, repo_dir), repo_dir)
    print(f"已推送仓库: {repo_dir}")
    if output:
        print(output)
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    pull_result = _cmd_pull(args)
    if pull_result != 0:
        return pull_result
    return _cmd_push(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同步由 skill-dev-link 接入的 skill 仓库")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="直接同步 skill 对应仓库（先拉取再推送）")
    sync_parser.add_argument("--name", required=True, help="skill 名称，用于解析所属仓库")
    sync_parser.add_argument("--repo-dir", help="显式指定仓库目录，跳过链接状态解析")
    sync_parser.add_argument("--rebase", action="store_true", help="使用 rebase 方式拉取")
    sync_parser.add_argument("--autostash", action="store_true", help="拉取前自动暂存本地未提交改动")
    sync_parser.add_argument("--set-upstream", action="store_true", help="为当前分支设置上游分支后推送")
    sync_parser.add_argument("--remote", default=DEFAULT_REMOTE, help=f"推送远程名，默认 {DEFAULT_REMOTE}")

    status_parser = subparsers.add_parser("status", help="查看 skill 对应仓库状态")
    status_parser.add_argument("--name", required=True, help="skill 名称，用于解析所属仓库")
    status_parser.add_argument("--repo-dir", help="显式指定仓库目录，跳过链接状态解析")

    pull_parser = subparsers.add_parser("pull", help="从远程拉取 skill 对应仓库")
    pull_parser.add_argument("--name", required=True, help="skill 名称，用于解析所属仓库")
    pull_parser.add_argument("--repo-dir", help="显式指定仓库目录，跳过链接状态解析")
    pull_parser.add_argument("--rebase", action="store_true", help="使用 rebase 方式拉取")
    pull_parser.add_argument("--autostash", action="store_true", help="拉取前自动暂存本地未提交改动")

    push_parser = subparsers.add_parser("push", help="将 skill 对应仓库推送到远程")
    push_parser.add_argument("--name", required=True, help="skill 名称，用于解析所属仓库")
    push_parser.add_argument("--repo-dir", help="显式指定仓库目录，跳过链接状态解析")
    push_parser.add_argument("--set-upstream", action="store_true", help="为当前分支设置上游分支后推送")
    push_parser.add_argument("--remote", default=DEFAULT_REMOTE, help=f"推送远程名，默认 {DEFAULT_REMOTE}")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "sync":
            return _cmd_sync(args)
        if args.command == "status":
            return _cmd_status(args)
        if args.command == "pull":
            return _cmd_pull(args)
        if args.command == "push":
            return _cmd_push(args)
        parser.print_help()
        return 1
    except RepoSyncError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
