---
name: repo-devcontainer
description: 为已有代码仓库创建、补齐或修复可编译的 VS Code Dev Container 与 Docker 启动方案，并集成 Codex 配置同步。用户要求给某个仓库准备编译容器、开发容器、devcontainer、VS Code 容器打开、容器内 Codex 工作环境、构建工具链或仓库级一键启动脚本时使用。
---

# 仓库开发容器

## 目标

为目标仓库生成一套可实际使用的开发容器方案：能启动、能被 VS Code 打开、能在容器内运行 Codex、能执行仓库的最小编译或构建验证。

不要把现有项目样例当成固定模板。Qt、vcpkg、musl、Docker socket、交叉编译、SDK 初始化都只是按需启用的能力，不能默认假设。

## 工作流

1. 明确目标仓库
   - 如果用户没有给路径，使用当前工作目录。
   - 读取目标仓库内的 `AGENTS.md`、`README*`、`docs/`、构建脚本、CI 文件和包管理配置。
   - 先执行 `git status -sb`，避免覆盖用户未提交改动；所有编辑都必须保留用户已有改动。

2. 探测构建系统
   - 优先识别仓库已经使用的构建入口，不重造构建体系。
   - 常见模式和包管理判断见 `references/patterns.md`，只在需要细节时读取。
   - 记录最小 smoke 命令，例如 `cmake --preset x64`、`cmake --build --preset x64`、`make -n`、`qmake -v`、`cargo check`、`go test ./...`、`npm test`。

3. 设计容器能力
   - 默认使用目标仓库实际路径做 bind mount，容器内路径默认 `/workspace/<repo-name>`。
   - 如果仓库已有明确路径约定，例如 `/data/code/<repo>`，优先沿用既有约定。
   - 只安装被仓库证据支持的工具链和包管理器。
   - 对大目录和缓存使用 volume，例如 `ccache`、vcpkg root/cache、Conan cache、Cargo registry、Go build cache、npm/pnpm cache、SDK 或交叉工具链输出。
   - 只有仓库构建或打包需要构建镜像时，才挂载 Docker socket。

4. 生成或更新文件
   - `.devcontainer/Dockerfile`
   - `.devcontainer/devcontainer.json`
   - `script/devcontainer/start_<repo>_dev.sh`，如果仓库已有 `scripts/` 约定则沿用。
   - 可选：`script/devcontainer/init_<repo>_dev.sh`，用于 Codex 同步、工具链初始化、缓存目录准备和 safe.directory。
   - 模板见 `assets/templates/`。复制模板后必须替换占位符，并按仓库实际情况删减。

5. 集成 Codex
   - 宿主机 Codex 目录只读挂载到 `/codex-sync`。
   - 容器内 Codex home 使用独立 volume，默认 `/root/.codex`。
   - 初始化脚本中链接 `config.toml`、`auth.json`、`AGENTS.md`、`skills/`，不要让容器直接写宿主机 Codex 目录。

6. 验证
   - 构建镜像并启动容器。
   - 检查容器仍在运行、工作目录正确、Codex 文件可见、关键工具链版本可输出。
   - 执行最小 smoke 构建验证。不要默认跑完整发布打包，除非用户要求或仓库文档明确这是最小验证。
   - 报告容器名、镜像名、进入命令、VS Code 打开方式、验证结果和未决风险。

## 生成约定

- 所有新增说明文档使用中文。
- 默认容器名：`<repo-name>-dev`。
- 默认镜像名：`<repo-name>-dev:ubuntu24.04`，除非仓库需要其他基础系统。
- 默认远程用户可使用 `root`，因为很多旧仓库和交叉工具链依赖 root 安装路径；如果仓库已有非 root 约定则沿用。
- `devcontainer.json` 必须让 VS Code 能打开目标仓库，并安装与语言匹配的扩展。
- 启动脚本必须支持 `--recreate` 和 `--no-build`。
- 初始化脚本必须可重复执行，重复启动不能破坏已有缓存和源码。
- 验证失败时保留已生成文件，说明失败命令和下一步修复点。

## 何时读取资源

- 需要判断仓库类型、工具链和缓存策略时，读取 `references/patterns.md`。
- 需要生成文件时，使用 `assets/templates/` 下的模板作为起点：
  - `Dockerfile.template`
  - `devcontainer.json.template`
  - `start_repo_dev.sh.template`
  - `init_repo_dev.sh.template`

## 输出要求

完成后用简短中文说明：

- 创建或修改了哪些文件。
- 容器名、镜像名、源码挂载路径和容器工作目录。
- 如何启动容器、如何进入容器、如何用 VS Code 打开。
- 已执行的验证命令和结果。
- 哪些能力是按需启用的，例如 vcpkg、Conan、Docker socket、交叉工具链、SDK。
