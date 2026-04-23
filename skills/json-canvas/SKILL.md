---
name: json-canvas
description: 创建和编辑 JSON Canvas 文件（`.canvas`），支持节点、连线、分组和它们之间的关系。处理 `.canvas` 文件、绘制可视化画布、思维导图、流程图，或用户提到 Obsidian Canvas 文件时使用。
---

# JSON Canvas

## 文件结构

`.canvas` 文件遵循 [JSON Canvas Spec 1.0](https://jsoncanvas.org/spec/1.0/)，顶层包含两个数组：

```json
{
  "nodes": [],
  "edges": []
}
```

- `nodes`：可选，节点对象数组
- `edges`：可选，连接节点的边对象数组

## 常见工作流

### 1. 创建新画布

1. 先创建一个基础 `.canvas` 文件：`{"nodes": [], "edges": []}`
2. 为每个节点生成唯一的 16 位十六进制 ID，例如 `"6f0ad84f44ce9c17"`
3. 添加节点时，至少提供 `id`、`type`、`x`、`y`、`width`、`height`
4. 添加边时，`fromNode` 和 `toNode` 必须引用已有节点 ID
5. **校验**：确保 JSON 能正常解析，并确认所有 `fromNode` / `toNode` 都能在 `nodes` 中找到

### 2. 给现有画布添加节点

1. 读取并解析现有 `.canvas` 文件
2. 生成一个不会和现有节点或边冲突的新 ID
3. 选择不与现有节点重叠的位置，通常预留 `50-100px` 间距
4. 把新节点追加到 `nodes` 数组
5. 如果需要，再新增边把新节点连接到已有节点
6. **校验**：确认所有 ID 唯一，且所有边引用的节点都存在

### 3. 连接两个节点

1. 先确认源节点与目标节点的 ID
2. 生成新的边 ID
3. 设置 `fromNode` 与 `toNode`
4. 需要控制锚点时，设置 `fromSide` / `toSide`，可选值为 `top`、`right`、`bottom`、`left`
5. 需要显示说明文字时，设置 `label`
6. 把边追加到 `edges` 数组
7. **校验**：再次确认 `fromNode` 和 `toNode` 都指向存在的节点

### 4. 编辑现有画布

1. 读取并解析 `.canvas` 文件
2. 通过 `id` 找到目标节点或边
3. 修改需要变更的属性，例如文本、位置、颜色
4. 将更新后的 JSON 写回文件
5. **校验**：编辑后重新检查 ID 唯一性和边引用完整性

## 节点

节点是放在画布上的对象。`nodes` 数组的顺序决定了 Z 轴层级：越靠前越在底层，越靠后越在顶层。

### 通用节点属性

| 属性 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `id` | 是 | string | 唯一的 16 位十六进制标识符 |
| `type` | 是 | string | `text`、`file`、`link` 或 `group` |
| `x` | 是 | integer | X 坐标，单位像素 |
| `y` | 是 | integer | Y 坐标，单位像素 |
| `width` | 是 | integer | 宽度，单位像素 |
| `height` | 是 | integer | 高度，单位像素 |
| `color` | 否 | canvasColor | 预设值 `"1"`-`"6"`，或十六进制颜色，如 `"#FF0000"` |

### 文本节点

| 属性 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `text` | 是 | string | 支持 Markdown 的纯文本 |

```json
{
  "id": "6f0ad84f44ce9c17",
  "type": "text",
  "x": 0,
  "y": 0,
  "width": 400,
  "height": 200,
  "text": "# 你好\n\n这是一段 **Markdown** 内容。"
}
```

**换行陷阱**：JSON 字符串里的换行要写成 `\n`，不要写字面量 `\\n`，否则 Obsidian 会把它显示成字符 `\` 和 `n`。

### 文件节点

| 属性 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `file` | 是 | string | 文件系统中的路径 |
| `subpath` | 否 | string | 指向标题或块的子路径，以 `#` 开头 |

```json
{
  "id": "a1b2c3d4e5f67890",
  "type": "file",
  "x": 500,
  "y": 0,
  "width": 400,
  "height": 300,
  "file": "Attachments/diagram.png"
}
```

### 链接节点

| 属性 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `url` | 是 | string | 外部 URL |

```json
{
  "id": "c3d4e5f678901234",
  "type": "link",
  "x": 1000,
  "y": 0,
  "width": 400,
  "height": 200,
  "url": "https://obsidian.md"
}
```

### 分组节点

分组是用于承载其他节点的视觉容器。把子节点放在分组范围内，整体会更清晰。

| 属性 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `label` | 否 | string | 分组标题 |
| `background` | 否 | string | 背景图路径 |
| `backgroundStyle` | 否 | string | `cover`、`ratio` 或 `repeat` |

```json
{
  "id": "d4e5f6789012345a",
  "type": "group",
  "x": -50,
  "y": -50,
  "width": 1000,
  "height": 600,
  "label": "项目总览",
  "color": "4"
}
```

## 连线

边通过 `fromNode` 和 `toNode` 把两个节点连接起来。

| 属性 | 必填 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | 是 | string | - | 唯一标识符 |
| `fromNode` | 是 | string | - | 源节点 ID |
| `fromSide` | 否 | string | - | `top`、`right`、`bottom` 或 `left` |
| `fromEnd` | 否 | string | `none` | `none` 或 `arrow` |
| `toNode` | 是 | string | - | 目标节点 ID |
| `toSide` | 否 | string | - | `top`、`right`、`bottom` 或 `left` |
| `toEnd` | 否 | string | `arrow` | `none` 或 `arrow` |
| `color` | 否 | canvasColor | - | 线条颜色 |
| `label` | 否 | string | - | 线上的说明文字 |

```json
{
  "id": "0123456789abcdef",
  "fromNode": "6f0ad84f44ce9c17",
  "fromSide": "right",
  "toNode": "a1b2c3d4e5f67890",
  "toSide": "left",
  "toEnd": "arrow",
  "label": "指向"
}
```

## 颜色

`canvasColor` 可以使用十六进制颜色，也可以使用预设数字：

| 预设值 | 颜色 |
|--------|------|
| `"1"` | 红色 |
| `"2"` | 橙色 |
| `"3"` | 黄色 |
| `"4"` | 绿色 |
| `"5"` | 青色 |
| `"6"` | 紫色 |

预设值本身没有固定 RGB，具体外观取决于使用该规范的应用配色。

## ID 生成

统一使用 16 位小写十六进制字符串：

```text
"6f0ad84f44ce9c17"
"a3b2c1d0e9f8a7b6"
```

## 布局建议

- 坐标允许为负值，画布是无限延展的
- `x` 向右递增，`y` 向下递增，坐标表示左上角位置
- 节点之间建议留 `50-100px` 间距
- 分组内部建议保留 `20-50px` 内边距
- 为了更整齐，尽量按 `10` 或 `20` 的倍数对齐

| 节点类型 | 建议宽度 | 建议高度 |
|----------|----------|----------|
| 小文本 | 200-300 | 80-150 |
| 中文本 | 300-450 | 150-300 |
| 大文本 | 400-600 | 300-500 |
| 文件预览 | 300-500 | 200-400 |
| 链接预览 | 250-400 | 100-200 |

## 校验清单

创建或编辑 `.canvas` 文件后，至少检查：

1. 所有 `id` 在节点和边之间都唯一
2. 每个 `fromNode` 与 `toNode` 都指向已有节点
3. 每种节点都具备必填字段：文本节点有 `text`，文件节点有 `file`，链接节点有 `url`
4. `type` 只能是 `text`、`file`、`link`、`group`
5. `fromSide` / `toSide` 只能是 `top`、`right`、`bottom`、`left`
6. `fromEnd` / `toEnd` 只能是 `none`、`arrow`
7. 颜色要么是 `"1"` 到 `"6"`，要么是合法十六进制值，例如 `"#FF0000"`
8. JSON 本身必须可解析

如果校验失败，优先检查：重复 ID、悬空的边引用、以及文本内容里没有正确转义的换行。

## 完整示例

查看 [references/EXAMPLES.md](references/EXAMPLES.md) 获取完整示例，包括思维导图、项目看板、研究画布和流程图。

## 参考资料

- [JSON Canvas Spec 1.0](https://jsoncanvas.org/spec/1.0/)
- [JSON Canvas GitHub](https://github.com/obsidianmd/jsoncanvas)
