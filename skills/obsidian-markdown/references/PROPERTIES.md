# Properties（Frontmatter）参考

属性通过 YAML frontmatter 写在笔记开头：

```yaml
---
title: 我的笔记标题
date: 2024-01-15
tags:
  - project
  - important
aliases:
  - 我的笔记
  - 备用名称
cssclasses:
  - custom-class
status: in-progress
rating: 4.5
completed: false
due: 2024-02-01T14:30:00
---
```

## 属性类型

| 类型 | 示例 |
|------|------|
| 文本 | `title: My Title` |
| 数字 | `rating: 4.5` |
| 复选框 | `completed: true` |
| 日期 | `date: 2024-01-15` |
| 日期时间 | `due: 2024-01-15T14:30:00` |
| 列表 | `tags: [one, two]` 或标准 YAML 列表 |
| 链接 | `related: "[[Other Note]]"` |

## 默认属性

- `tags`：笔记标签，可搜索，也会出现在图谱中
- `aliases`：笔记别名，会参与链接建议
- `cssclasses`：在阅读 / 编辑视图中附加到笔记的 CSS 类

## 标签

```markdown
#tag
#nested/tag
#tag-with-dashes
#tag_with_underscores
```

标签可以包含：

- 字母，支持任意语言
- 数字，但不能作为第一个字符
- 下划线 `_`
- 连字符 `-`
- 斜杠 `/`，可用于层级标签

在 frontmatter 里也可以这样写：

```yaml
---
tags:
  - tag1
  - nested/tag2
---
```
