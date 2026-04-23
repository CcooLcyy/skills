#!/usr/bin/env python3
"""技能仓库状态查看与 Git 同步。"""

from __future__ import annotations

from pathlib import Path

import link_ops

DEFAULT_REMOTE = "origin"


class RepoSyncError(Exception):
    pass


def resolve_repo(
    name: str,
    repo_dir_text: str | None = None,
    skills_root_path: Path | None = None,
) -> tuple[Path, dict]:
    entry = {}
    if repo_dir_text:
        repo_dir = link_ops.expand_path(repo_dir_text)
    else:
        state = link_ops.load_state(link_ops.state_path(skills_root_path))
        entry = state.get("links", {}).get(name)
        if not entry:
            raise RepoSyncError(f"未找到接入记录: {name}")
        repo_dir_value = entry.get("repo_dir", "")
        if not repo_dir_value:
            raise RepoSyncError(f"接入记录缺少 repo_dir: {name}")
        repo_dir = link_ops.expand_path(repo_dir_value)
    if not repo_dir.is_dir():
        raise RepoSyncError(f"仓库目录不存在: {repo_dir}")
    if not link_ops.is_git_repo(repo_dir):
        raise RepoSyncError(f"目录不是 Git 仓库: {repo_dir}")
    return repo_dir, entry


def has_uncommitted_changes(repo_dir: Path) -> bool:
    output = link_ops.run_git(["status", "--porcelain"], repo_dir)
    return bool(output.strip())


def repo_status(
    name: str,
    repo_dir_text: str | None = None,
    skills_root_path: Path | None = None,
) -> dict:
    repo_dir, entry = resolve_repo(name, repo_dir_text, skills_root_path=skills_root_path)
    output = link_ops.run_git(["status", "-sb"], repo_dir)
    return {
        "name": name,
        "repo_dir": str(repo_dir),
        "entry": entry,
        "git_status": output,
    }


def pull_repo(
    name: str,
    repo_dir_text: str | None = None,
    rebase: bool = False,
    autostash: bool = False,
    skills_root_path: Path | None = None,
) -> dict:
    repo_dir, _entry = resolve_repo(name, repo_dir_text, skills_root_path=skills_root_path)
    dirty = has_uncommitted_changes(repo_dir)
    if dirty and not autostash:
        raise RepoSyncError("仓库存在未提交改动，请先提交或暂存，或显式使用 --autostash")
    cmd = ["pull"]
    if rebase:
        cmd.append("--rebase")
    if autostash:
        cmd.append("--autostash")
    output = link_ops.run_git(cmd, repo_dir)
    return {"repo_dir": str(repo_dir), "output": output}


def _build_push_cmd(set_upstream: bool, remote: str, repo_dir: Path) -> list[str]:
    if set_upstream:
        branch = link_ops.run_git(["branch", "--show-current"], repo_dir)
        if not branch:
            raise RepoSyncError("无法识别当前分支，不能设置上游分支")
        return ["push", "--set-upstream", remote, branch]
    return ["push", remote]


def push_repo(
    name: str,
    repo_dir_text: str | None = None,
    set_upstream: bool = False,
    remote: str = DEFAULT_REMOTE,
    skills_root_path: Path | None = None,
) -> dict:
    repo_dir, _entry = resolve_repo(name, repo_dir_text, skills_root_path=skills_root_path)
    dirty_warning = has_uncommitted_changes(repo_dir)
    output = link_ops.run_git(_build_push_cmd(set_upstream, remote, repo_dir), repo_dir)
    return {
        "repo_dir": str(repo_dir),
        "output": output,
        "dirty_warning": dirty_warning,
    }


def sync_repo(
    name: str,
    repo_dir_text: str | None = None,
    rebase: bool = False,
    autostash: bool = False,
    set_upstream: bool = False,
    remote: str = DEFAULT_REMOTE,
    skills_root_path: Path | None = None,
) -> dict:
    pull_result = pull_repo(
        name,
        repo_dir_text,
        rebase=rebase,
        autostash=autostash,
        skills_root_path=skills_root_path,
    )
    push_result = push_repo(
        name,
        repo_dir_text,
        set_upstream=set_upstream,
        remote=remote,
        skills_root_path=skills_root_path,
    )
    return {"pull": pull_result, "push": push_result}
