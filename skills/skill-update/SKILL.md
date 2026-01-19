---
name: skill-update
description: 用于更新已安装的 Codex 技能。用户提出“更新/重装/批量更新技能”、希望从之前的安装来源自动刷新，或指定 $skill-name 要求更新时使用。
---

# Skill 更新

## 概述
用于从已记录的安装来源重新安装已安装技能，覆盖现有版本。

## 工作流
1. 确认更新范围
   - 识别用户提到的 $skill-name；未指定时询问是否更新全部或给出列表。
2. 确认技能目录与来源文件
   - 默认技能目录：`$CODEX_HOME/skills`（默认 `~/.codex/skills`）。
   - 默认来源文件：`$CODEX_HOME/skills/.skill-sources.json`。
3. 补齐来源记录
   - 若来源文件缺失或目标技能无记录，先收集来源信息并写入。
4. 执行更新
   - 运行 `scripts/update_skills.py update --all` 或 `--name <skill>`。
   - 采用覆盖式更新，安装成功后删除旧版本（失败时回滚）。
5. 收尾
   - 输出更新结果和失败原因。
   - 提醒重启 Codex 以加载新版本。

## 来源记录
- 使用 `scripts/update_skills.py add` 添加或更新来源。
- 支持 GitHub 安装源或本地路径源。
- 默认保存在 `$CODEX_HOME/skills/.skill-sources.json`，可通过 `--sources` 覆盖。
- 默认远程仓库：`https://github.com/CcooLcyy/skills.git`，`add` 省略 `--repo` 时使用（需提供 `--path`）。

示例（JSON）:
```json
{
  "version": 1,
  "skills": {
    "git-commit": {
      "repo": "CcooLcyy/skills",
      "path": "skills/git-commit",
      "ref": "main",
      "method": "auto"
    },
    "custom-skill": {
      "local_path": "/path/to/custom-skill"
    }
  }
}
```

## 常用命令
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py list`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py add --name git-commit --path skills/git-commit --ref main`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py add --name custom-skill --local-path /path/to/custom-skill`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py update --all`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py update --name git-commit`
