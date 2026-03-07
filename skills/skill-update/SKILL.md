---
name: skill-update
description: 用于统一管理 Codex skill 的更新与同步。既支持按来源记录重装普通安装型 skill，也支持把已通过 skill-dev-link 接入仓库的 skill 统一做仓库状态查看、远程拉取和远程推送。对仓库接入型 skill，用户未明确指定动作时，默认直接同步远程和本地。当用户提出“更新/重装/批量更新技能”或“同步 skill 仓库、拉取远程、推送本地 skill 改动”时使用。
---

# Skill 更新

## 概述

这个 skill 是统一入口，负责两类事情：

- 普通安装型 skill 的来源记录与覆盖更新
- 已通过 `skill-dev-link` 接入仓库的 skill 的仓库同步

其中仓库同步能力由 `skill-repo-sync` 的脚本承接；`skill-update` 负责统一对外入口。

对仓库接入型 skill，如果用户只说“更新 skill”“同步 skill”而没有额外指定查看状态、只拉取或只推送，默认动作是直接同步远程和本地，也就是先拉取、再推送。

## 工作流

### 1. 普通安装型 skill：来源更新

1. 确认技能目录与来源文件
   - 默认技能目录：`$CODEX_HOME/skills`（默认 `~/.codex/skills`）
   - 默认来源文件：`$CODEX_HOME/skills/.skill-sources.json`
2. 补齐来源记录
   - 若来源文件缺失或目标技能无记录，先使用 `add` 写入来源信息
3. 检查是否有新内容
   - 从 GitHub 或本地路径拉取到临时目录
   - 与已安装版本做目录哈希对比
   - 无变化则输出“已是最新”
4. 执行更新
   - 默认更新全部：`update --all`
   - 指定技能更新：`update --name <skill>`
   - 采用覆盖式更新，失败回滚
5. 收尾
   - 输出更新结果
   - 提醒重启 Codex 以加载新版本

### 2. 仓库接入型 skill：仓库同步

1. 识别 skill 是否由 `skill-dev-link` 接入
   - 通过 `~/.codex/skills/.dev-links.json` 定位 skill 所在仓库
2. 默认同步远程和本地
   - 用户未明确指定子动作时，默认使用 `repo-sync --name <skill>`
   - 执行顺序是先 `repo-pull`，再 `repo-push`
   - 若本地有未提交改动，默认停止；如确需自动暂存再拉取，可加 `--autostash`
3. 查看仓库状态
   - 使用 `repo-status --name <skill>`
4. 拉取远程改动
   - 使用 `repo-pull --name <skill>`
   - 若本地有未提交改动，默认停止；如确需自动暂存再拉取，可加 `--autostash`
5. 推送本地提交
   - 使用 `repo-push --name <skill>`
   - 仅推送已有提交，不自动提交工作区改动

## 来源记录

- 使用 `scripts/update_skills.py add` 添加或更新来源
- 支持 GitHub 安装源或本地路径源
- 默认保存在 `$CODEX_HOME/skills/.skill-sources.json`
- 默认远程仓库：`https://github.com/CcooLcyy/skills.git`，`add` 省略 `--repo` 时使用（需提供 `--path`）

## 软链保护

- 如果目标 skill 当前是软链，普通 `update` 会拒绝覆盖
- 这是为了避免破坏 `skill-dev-link` 建立的仓库连接关系
- 遇到这类 skill，请改用 `repo-sync`、`repo-status`、`repo-pull`、`repo-push`
- 若软链已经被其他操作破坏，可再用 `skill-dev-link` 重新连接

## 常用命令

- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py list`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py add --name git-commit --path skills/git-commit --ref main`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py update --all`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py update --name git-commit`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py repo-sync --name git-commit`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py repo-status --name git-commit`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py repo-pull --name git-commit --rebase`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py repo-push --name git-commit`
