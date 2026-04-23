---
name: defuddle
description: 使用 Defuddle CLI 从网页中提取干净的 Markdown 内容，去除导航、广告和杂项文本以节省 token。当用户提供 URL 需要阅读或分析普通网页、在线文档、文章或博客时，优先用它替代 WebFetch。不要用于以 .md 结尾的 URL，这类页面本身已经是 Markdown，应直接使用 WebFetch。
---

# Defuddle

使用 Defuddle CLI 从网页中提取可读性更高的正文内容。对于普通网页，优先于 WebFetch 使用，因为它会移除导航、广告和页面噪音，通常更省 token。

如果本机尚未安装：

```bash
npm install -g defuddle
```

## 用法

优先使用 `--md` 输出 Markdown：

```bash
defuddle parse <url> --md
```

保存到文件：

```bash
defuddle parse <url> --md -o content.md
```

提取指定元数据：

```bash
defuddle parse <url> -p title
defuddle parse <url> -p description
defuddle parse <url> -p domain
```

## 输出格式

| 参数 | 格式 |
|------|------|
| `--md` | Markdown，默认首选 |
| `--json` | 同时包含 HTML 与 Markdown 的 JSON |
| 不带参数 | HTML |
| `-p <name>` | 单个元数据字段 |
