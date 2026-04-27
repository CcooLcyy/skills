from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class SkillStructureTests(unittest.TestCase):
    def test_new_skills_are_listed_in_readme(self) -> None:
        readme = _read(REPO_ROOT / "README.md")

        self.assertIn("- `draw-image`：", readme)
        self.assertIn("- `repo-devcontainer`：", readme)

    def test_draw_image_skill_structure(self) -> None:
        skill_dir = REPO_ROOT / "skills" / "draw-image"
        skill = _read(skill_dir / "SKILL.md")
        agent = _read(skill_dir / "agents" / "openai.yaml")
        script = skill_dir / "scripts" / "probe_provider.py"

        self.assertIn("name: draw-image", skill)
        self.assertIn("GPT Image 2.0", skill)
        self.assertIn("base_url", skill)
        self.assertIn("GPT_IMAGE_API_KEY", skill)
        self.assertTrue(script.is_file())
        self.assertIn('display_name: "画图"', agent)
        self.assertIn("$draw-image", agent)

    def test_repo_devcontainer_skill_structure(self) -> None:
        skill_dir = REPO_ROOT / "skills" / "repo-devcontainer"
        skill = _read(skill_dir / "SKILL.md")
        agent = _read(skill_dir / "agents" / "openai.yaml")
        references = _read(skill_dir / "references" / "patterns.md")

        self.assertIn("name: repo-devcontainer", skill)
        self.assertIn("Dev Container", skill)
        self.assertIn("assets/templates/", skill)
        self.assertIn("CMake / C++", references)
        self.assertIn("Docker Socket", references)
        self.assertIn('display_name: "仓库开发容器"', agent)
        self.assertIn("$repo-devcontainer", agent)
        self.assertIn("链接 `config.toml`、`auth.json`", skill)
        self.assertNotIn("复制 `auth.json`", skill)

    def test_repo_devcontainer_auth_template_uses_live_link(self) -> None:
        template = _read(
            REPO_ROOT
            / "skills"
            / "repo-devcontainer"
            / "assets"
            / "templates"
            / "init_repo_dev.sh.template"
        )

        self.assertIn('link_codex_sync_entry "auth.json"', template)
        self.assertNotIn("install -m 600", template)
        self.assertNotIn("cmp -s", template)

    def test_repo_devcontainer_templates_keep_required_placeholders(self) -> None:
        template_dir = REPO_ROOT / "skills" / "repo-devcontainer" / "assets" / "templates"
        expected = {
            "Dockerfile.template": [
                "{{BASE_IMAGE}}",
                "{{APT_PACKAGES}}",
                "{{INIT_SCRIPT_REL}}",
                "{{CONTAINER_WORKDIR}}",
            ],
            "devcontainer.json.template": [
                "{{HOST_REPO_ROOT}}",
                "{{CONTAINER_WORKDIR}}",
                "{{CODEX_HOME_VOLUME}}",
                "{{VSCODE_EXTENSIONS}}",
            ],
            "start_repo_dev.sh.template": [
                "{{IMAGE_TAG}}",
                "{{CONTAINER_NAME}}",
                "{{CREATE_EXTRA_VOLUMES}}",
                "{{EXTRA_DOCKER_RUN_ARGS}}",
            ],
            "init_repo_dev.sh.template": [
                "{{REPO_SLUG}}",
                "{{CONTAINER_WORKDIR}}",
                "{{CUSTOM_INIT_COMMANDS}}",
            ],
        }

        for file_name, placeholders in expected.items():
            with self.subTest(file_name=file_name):
                content = _read(template_dir / file_name)
                for placeholder in placeholders:
                    self.assertIn(placeholder, content)


if __name__ == "__main__":
    unittest.main()
