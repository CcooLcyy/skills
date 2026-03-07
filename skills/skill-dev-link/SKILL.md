---
name: skill-dev-link
description: 用于把 Git 仓库中的 Codex skills 接入本地 `~/.codex/skills` 开发流程，完成技能仓库的初始化或登记、默认全量链接仓库中的全部 skill、按需重连单个或全部 skill、检查链接状态、恢复原目录等操作。当用户希望边使用边修改 skill，并把修改直接纳入仓库提交时使用。
---

# Skill Dev Link

## 概述

这个 skill 用来把“正在运行的本地 skill 目录”和“Git 仓库中的 skill 源码目录”接起来。

默认行为是：仓库登记完成后，自动把仓库 `skills/` 目录下所有有效 skill 接到 `~/.codex/skills`。完成链接后，修改 `~/.codex/skills/<skill-name>`，实际上就是在修改仓库里的源码目录。

## 何时使用

- 用户希望把某个或全部 skill 接入 Git 仓库开发流程时
- 用户已经克隆了 skill 仓库，想把仓库中的全部 skill 默认接到 `~/.codex/skills` 时
- 用户想先备份原安装 skill，再切换到仓库版本时
- 用户想查看某个 skill 当前是否已链接、链接是否损坏、备份是否还在时
- 用户想撤销软链并恢复原安装 skill 时

## 工作流

### 1. 准备或登记仓库

- 优先运行 `scripts/manage_skill_links.py setup`
- 默认仓库是 `CcooLcyy/skills`
- 默认工作区是 `$CODEX_HOME/skill-repos/CcooLcyy-skills`，未设置 `CODEX_HOME` 时等价于 `~/.codex/skill-repos/CcooLcyy-skills`
- 如果仓库目录不存在，脚本会克隆仓库；如果已经存在，则只校验并登记
- `setup` 默认会在登记完成后，把仓库 `skills/` 下所有带 `SKILL.md` 的目录全部链接到 `~/.codex/skills`
- 如果只想登记仓库、不立即链接，可加 `--no-link-all`

示例：

- `python3 scripts/manage_skill_links.py setup`
- `python3 scripts/manage_skill_links.py setup --repo-dir /data/code/skills`
- `python3 scripts/manage_skill_links.py setup --no-link-all`
- `python3 scripts/manage_skill_links.py setup --repo CcooLcyy/skills --repo-url git@github.com:CcooLcyy/skills.git`

### 2. 链接单个或全部 skill

- 使用 `link --name <skill-name>` 处理单个 skill
- 使用 `link --all` 重新扫描仓库并批量链接全部 skill
- 默认把仓库中的 `skills/<skill-name>` 接到 `~/.codex/skills/<skill-name>`
- 如果 `~/.codex/skills/<skill-name>` 目前是普通目录或文件，脚本会先备份再创建软链
- 如果目标已经是指向同一源码目录的软链，直接提示“已链接”
- 如果目标已经是其他未托管软链，默认停止，避免误覆盖

示例：

- `python3 scripts/manage_skill_links.py link --name git-commit`
- `python3 scripts/manage_skill_links.py link --all`
- `python3 scripts/manage_skill_links.py link --all --repo-dir /data/code/skills`

### 3. 检查状态

- 使用 `status` 查看默认仓库和已记录的链接状态
- 可用 `--name <skill-name>` 只看某一个 skill
- 重点关注：目标是否仍为软链、软链是否指向预期源码目录、源目录是否还存在、备份是否可恢复

示例：

- `python3 scripts/manage_skill_links.py status`
- `python3 scripts/manage_skill_links.py status --name git-commit`

### 4. 恢复原安装 skill

- 使用 `restore --name <skill-name>` 删除软链并恢复备份目录
- 若当前没有备份，则只移除软链并删除记录
- 恢复后，该 skill 会回到软链前的本地安装版本

示例：

- `python3 scripts/manage_skill_links.py restore --name git-commit`

## 安全约束

- 默认全量链接的对象仅限仓库 `skills/` 目录下带 `SKILL.md` 的有效 skill 目录
- 不会把整个 `~/.codex/skills` 或整个仓库目录做软链
- `link` 前必须先备份原目标目录，除非目标已经是受管软链
- 遇到未托管软链时默认停止，不擅自覆盖
- 状态记录保存在 `~/.codex/skills/.dev-links.json`
- 备份目录默认放在 `~/.codex/skills/.dev-link-backups/`

## 配合提交

- 链接完成后，修改 `~/.codex/skills/<skill-name>` 就是在修改仓库源码
- 需要提交时，直接进入仓库目录执行 `git diff`、`git commit`、`git push`
- 若需要 Codex 帮你整理提交，可再调用 `git-commit` skill

## 资源

### `scripts/manage_skill_links.py`

- `setup`：初始化或登记 skill 仓库，并默认全量链接全部 skill
- `link --name`：备份原目录并创建单个 skill 软链
- `link --all`：重新扫描仓库并批量链接全部 skill
- `status`：查看默认仓库与各 skill 的链接状态
- `restore`：删除软链并恢复备份
