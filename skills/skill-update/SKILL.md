---
name: skill-update
description: 用于统一管理 Codex skill 的来源更新、仓库接入与 Git 同步。用户提出更新或重装技能、把技能仓库接入本地开发、查看技能当前状态、同步仓库、拉取远程改动、推送本地提交等需求时使用。
---

# Skill 更新

## 概述

这个 skill 是技能管理的统一入口，负责两类事情：

- 普通安装型 skill 的来源记录与覆盖更新
- 仓库开发模式下的仓库登记、软链接入、状态查看、拉取推送同步与恢复

完成接入后，修改 `~/.codex/skills/<skill-name>`，实际上就是在修改仓库里的源码目录。

## 何时使用

- 用户希望更新、重装或批量维护本地已安装 skill 时
- 用户希望把 skill 仓库接入本地开发流程时
- 用户希望查看某个 skill 当前的来源记录、软链状态或所属仓库状态时
- 用户希望同步已接入 skill 所在仓库、拉取远程改动或推送本地提交时
- 用户希望撤销软链并恢复接入前的本地 skill 时

## 工作流

### 1. 普通安装型 skill：来源更新

1. 确认技能目录与来源文件
   - 默认技能目录：`$CODEX_HOME/skills`（默认 `~/.codex/skills`）
   - 默认来源文件：`$CODEX_HOME/skills/.skill-sources.json`
2. 补齐来源记录
   - 若来源文件缺失或目标技能无记录，先使用 `source-add` 写入来源信息
3. 检查是否有新内容
   - 从 GitHub 或本地路径取到临时目录
   - 与已安装版本做目录哈希对比
   - 无变化则输出“已是最新”
4. 执行更新
   - 默认更新全部：`update --all`
   - 指定技能更新：`update --name <skill>`
   - 采用覆盖式更新，失败回滚

### 2. 仓库开发模式：接入与同步

1. 登记或接入仓库
   - 使用 `connect`
   - 默认仓库是 `CcooLcyy/skills`
   - 默认工作区是 `$CODEX_HOME/skill-repos/CcooLcyy-skills`
   - 未指定 `--name`、`--all`、`--no-link` 时，默认链接仓库 `skills/` 下全部有效 skill
2. 查看状态
   - 使用 `status`
   - `--name <skill-name>` 时优先显示该 skill 的接入记录、软链状态、备份状态，以及所属仓库的 `git status -sb`
3. 同步仓库
   - 使用 `sync --name <skill-name>`
   - 执行顺序是先 `pull`，再 `push`
   - 若仓库存在未提交改动，默认停止；如确认需要临时搁置本地改动再拉取，可加 `--autostash`
4. 单独拉取或推送
   - 使用 `pull --name <skill-name>` 或 `push --name <skill-name>`
5. 恢复本地 skill
   - 使用 `restore --name <skill-name>` 删除软链并恢复备份目录

## 安全约束

- 接入时只会处理仓库 `skills/` 目录下带 `SKILL.md` 的有效 skill 目录
- 不会把整个 `~/.codex/skills` 或整个仓库目录做软链
- 创建软链前必须先备份原目标目录，除非目标已经是受管软链
- 遇到未托管软链时默认停止，不擅自覆盖
- 接入状态记录保存在 `~/.codex/skills/.dev-links.json`
- 来源记录保存在 `~/.codex/skills/.skill-sources.json`
- `pull` 在仓库不干净时默认拒绝执行，除非明确传入 `--autostash`
- 不自动提交改动，不自动强推远程分支

## 常用命令

- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py source-list`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py source-add --name git-commit --path skills/git-commit --ref main`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py update --all`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py connect --repo-dir /data/code/skills`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py connect --name git-commit --repo-dir /data/code/skills`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py status --name git-commit`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py sync --name git-commit`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py pull --name git-commit --rebase`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py push --name git-commit --set-upstream`
- `python3 $CODEX_HOME/skills/skill-update/scripts/update_skills.py restore --name git-commit`
