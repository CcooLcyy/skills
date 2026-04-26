#!/usr/bin/env python3
"""git-commit 技能的确定性 Git 辅助脚本。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class GitCommitHelperError(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="辅助 git-commit 技能完成状态探查、提交与最终同步。")
    parser.add_argument("--repo", default=".", help="Git 仓库路径，默认当前目录。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="收集提交前上下文。")
    inspect_parser.add_argument("--json", action="store_true", help="输出 JSON，便于机器读取。")
    inspect_parser.add_argument("--include-diff", action="store_true", help="包含截断后的 git diff 与 cached diff。")
    inspect_parser.add_argument("--max-diff-lines", type=int, default=200, help="每段 diff 最多输出行数。")
    inspect_parser.set_defaults(func=cmd_inspect)

    commit_parser = subparsers.add_parser("commit", help="使用 UTF-8 无 BOM 临时消息文件执行 git commit。")
    commit_parser.add_argument("--message-file", required=True, help="提交信息文件路径。")
    commit_parser.add_argument("--amend", action="store_true", help="传递 git commit --amend。")
    commit_parser.add_argument("--no-verify", action="store_true", help="传递 git commit --no-verify。")
    commit_parser.set_defaults(func=cmd_commit)

    sync_parser = subparsers.add_parser("sync", help="提交后 fetch/rebase/push，同步远端。")
    sync_parser.add_argument("--remote", default="origin", help="没有 upstream 时用于 push -u 的远端名。")
    sync_parser.add_argument("--autostash", action="store_true", help="pull --rebase 时使用 --autostash。")
    sync_parser.add_argument("--dry-run", action="store_true", help="只展示将执行的同步动作，不执行 fetch/pull/push。")
    sync_parser.add_argument("--no-push", action="store_true", help="只同步远端引用和 rebase，不执行 push。")
    sync_parser.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except GitCommitHelperError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def cmd_inspect(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    report = build_inspect_report(repo, args.include_diff, args.max_diff_lines)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_inspect_markdown(report)


def cmd_commit(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    message_path = Path(args.message_file).expanduser()
    if not message_path.is_file():
        raise GitCommitHelperError(f"提交信息文件不存在: {message_path}")
    message = read_utf8_message(message_path)
    validate_commit_message(message)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False) as tmp:
        tmp.write(message)
        tmp_path = Path(tmp.name)
    try:
        command = ["commit", "-F", str(tmp_path)]
        if args.amend:
            command.append("--amend")
        if args.no_verify:
            command.append("--no-verify")
        output = run_git(command, repo)
    finally:
        tmp_path.unlink(missing_ok=True)
    if output:
        print(output)
    print()
    print(run_git(["status", "-sb"], repo))
    print(run_git(["log", "-1", "--oneline"], repo))


def cmd_sync(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    branch = run_git(["branch", "--show-current"], repo).strip()
    if not branch:
        raise GitCommitHelperError("当前处于 detached HEAD，无法安全设置 upstream 或推送当前分支。")

    dirty = bool(run_git(["status", "--porcelain"], repo).strip())
    print(run_git(["status", "-sb"], repo))
    print(run_git(["log", "-1", "--oneline"], repo))

    if args.dry_run:
        print("dry-run: 不执行 fetch/pull/push，ahead/behind 基于本地远端引用。")
    else:
        run_and_print(["fetch", "--prune"], repo)

    upstream = get_upstream(repo)
    if not upstream:
        ensure_remote_exists(repo, args.remote)
        command = ["push", "-u", args.remote, "HEAD"]
        if args.no_push:
            print(f"no-push: 当前分支没有 upstream，需执行: git {' '.join(command)}")
            return
        run_or_dry(command, repo, args.dry_run)
        return

    ahead, behind = ahead_behind(repo, upstream)
    print(f"upstream: {upstream}")
    print(f"ahead: {ahead}, behind: {behind}")

    if behind:
        if dirty and not args.autostash:
            raise GitCommitHelperError(
                "本地工作区存在未提交改动，不能自动 pull --rebase。请先处理改动，或确认后使用 --autostash。"
            )
        pull_command = ["pull", "--rebase"]
        if args.autostash:
            pull_command.append("--autostash")
        run_or_dry(pull_command, repo, args.dry_run)
        if not args.dry_run:
            ahead, behind = ahead_behind(repo, upstream)
            print(f"after rebase ahead: {ahead}, behind: {behind}")

    if args.no_push:
        print("no-push: 已跳过 push。")
        return
    if ahead:
        run_or_dry(["push"], repo, args.dry_run)
    elif behind:
        print("仍落后 upstream，未执行 push。")
    else:
        print("本地分支与 upstream 已同步，无需 push。")


def build_inspect_report(repo: Path, include_diff: bool, max_diff_lines: int) -> dict[str, Any]:
    status_short = run_git(["status", "-sb"], repo)
    porcelain = run_git(["status", "--porcelain"], repo)
    staged_files, unstaged_files, untracked_files = parse_status_porcelain(porcelain)
    upstream = get_upstream(repo)
    ahead = behind = None
    if upstream:
        ahead, behind = ahead_behind(repo, upstream)

    report: dict[str, Any] = {
        "repo": str(repo),
        "branch": run_git(["branch", "--show-current"], repo).strip(),
        "status_short": status_short,
        "staged_files": staged_files,
        "unstaged_files": unstaged_files,
        "untracked_files": untracked_files,
        "exclude_hints": exclusion_hints(staged_files + unstaged_files + untracked_files),
        "diff_stat": run_git(["diff", "--stat"], repo, check=False),
        "cached_diff_stat": run_git(["diff", "--cached", "--stat"], repo, check=False),
        "commit_guidance": detect_commit_guidance(repo),
        "recent_commits": run_git(["log", "-8", "--pretty=format:%h\t%s"], repo, check=False).splitlines(),
        "remotes": run_git(["remote", "-v"], repo, check=False).splitlines(),
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
    }
    if include_diff:
        report["diff"] = truncate_lines(run_git(["diff"], repo, check=False), max_diff_lines)
        report["cached_diff"] = truncate_lines(run_git(["diff", "--cached"], repo, check=False), max_diff_lines)
    return report


def print_inspect_markdown(report: dict[str, Any]) -> None:
    print("# git-commit inspect")
    print()
    print(f"- repo: {report['repo']}")
    print(f"- branch: {report['branch'] or '(detached HEAD)'}")
    print(f"- upstream: {report['upstream'] or '(none)'}")
    if report["ahead"] is not None and report["behind"] is not None:
        print(f"- ahead/behind: {report['ahead']}/{report['behind']}")
    print()
    print("## status")
    print_code(report["status_short"])
    print()
    print_file_list("staged", report["staged_files"])
    print_file_list("unstaged", report["unstaged_files"])
    print_file_list("untracked", report["untracked_files"])
    print()
    print("## diff stat")
    print_code(report["diff_stat"] or "(empty)")
    print()
    print("## cached diff stat")
    print_code(report["cached_diff_stat"] or "(empty)")
    print()
    print("## possible excludes")
    hints = report["exclude_hints"]
    if hints:
        for item in hints:
            print(f"- {item['path']}: {item['reason']}")
    else:
        print("- (none)")
    print()
    print("## commit guidance")
    guidance = report["commit_guidance"]
    if guidance["files"]:
        for item in guidance["files"]:
            print(f"- {item['path']}: {item['reason']}")
    else:
        print("- 未发现明确提交规范文件。")
    if guidance["git_commit_template"]:
        print(f"- git config commit.template: {guidance['git_commit_template']}")
    if guidance["package_json"]:
        print(f"- package.json: {', '.join(guidance['package_json'])}")
    print()
    print("## recent commits")
    if report["recent_commits"]:
        for line in report["recent_commits"]:
            print(f"- {line}")
    else:
        print("- (none)")
    if "diff" in report:
        print()
        print("## diff")
        print_code(report["diff"] or "(empty)")
        print()
        print("## cached diff")
        print_code(report["cached_diff"] or "(empty)")


def print_file_list(title: str, files: list[str]) -> None:
    print(f"## {title} files")
    if not files:
        print("- (none)")
        return
    for path in files:
        print(f"- {path}")


def parse_status_porcelain(output: str) -> tuple[list[str], list[str], list[str]]:
    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        status = line[:2]
        path = line[3:] if len(line) > 3 else ""
        if status == "??":
            untracked.append(path)
            continue
        if status[0] != " ":
            staged.append(path)
        if status[1] != " ":
            unstaged.append(path)
    return staged, unstaged, untracked


def exclusion_hints(paths: list[str]) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        lower = normalized.lower()
        reason = ""
        name = Path(normalized).name.lower()
        if name == ".env" or name.startswith(".env."):
            reason = "环境变量文件，确认是否包含密钥或本地配置。"
        elif any(part in lower for part in ["secret", "credential", "token", "password"]):
            reason = "路径名疑似包含敏感信息关键词。"
        elif lower.endswith((".pem", ".key", ".p12", ".pfx")) or name.startswith("id_rsa"):
            reason = "密钥或证书文件，通常不应提交。"
        elif lower.endswith((".log", ".tmp", ".bak", ".pyc")):
            reason = "日志、临时文件或编译产物，通常不应提交。"
        elif any(part in lower.split("/") for part in ["dist", "build", "coverage", "__pycache__", ".pytest_cache", ".next"]):
            reason = "生成目录或缓存目录，确认是否应提交。"
        elif lower.endswith((".zip", ".tar", ".tar.gz", ".tgz", ".7z", ".rar")):
            reason = "归档大文件，确认是否应提交。"
        if reason:
            hints.append({"path": path, "reason": reason})
    return hints


def detect_commit_guidance(repo: Path) -> dict[str, Any]:
    files: list[dict[str, str]] = []
    exact_names = [
        "CONTRIBUTING.md",
        "README.md",
        ".gitmessage",
        ".gitmessage.txt",
        ".commitlintrc",
        ".commitlintrc.json",
        ".commitlintrc.js",
        ".commitlintrc.cjs",
        ".commitlintrc.yaml",
        ".commitlintrc.yml",
        "commitlint.config.js",
        "commitlint.config.cjs",
        "commitlint.config.mjs",
        "commitlint.config.ts",
    ]
    for name in exact_names:
        path = repo / name
        if path.exists():
            files.append({"path": str(path.relative_to(repo)), "reason": "提交规范或仓库说明候选文件。"})

    docs = repo / "docs"
    if docs.is_dir():
        for path in sorted(docs.rglob("*")):
            if len(files) >= 30:
                break
            if not path.is_file():
                continue
            lower = path.name.lower()
            if "commit" in lower or "contribut" in lower or "提交" in lower or "贡献" in lower:
                files.append({"path": str(path.relative_to(repo)), "reason": "docs 中疑似提交规范文档。"})

    git_template = run_git(["config", "--get", "commit.template"], repo, check=False).strip()
    package_guidance = package_json_guidance(repo)
    return {
        "files": dedupe_files(files),
        "git_commit_template": git_template,
        "package_json": package_guidance,
    }


def package_json_guidance(repo: Path) -> list[str]:
    path = repo / "package.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ["package.json 存在但无法解析"]
    guidance: list[str] = []
    if "commitlint" in data:
        guidance.append("commitlint")
    config = data.get("config")
    if isinstance(config, dict) and "commitizen" in config:
        guidance.append("config.commitizen")
    for dep_key in ("dependencies", "devDependencies"):
        deps = data.get(dep_key)
        if not isinstance(deps, dict):
            continue
        for name in deps:
            if "commitlint" in name or "commitizen" in name:
                guidance.append(f"{dep_key}.{name}")
    return guidance


def dedupe_files(files: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in files:
        if item["path"] in seen:
            continue
        seen.add(item["path"])
        result.append(item)
    return result


def get_upstream(repo: Path) -> str:
    return run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], repo, check=False).strip()


def ahead_behind(repo: Path, upstream: str) -> tuple[int, int]:
    output = run_git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"], repo, check=False).strip()
    if not output:
        return 0, 0
    parts = output.split()
    if len(parts) != 2:
        return 0, 0
    return int(parts[0]), int(parts[1])


def ensure_remote_exists(repo: Path, remote: str) -> None:
    remotes = run_git(["remote"], repo, check=False).splitlines()
    if remote not in remotes:
        raise GitCommitHelperError(f"当前仓库没有远端 {remote!r}，请明确远端与分支名。")


def resolve_repo(repo_text: str) -> Path:
    repo = Path(repo_text).expanduser().resolve()
    output = run_git(["rev-parse", "--show-toplevel"], repo, check=False).strip()
    if not output:
        raise GitCommitHelperError(f"不是 Git 仓库或不在工作树中: {repo}")
    return Path(output)


def run_git(args: list[str], repo: Path, check: bool = True) -> str:
    command = ["git", "-C", str(repo), *args]
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed"
        raise GitCommitHelperError(message)
    return proc.stdout.rstrip()


def run_and_print(args: list[str], repo: Path) -> None:
    print(f"$ git {' '.join(args)}")
    output = run_git(args, repo)
    if output:
        print(output)


def run_or_dry(args: list[str], repo: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"dry-run: git {' '.join(args)}")
        return
    run_and_print(args, repo)


def read_utf8_message(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    except UnicodeDecodeError as exc:
        raise GitCommitHelperError(f"提交信息不是有效 UTF-8: {path}") from exc


def validate_commit_message(message: str) -> None:
    if not message.strip():
        raise GitCommitHelperError("提交信息为空。")
    first_line = message.strip().splitlines()[0]
    if not first_line.strip():
        raise GitCommitHelperError("提交信息标题为空。")
    if "\\n" in message and "\n" not in message.strip():
        raise GitCommitHelperError("提交信息疑似包含字面量 \\\\n，请改成真实换行。")


def truncate_lines(text: str, max_lines: int) -> str:
    if max_lines <= 0:
        return ""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    omitted = len(lines) - max_lines
    return "\n".join(lines[:max_lines] + [f"... ({omitted} lines omitted)"])


def print_code(text: str) -> None:
    print("```")
    print(text)
    print("```")


if __name__ == "__main__":
    sys.exit(main())
