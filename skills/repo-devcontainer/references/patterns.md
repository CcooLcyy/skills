# 仓库模式识别参考

只在需要判断目标仓库容器能力时读取本文件。不要机械套用全部内容；以仓库实际文件和文档为准。

## 通用探测清单

- 仓库说明：`README*`、`docs/`、`AGENTS.md`、`CONTRIBUTING*`
- 构建入口：`build.sh`、`package.sh`、`Makefile`、`CMakeLists.txt`、`CMakePresets.json`、`meson.build`、`configure`、`*.pro`
- 依赖管理：`vcpkg.json`、`vcpkg-configuration.json`、`conanfile.*`、`package.json`、`pnpm-lock.yaml`、`requirements.txt`、`pyproject.toml`、`go.mod`、`Cargo.toml`
- CI 线索：`.github/workflows/*`、`.gitlab-ci.yml`、`Jenkinsfile`、`Dockerfile`
- 交叉编译线索：工具链文件、`CMAKE_SYSTEM_PROCESSOR`、`CMAKE_TOOLCHAIN_FILE`、`aarch64`、`arm-linux`、`musl`、`sysroot`、`SDK`

## CMake / C++

证据：

- `CMakeLists.txt`
- `CMakePresets.json`
- `vcpkg.json` 或 `conanfile.*`

容器能力：

- 安装 `build-essential`、`cmake`、`ninja-build`、`git`、`pkg-config`、`ccache`。
- 如果有 `CMakePresets.json`，优先用 preset 验证。
- 如果使用 vcpkg，使用独立 volume 承载 `VCPKG_ROOT`、下载缓存和二进制缓存。
- 如果使用 Conan，缓存 `/root/.conan2` 或仓库既有 Conan home。

验证示例：

```bash
cmake --list-presets
cmake --preset <preset>
cmake --build --preset <preset>
```

## Make / Autotools

证据：

- `Makefile`
- `configure`
- `autogen.sh`

容器能力：

- 安装 `build-essential`、`make`、`autoconf`、`automake`、`libtool`、`pkg-config`。
- 如果 Makefile 依赖外部 SDK，先定位 SDK 输入和环境变量。

验证示例：

```bash
make -n
make -j"$(nproc)"
```

## qmake / Qt

证据：

- `*.pro`、`*.pri`
- README 提到 Qt/qmake

容器能力：

- 只有发现 qmake/Qt 证据时才启用 Qt 能力。
- 区分主机 Qt、交叉 Qt、仓库私有 SDK。
- 对大 SDK 使用 volume 或用户提供的目录/压缩包输入。

验证示例：

```bash
qmake -v
qmake <project.pro>
make -j"$(nproc)"
```

## Rust

证据：

- `Cargo.toml`
- `rust-toolchain.toml`

容器能力：

- 安装 Rust toolchain，优先按 `rust-toolchain.toml`。
- 缓存 `CARGO_HOME` 和 `target/`，是否缓存 `target/` 取决于仓库体量。

验证示例：

```bash
cargo check
cargo test
```

## Go

证据：

- `go.mod`
- `go.work`

容器能力：

- 安装 Go，版本优先读取 `go.mod`。
- 缓存 `GOMODCACHE` 和 `GOCACHE`。

验证示例：

```bash
go test ./...
go build ./...
```

## Node / 前端

证据：

- `package.json`
- `pnpm-lock.yaml`、`yarn.lock`、`package-lock.json`

容器能力：

- 按 lockfile 选择 pnpm/yarn/npm。
- 缓存包管理器目录，避免把 `node_modules` 做成镜像层。
- 如果是前端应用，启动 dev server 后给出 URL。

验证示例：

```bash
npm test
npm run build
pnpm test
pnpm build
```

## Python

证据：

- `pyproject.toml`
- `requirements.txt`
- `poetry.lock`、`uv.lock`

容器能力：

- 优先使用仓库声明的工具：uv、poetry、pip。
- 缓存 pip/uv/poetry 缓存目录。
- 不默认创建虚拟环境在源码目录，除非仓库已有约定。

验证示例：

```bash
python -m pytest
uv run pytest
poetry run pytest
```

## Docker Socket

只有以下情况才挂载 `/var/run/docker.sock`：

- 仓库构建脚本调用 `docker build`、`docker compose`、`docker load/save`。
- 发布流程需要在容器内构建镜像。
- 用户明确要求容器内能控制宿主 Docker。

挂载后必须在最终报告中说明该能力已启用。

## 多子仓库共享容器

适用场景：

- 一个父目录下有多个相关 Git 仓库。
- 多个仓库共享工具链、SDK 或包缓存。
- 打包流程要求串行构建多个子项目。

策略：

- 工作目录设为父目录，例如 `/workspace/<group>`。
- 对每个子仓库加入 `git safe.directory`。
- 明确标准构建顺序，避免并行执行会互相覆盖的打包脚本。
