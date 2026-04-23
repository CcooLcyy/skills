# Embeds 参考

## 嵌入笔记

```markdown
![[Note Name]]
![[Note Name#Heading]]
![[Note Name#^block-id]]
```

## 嵌入图片

```markdown
![[image.png]]
![[image.png|640x480]]    宽 x 高
![[image.png|300]]        只指定宽度，自动保持比例
```

## 外链图片

```markdown
![Alt text](https://example.com/image.png)
![Alt text|300](https://example.com/image.png)
```

## 嵌入音频

```markdown
![[audio.mp3]]
![[audio.ogg]]
```

## 嵌入 PDF

```markdown
![[document.pdf]]
![[document.pdf#page=3]]
![[document.pdf#height=400]]
```

## 嵌入列表

```markdown
![[Note#^list-id]]
```

其中列表需要先定义块 ID：

```markdown
- 项目 1
- 项目 2
- 项目 3

^list-id
```

## 嵌入搜索结果

````markdown
```query
tag:#project status:done
```
````
