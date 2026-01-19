# 技能

此仓库存放 Codex 技能，统一放在 `skills/` 目录下。
每个技能位于独立目录中，包含：
- SKILL.md
- 可选的 scripts/、references/、assets/

示例结构：

skills/
  git-commit/
    SKILL.md
    scripts/
    references/
    assets/

安装方式：
- 直接复制或创建软链接到 `$CODEX_HOME/skills`
- 使用 skill-installer：
  scripts/install-skill-from-github.py --repo <owner>/<repo> --path skills/git-commit

打包产物建议放在 `dist/` 并忽略（.skill 文件）。
