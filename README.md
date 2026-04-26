# 技能

此仓库存放 Codex 技能，统一放在 `skills/` 目录下。

当前公开 skill：

- `git-commit`：整理本地仓库提交流程与提交信息
- `skill-update`：统一管理技能来源更新、仓库接入与同步
- `defuddle`：用 Defuddle CLI 抽取网页正文，优先生成干净的 Markdown
- `json-canvas`：创建和编辑 Obsidian `.canvas` 文件
- `obsidian-bases`：创建和编辑 Obsidian `.base` 文件与视图配置
- `obsidian-cli`：通过 Obsidian CLI 操作 vault，并支持插件 / 主题开发调试
- `obsidian-markdown`：编写和维护 Obsidian 特有 Markdown 语法

每个技能位于独立目录中，包含：

- `SKILL.md`
- 可选的 `scripts/`、`references/`、`assets/`、`agents/`

新增或生成任何 skill 时，必须同时提供对应测试。纯文档型 skill 至少提供结构或内容校验；包含 `scripts/` 的 skill 必须覆盖核心命令或函数行为。测试优先放在 `tests/` 目录，并按现有测试风格命名。

示例结构：

```text
skills/
  skill-update/
    SKILL.md
    agents/
    scripts/
```

安装方式：

- 直接复制或创建软链接到 `$CODEX_HOME/skills`
- 使用 `skill-installer` 从仓库中的具体 skill 路径安装

对于技能管理相关需求，统一使用 `skill-update` 作为入口，不再单独安装或暴露仓库接入、仓库同步类 skill。

## Obsidian Skills

仓库已一次性收编以下 Obsidian 相关 skill：

- `defuddle`
- `json-canvas`
- `obsidian-bases`
- `obsidian-cli`
- `obsidian-markdown`

这些 skill 来源于 `kepano/obsidian-skills`，当前以本仓库为准进行本地维护，不设计远程同步或自动更新流程。每个 skill 目录都附带 `UPSTREAM.md` 记录导入基线 commit、导入日期和许可证信息。

使用前提：

- `obsidian-cli` 依赖本机已安装 `obsidian` CLI，且 Obsidian 应用正在运行
- `defuddle` 依赖本机可执行的 `defuddle` 命令

第三方许可证原文位于 `third_party/licenses/kepano-obsidian-skills-MIT.txt`。

打包产物建议放在 `dist/` 并忽略（`.skill` 文件）。
