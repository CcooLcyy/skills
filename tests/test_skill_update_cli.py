from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "skill-update" / "scripts" / "update_skills.py"


def _run(
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=str(cwd or REPO_ROOT),
        env=env,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class SkillUpdateCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source"
            target = temp_path / "target"
            source.mkdir()
            try:
                os.symlink(str(source), str(target))
            except OSError as exc:
                raise unittest.SkipTest(f"当前环境不支持软链: {exc}") from exc

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.codex_home = self.root / "codex-home"
        self.skills_root = self.codex_home / "skills"
        self.skills_root.mkdir(parents=True, exist_ok=True)
        self.env = os.environ.copy()
        self.env["CODEX_HOME"] = str(self.codex_home)

    def _assert_ok(self, result: subprocess.CompletedProcess[str]) -> None:
        if result.returncode != 0:
            self.fail(f"命令失败\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")

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

    def _create_repo(self, name: str, skill_names: list[str], *, with_remote: bool = False) -> Path:
        repo = self.root / name
        repo.mkdir()
        self._git(repo, "init", "-q")
        self._git(repo, "checkout", "-qb", "main")
        self._git(repo, "config", "user.name", "Codex")
        self._git(repo, "config", "user.email", "codex@example.com")
        skills_dir = repo / "skills"
        skills_dir.mkdir()
        for skill_name in skill_names:
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"# {skill_name}\n", encoding="utf-8")
            (skill_dir / "content.txt").write_text(f"{skill_name}-v1\n", encoding="utf-8")
        self._git(repo, "add", ".")
        self._git(repo, "commit", "-qm", "init")
        if with_remote:
            remote = self.root / f"{name}-remote.git"
            self._git(self.root, "init", "--bare", "-q", str(remote))
            self._git(repo, "remote", "add", "origin", str(remote))
        return repo

    def test_source_commands_and_update(self) -> None:
        source_dir = self.root / "source-skill" / "demo"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("# demo\n", encoding="utf-8")
        (source_dir / "content.txt").write_text("v1\n", encoding="utf-8")

        result = _run(
            ["source-add", "--name", "demo", "--local-path", str(source_dir)],
            env=self.env,
        )
        self._assert_ok(result)

        result = _run(["source-list"], env=self.env)
        self._assert_ok(result)
        self.assertIn("demo: 本地", result.stdout)

        result = _run(["update", "--name", "demo"], env=self.env)
        self._assert_ok(result)
        self.assertEqual((self.skills_root / "demo" / "content.txt").read_text(encoding="utf-8"), "v1\n")

        (source_dir / "content.txt").write_text("v2\n", encoding="utf-8")
        result = _run(["update", "--name", "demo"], env=self.env)
        self._assert_ok(result)
        self.assertEqual((self.skills_root / "demo" / "content.txt").read_text(encoding="utf-8"), "v2\n")

        result = _run(["status", "--name", "demo"], env=self.env)
        self._assert_ok(result)
        self.assertIn("来源记录:", result.stdout)
        self.assertIn("当前安装状态:", result.stdout)

        result = _run(["source-remove", "--name", "demo"], env=self.env)
        self._assert_ok(result)
        result = _run(["source-list"], env=self.env)
        self._assert_ok(result)
        self.assertIn("暂无来源记录", result.stdout)

    def test_connect_no_link_then_link_all_and_restore(self) -> None:
        repo = self._create_repo("repo-all", ["alpha", "beta"])

        result = _run(["connect", "--repo-dir", str(repo), "--no-link"], env=self.env)
        self._assert_ok(result)
        self.assertFalse((self.skills_root / "alpha").exists())

        previous_alpha = self.skills_root / "alpha"
        previous_alpha.mkdir()
        (previous_alpha / "before.txt").write_text("old\n", encoding="utf-8")

        result = _run(["connect", "--repo-dir", str(repo), "--name", "alpha"], env=self.env)
        self._assert_ok(result)
        self.assertTrue((self.skills_root / "alpha").is_symlink())

        state = json.loads((self.skills_root / ".dev-links.json").read_text(encoding="utf-8"))
        alpha_entry = state["links"]["alpha"]
        self.assertTrue(Path(alpha_entry["backup_path"]).exists())

        result = _run(["connect", "--repo-dir", str(repo)], env=self.env)
        self._assert_ok(result)
        self.assertTrue((self.skills_root / "beta").is_symlink())

        result = _run(["restore", "--name", "alpha"], env=self.env)
        self._assert_ok(result)
        self.assertTrue((self.skills_root / "alpha").is_dir())
        self.assertEqual((self.skills_root / "alpha" / "before.txt").read_text(encoding="utf-8"), "old\n")

    def test_connect_uses_current_matching_repo_when_repo_dir_omitted(self) -> None:
        repo = self._create_repo("repo-current", ["alpha"], with_remote=True)
        remote = self.root / "repo-current-remote.git"

        result = _run(
            [
                "connect",
                "--repo",
                "local/repo-current",
                "--repo-url",
                str(remote),
                "--name",
                "alpha",
            ],
            env=self.env,
            cwd=repo / "skills" / "alpha",
        )

        self._assert_ok(result)
        self.assertIn("已从当前工作目录识别 skill 仓库", result.stdout)
        self.assertEqual(
            os.path.realpath(self.skills_root / "alpha"),
            str((repo / "skills" / "alpha").resolve()),
        )

    def test_connect_requires_repo_location_when_current_dir_is_unrelated(self) -> None:
        unrelated = self.root / "unrelated"
        unrelated.mkdir()

        result = _run(["connect", "--name", "alpha"], env=self.env, cwd=unrelated)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("当前工作目录未关联目标 skill 仓库", result.stderr)
        self.assertIn("--repo-dir", result.stderr)

    def test_connect_search_repo_dir_uses_registered_matching_repo(self) -> None:
        repo = self._create_repo("repo-search", ["alpha"], with_remote=True)
        remote = self.root / "repo-search-remote.git"
        unrelated = self.root / "unrelated-search"
        unrelated.mkdir()

        result = _run(
            [
                "connect",
                "--repo",
                "local/repo-search",
                "--repo-url",
                str(remote),
                "--repo-dir",
                str(repo),
                "--no-link",
            ],
            env=self.env,
        )
        self._assert_ok(result)

        result = _run(
            [
                "connect",
                "--repo",
                "local/repo-search",
                "--repo-url",
                str(remote),
                "--search-repo-dir",
                "--name",
                "alpha",
            ],
            env=self.env,
            cwd=unrelated,
        )

        self._assert_ok(result)
        self.assertIn("已搜索到本地 skill 仓库", result.stdout)
        self.assertEqual(
            os.path.realpath(self.skills_root / "alpha"),
            str((repo / "skills" / "alpha").resolve()),
        )

    def test_connect_matches_ssh_url_with_username(self) -> None:
        repo = self._create_repo("repo-ssh", ["alpha"])
        self._git(repo, "remote", "add", "origin", "ssh://git@github.com/local/repo-ssh.git")

        result = _run(
            [
                "connect",
                "--repo",
                "local/repo-ssh",
                "--name",
                "alpha",
            ],
            env=self.env,
            cwd=repo,
        )

        self._assert_ok(result)
        self.assertIn("已从当前工作目录识别 skill 仓库", result.stdout)
        self.assertEqual(
            os.path.realpath(self.skills_root / "alpha"),
            str((repo / "skills" / "alpha").resolve()),
        )

    def test_connect_rejects_unmanaged_symlink_and_allows_managed_relink(self) -> None:
        repo_a = self._create_repo("repo-a", ["alpha"])
        repo_b = self._create_repo("repo-b", ["alpha"])

        os.symlink(str(repo_a / "skills" / "alpha"), str(self.skills_root / "alpha"))
        result = _run(["connect", "--repo-dir", str(repo_b), "--name", "alpha"], env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未托管软链", result.stderr)

        os.remove(self.skills_root / "alpha")
        result = _run(["connect", "--repo-dir", str(repo_a), "--name", "alpha"], env=self.env)
        self._assert_ok(result)

        result = _run(["connect", "--repo-dir", str(repo_b), "--name", "alpha"], env=self.env)
        self._assert_ok(result)
        self.assertEqual(
            os.path.realpath(self.skills_root / "alpha"),
            str((repo_b / "skills" / "alpha").resolve()),
        )

    def test_status_for_linked_skill_includes_git_status(self) -> None:
        repo = self._create_repo("repo-status", ["alpha"])
        result = _run(["connect", "--repo-dir", str(repo), "--name", "alpha"], env=self.env)
        self._assert_ok(result)

        result = _run(["status", "--name", "alpha"], env=self.env)
        self._assert_ok(result)
        self.assertIn("接入记录:", result.stdout)
        self.assertIn("git status:", result.stdout)
        self.assertIn("## main", result.stdout)

    def test_pull_and_sync_fail_when_repo_is_dirty_without_autostash(self) -> None:
        repo = self._create_repo("repo-dirty", ["alpha"])
        result = _run(["connect", "--repo-dir", str(repo), "--name", "alpha"], env=self.env)
        self._assert_ok(result)

        (repo / "skills" / "alpha" / "content.txt").write_text("dirty\n", encoding="utf-8")

        result = _run(["pull", "--name", "alpha"], env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("仓库存在未提交改动", result.stderr)

        result = _run(["sync", "--name", "alpha"], env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("仓库存在未提交改动", result.stderr)

    def test_push_warns_on_dirty_repo_but_succeeds(self) -> None:
        repo = self._create_repo("repo-push", ["alpha"], with_remote=True)
        result = _run(["connect", "--repo-dir", str(repo), "--name", "alpha"], env=self.env)
        self._assert_ok(result)

        (repo / "skills" / "alpha" / "content.txt").write_text("dirty\n", encoding="utf-8")

        result = _run(["push", "--name", "alpha", "--set-upstream"], env=self.env)
        self._assert_ok(result)
        self.assertIn("警告: 仓库仍有未提交改动", result.stderr)


if __name__ == "__main__":
    unittest.main()
