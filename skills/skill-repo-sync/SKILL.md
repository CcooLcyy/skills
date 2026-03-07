---
name: skill-repo-sync
description: 用于对由 skill-dev-link 接入的 Codex skill 仓库执行 Git 状态查看、远程拉取、推送等同步操作。用户只说“同步”而未细分动作时，默认直接同步远程和本地。当用户希望同步远程 skill 仓库、把本地 skill 改动推送到远程，或让其他 skill 统一转调仓库同步能力时使用。
---

# Skill Repo Sync

## 概述

这个 skill 只负责“仓库同步”，不负责安装覆盖，也不负责软链建立。

它读取 `~/.codex/skills/.dev-links.json`，通过 skill 名称定位对应的 Git 仓库，然后对该仓库执行 `sync`、`status`、`pull`、`push`。

注意：命令参数中的 `--name <skill-name>` 只是用来定位仓库；一旦执行 `sync`、`pull` 或 `push`，影响的是这个 skill 所在的整个仓库，而不是单个目录。

## 何时使用

- 用户希望直接把远程和本地 skill 仓库同步起来时
- 用户希望查看某个已接入 skill 所在仓库的 Git 状态时
- 用户希望把远程 skill 仓库拉取到本地时
- 用户希望把本地 skill 仓库中的提交推送到远程时
- 其他 skill 需要统一复用仓库同步能力时

## 工作流

### 1. 解析 skill 对应仓库

- 优先根据 `--repo-dir` 直接使用指定仓库
- 未指定时，读取 `~/.codex/skills/.dev-links.json`
- 从 `links.<skill-name>.repo_dir` 找到仓库目录
- 若找不到记录或仓库不是 Git 仓库，则直接报错

### 2. 默认同步远程和本地

- 用户只说“同步 skill 仓库”时，默认使用 `sync --name <skill-name>`
- 执行顺序是先 `pull`，再 `push`
- 若仓库存在未提交改动，默认停止；如确认需要临时搁置本地改动再拉取，可加 `--autostash`

示例：

- `python3 scripts/repo_sync.py sync --name git-commit`
- `python3 scripts/repo_sync.py sync --name git-commit --rebase`

### 3. 查看仓库状态

- 使用 `status --name <skill-name>`
- 输出 skill 名、仓库目录、链接源目录以及 `git status -sb`

示例：

- `python3 scripts/repo_sync.py status --name git-commit`
- `python3 scripts/repo_sync.py status --name git-commit --repo-dir /data/code/skills`

### 4. 拉取远程改动

- 使用 `pull --name <skill-name>`
- 若仓库存在未提交改动，默认停止，避免把未提交更改和拉取动作混在一起
- 如确认需要临时搁置本地改动再拉取，可加 `--autostash`
- 如希望保持线性历史，可加 `--rebase`

示例：

- `python3 scripts/repo_sync.py pull --name git-commit`
- `python3 scripts/repo_sync.py pull --name git-commit --rebase`
- `python3 scripts/repo_sync.py pull --name git-commit --rebase --autostash`

### 5. 推送本地提交

- 使用 `push --name <skill-name>`
- 默认执行 `git push`
- 若当前分支尚未配置上游分支，可加 `--set-upstream`
- 若仓库仍有未提交改动，会给出提示，但不会阻止推送已提交内容

示例：

- `python3 scripts/repo_sync.py push --name git-commit`
- `python3 scripts/repo_sync.py push --name git-commit --set-upstream`

## 安全约束

- 只对已接入 skill 所在的 Git 仓库做同步，不修改 `~/.codex/skills` 目录结构
- `pull` 在仓库不干净时默认拒绝执行，除非明确传入 `--autostash`
- 不自动提交改动，不自动创建提交信息
- 不自动强推远程分支

## 配合其他 skill

- `skill-dev-link` 负责建立 skill 到仓库的连接关系
- `git-commit` 负责整理改动并执行 `git commit`
- `skill-update` 可以把仓库同步类请求转调到本 skill 的脚本；仓库接入型 skill 的默认更新动作也可以直接落到本 skill 的 `sync`

## 资源

### `scripts/repo_sync.py`

- `sync`：直接同步 skill 对应仓库，先拉取再推送
- `status`：查看 skill 对应仓库的 Git 状态
- `pull`：从远程拉取仓库改动
- `push`：将本地仓库提交推送到远程
