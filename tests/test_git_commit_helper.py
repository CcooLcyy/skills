from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "git-commit" / "scripts" / "git_commit_helper.py"


class GitCommitHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def _run_helper(self, args: list[str], *, repo: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--repo", str(repo), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _git(self, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            self.fail(
                f"git 命令失败: {' '.join(args)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def _create_repo(self, name: str = "repo") -> Path:
        repo = self.root / name
        repo.mkdir()
        self._git(repo, "init", "-q")
        self._git(repo, "checkout", "-qb", "main")
        self._git(repo, "config", "user.name", "Codex")
        self._git(repo, "config", "user.email", "codex@example.com")
        (repo / "tracked.txt").write_text("v1\n", encoding="utf-8")
        self._git(repo, "add", "tracked.txt")
        self._git(repo, "commit", "-qm", "init")
        return repo

    def test_inspect_json_reports_status_and_exclusion_hints(self) -> None:
        repo = self._create_repo()
        (repo / "tracked.txt").write_text("v2\n", encoding="utf-8")
        (repo / ".env.local").write_text("TOKEN=secret\n", encoding="utf-8")

        result = self._run_helper(
            ["inspect", "--json", "--include-diff", "--max-diff-lines", "20"],
            repo=repo,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["branch"], "main")
        self.assertIn("tracked.txt", report["unstaged_files"])
        self.assertIn(".env.local", report["untracked_files"])
        self.assertIn("tracked.txt", report["diff"])
        self.assertTrue(
            any(item["path"] == ".env.local" for item in report["exclude_hints"]),
            report["exclude_hints"],
        )

    def test_commit_uses_utf8_message_file(self) -> None:
        repo = self._create_repo()
        (repo / "tracked.txt").write_text("v2\n", encoding="utf-8")
        self._git(repo, "add", "tracked.txt")
        message_path = self.root / "message.txt"
        message_path.write_text(
            "\ufeff完善提交辅助脚本\n\n记录 UTF-8 提交信息文件路径。\n",
            encoding="utf-8",
        )

        result = self._run_helper(["commit", "--message-file", str(message_path)], repo=repo)

        self.assertEqual(result.returncode, 0, result.stderr)
        log = self._git(repo, "log", "-1", "--pretty=%B").stdout
        self.assertIn("完善提交辅助脚本", log)
        self.assertIn("记录 UTF-8 提交信息文件路径。", log)
        self.assertEqual(self._git(repo, "status", "--porcelain").stdout, "")

    def test_commit_rejects_literal_newline_message(self) -> None:
        repo = self._create_repo()
        message_path = self.root / "message.txt"
        message_path.write_text("标题\\n正文", encoding="utf-8")

        result = self._run_helper(["commit", "--message-file", str(message_path)], repo=repo)

        self.assertEqual(result.returncode, 2)
        self.assertIn("字面量", result.stderr)

    def test_sync_dry_run_reports_upstream_without_pushing(self) -> None:
        remote = self.root / "remote.git"
        self._git(self.root, "init", "--bare", "-q", str(remote))
        repo = self._create_repo()
        self._git(repo, "remote", "add", "origin", str(remote))
        self._git(repo, "push", "-u", "origin", "main")
        (repo / "tracked.txt").write_text("v2\n", encoding="utf-8")
        self._git(repo, "add", "tracked.txt")
        self._git(repo, "commit", "-qm", "local change")

        result = self._run_helper(["sync", "--dry-run", "--no-push"], repo=repo)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dry-run", result.stdout)
        self.assertIn("upstream: origin/main", result.stdout)
        self.assertIn("ahead: 1, behind: 0", result.stdout)
        self.assertIn("no-push", result.stdout)


if __name__ == "__main__":
    unittest.main()
