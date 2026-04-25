---
name: codex-context-guard
description: 当需要检查、修复或重新应用 Codex 上下文窗口配置时使用本技能，尤其适用于 VS Code Codex 扩展更新、重装、WSL/远端环境切换或模型目录漂移之后。它会验证当前 Codex CLI 或 VS Code 扩展捆绑 CLI，按需重新生成用户级 model_catalog_json，并更新 config.toml，让新 Codex 会话使用期望的上下文窗口。
---

# Codex Context Guard

## 用途

本技能用于保护用户级 Codex 上下文窗口覆盖配置，避免扩展更新、重装或运行环境切换后退回默认模型目录。它特别面向 VS Code Codex 扩展，因为 VS Code UI 中显示的有效窗口来自扩展/app-server 的运行时模型目录，而不只是 `config.toml` 中的裸配置值。

## 工作流

除非脚本报告明确阻塞，否则不要手工编辑 Codex 配置；优先运行随技能提供的脚本。

只检查：

```bash
python skills/codex-context-guard/scripts/codex_context_guard.py
```

检查并修复：

```bash
python skills/codex-context-guard/scripts/codex_context_guard.py --repair
```

VS Code Codex 扩展更新或重装后，即使当前可见数值看起来正确，也可以强制基于当前扩展二进制重新生成模型目录：

```bash
python skills/codex-context-guard/scripts/codex_context_guard.py --repair --force
```

如果当前环境需要 `python3`，将命令中的 `python` 替换为 `python3`。

## 目标选择

脚本默认使用 `--surface vscode`，因为主要目标是 VS Code Codex 扩展。选择顺序如下：

1. 正在运行的 VS Code Codex `app-server` 进程。
2. 当前操作系统环境中的最新版 VS Code 或 VS Code Server 扩展捆绑 CLI。
3. 仅在前两者找不到时，回退到 `PATH` 中的 `codex`。

这个区分很重要。全局 npm 安装的 `codex` CLI 不一定是 VS Code 扩展实际使用的二进制。

在 WSL、Remote SSH 或 Dev Container 中使用时，需要在对应环境里运行同一个脚本。脚本会检查该环境自己的 `~/.codex` 和 VS Code Server 扩展路径；Windows 用户级配置和 WSL 用户级配置彼此独立。

## 默认值

修复脚本默认使用：

- 目标模型：`config.toml` 顶层 `model`，未设置时为 `gpt-5.5`。
- 目标上下文窗口：`1000000`。
- 目标有效上下文百分比：`100`。
- 自动压缩阈值：`800000`。
- 配置文件路径：`$CODEX_HOME/config.toml`，未设置时为 `~/.codex/config.toml`。
- 模型目录路径：`$CODEX_HOME/model-catalog-1000k.json`，未设置时为 `~/.codex/model-catalog-1000k.json`。

需要调整时，使用 `--target-model`、`--context-window`、`--auto-compact`、`--codex-home`、`--config-path`、`--catalog-path` 或 `--codex` 覆盖。

## 验证

修复后，脚本会使用选中的 Codex 二进制运行 `codex debug models`，确认目标模型报告的上下文窗口与期望一致，并输出是否需要重启 VS Code。

如果修复前 VS Code app-server 已经在运行，需要提醒用户执行 `Developer: Reload Window` 或重启 Codex 扩展。旧会话会保留旧元数据；重载后的新会话才会使用修复后的模型目录。
