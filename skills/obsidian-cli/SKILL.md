---
name: obsidian-cli
description: 使用 Obsidian CLI 与运行中的 Obsidian vault 交互，读取、创建、搜索和管理笔记、任务、属性等内容；也支持插件与主题开发时的重载、执行 JavaScript、查看错误、截图和 DOM 检查。当用户要在命令行里操作 Obsidian、管理 vault 内容，或开发调试 Obsidian 插件和主题时使用。
---

# Obsidian CLI

使用 `obsidian` CLI 与正在运行的 Obsidian 实例交互。前提是 Obsidian 应用已经打开。

## 命令参考

执行 `obsidian help` 查看当前可用命令，这是最准确的实时说明。完整文档：<https://help.obsidian.md/cli>

## 语法

**参数** 使用 `=` 传值。值里有空格时要加引号：

```bash
obsidian create name="我的笔记" content="你好，世界"
```

**标志位** 是不带值的布尔开关：

```bash
obsidian create name="我的笔记" silent overwrite
```

多行内容请用 `\n` 表示换行，`\t` 表示制表符。

## 文件定位

很多命令接受 `file` 或 `path` 来指定目标文件。不传时默认作用于当前活动文件。

- `file=<name>`：按 wikilink 方式解析，只写名称即可，不必带路径和扩展名
- `path=<path>`：从 vault 根目录开始的精确路径，例如 `folder/note.md`

## Vault 定位

默认命中最近获得焦点的 vault。若要指定 vault，把 `vault=<name>` 放在命令最前面：

```bash
obsidian vault="My Vault" search query="测试"
```

## 常见模式

```bash
obsidian read file="My Note"
obsidian create name="New Note" content="# Hello" template="Template" silent
obsidian append file="My Note" content="New line"
obsidian search query="search term" limit=10
obsidian daily:read
obsidian daily:append content="- [ ] New task"
obsidian property:set name="status" value="done" file="My Note"
obsidian tasks daily todo
obsidian tags sort=count counts
obsidian backlinks file="My Note"
```

任意命令都可以加 `--copy` 把输出复制到剪贴板。加 `silent` 可以避免自动打开文件。列表类命令加 `total` 可以只返回数量。

## 插件开发

### 开发 / 测试循环

修改插件或主题代码后，建议按这个顺序验证：

1. **重载插件**，让改动生效：

   ```bash
   obsidian plugin:reload id=my-plugin
   ```

2. **查看错误**。如果出现报错，修复后再从第 1 步开始：

   ```bash
   obsidian dev:errors
   ```

3. **做视觉确认**，可截图或检查 DOM：

   ```bash
   obsidian dev:screenshot path=screenshot.png
   obsidian dev:dom selector=".workspace-leaf" text
   ```

4. **检查控制台输出**，看是否有异常日志或警告：

   ```bash
   obsidian dev:console level=error
   ```

### 其他开发命令

在应用上下文内执行 JavaScript：

```bash
obsidian eval code="app.vault.getFiles().length"
```

检查 CSS 属性：

```bash
obsidian dev:css selector=".workspace-leaf" prop=background-color
```

切换移动端模拟：

```bash
obsidian dev:mobile on
```

更多开发相关命令，包括 CDP 与调试器控制，也都可以通过 `obsidian help` 查看。
