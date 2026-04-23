---
name: obsidian-bases
description: 创建和编辑 Obsidian Bases（`.base` 文件），支持视图、筛选器、公式和汇总。当处理 `.base` 文件、在 Obsidian 中创建类似数据库的笔记视图，或用户提到 Bases、表格视图、卡片视图、筛选器或公式时使用。
---

# Obsidian Bases

## 工作流

1. **创建文件**：在 vault 中创建合法 YAML 内容的 `.base` 文件
2. **定义范围**：通过 `filters` 选择要显示的笔记，可按标签、文件夹、属性或日期过滤
3. **添加公式**：如有需要，在 `formulas` 段定义计算属性
4. **配置视图**：添加一个或多个视图，类型可为 `table`、`cards`、`list` 或 `map`，并用 `order` 指定展示字段顺序
5. **校验**：确认 YAML 语法合法，没有语法错误；检查所有引用的属性和公式都存在。常见问题包括：
   `:` 等特殊字符未加引号、公式里的引号不匹配、在 `order` 或 `properties` 中引用了未定义的 `formula.X`
6. **在 Obsidian 中测试**：打开 `.base` 文件，确认视图能正常渲染；若 Obsidian 报 YAML 错误，优先检查引号规则

## Schema

`.base` 文件使用合法 YAML，并以 `.base` 为扩展名。

```yaml
# 全局 filters 作用于该 base 中的所有视图
filters:
  # 可以是单个过滤表达式
  # 也可以是 and / or / not 递归对象
  and: []
  or: []
  not: []

# 定义可在各视图中复用的公式属性
formulas:
  formula_name: 'expression'

# 配置属性的显示名与设置
properties:
  property_name:
    displayName: "显示名"
  formula.formula_name:
    displayName: "公式显示名"
  file.ext:
    displayName: "扩展名"

# 定义自定义汇总公式
summaries:
  custom_summary_name: 'values.mean().round(3)'

# 配置一个或多个视图
views:
  - type: table | cards | list | map
    name: "视图名称"
    limit: 10                    # 可选：限制结果数
    groupBy:                     # 可选：分组方式
      property: property_name
      direction: ASC | DESC
    filters:                     # 视图级过滤
      and: []
    order:                       # 要展示的属性顺序
      - file.name
      - property_name
      - formula.formula_name
    summaries:                   # 为属性映射汇总方式
      property_name: Average
```

## 过滤语法

筛选器用于缩小结果范围，既可定义为全局过滤，也可在单个视图中覆盖。

### 过滤结构

```yaml
# 单条过滤
filters: 'status == "done"'

# AND：所有条件都必须满足
filters:
  and:
    - 'status == "done"'
    - 'priority > 3'

# OR：任一条件满足即可
filters:
  or:
    - 'file.hasTag("book")'
    - 'file.hasTag("article")'

# NOT：排除匹配项
filters:
  not:
    - 'file.hasTag("archived")'

# 嵌套过滤
filters:
  or:
    - file.hasTag("tag")
    - and:
        - file.hasTag("book")
        - file.hasLink("Textbook")
    - not:
        - file.hasTag("book")
        - file.inFolder("Required Reading")
```

### 过滤操作符

| 操作符 | 说明 |
|--------|------|
| `==` | 等于 |
| `!=` | 不等于 |
| `>` | 大于 |
| `<` | 小于 |
| `>=` | 大于等于 |
| `<=` | 小于等于 |
| `&&` | 逻辑与 |
| `\|\|` | 逻辑或 |
| `!` | 逻辑非 |

## 属性

### 三类属性

1. **笔记属性**：来自 frontmatter，例如 `note.author` 或直接写 `author`
2. **文件属性**：文件元数据，例如 `file.name`、`file.mtime`
3. **公式属性**：计算结果，例如 `formula.my_formula`

### 文件属性参考

| 属性 | 类型 | 说明 |
|------|------|------|
| `file.name` | String | 文件名 |
| `file.basename` | String | 不含扩展名的文件名 |
| `file.path` | String | 文件完整路径 |
| `file.folder` | String | 父文件夹路径 |
| `file.ext` | String | 文件扩展名 |
| `file.size` | Number | 文件大小，单位字节 |
| `file.ctime` | Date | 创建时间 |
| `file.mtime` | Date | 修改时间 |
| `file.tags` | List | 文件内全部标签 |
| `file.links` | List | 文件里的内部链接 |
| `file.backlinks` | List | 链接到当前文件的其他文件 |
| `file.embeds` | List | 当前笔记中的嵌入内容 |
| `file.properties` | Object | frontmatter 全部属性 |

### `this` 关键字

- 在主内容区使用时：指向当前 `.base` 文件自身
- 作为嵌入内容显示时：指向嵌入它的文件
- 在侧边栏中使用时：指向主内容区当前激活的文件

## 公式语法

公式从属性中计算值，统一定义在 `formulas` 段。

```yaml
formulas:
  # 简单算术
  total: "price * quantity"

  # 条件逻辑
  status_icon: 'if(done, "✅", "⏳")'

  # 字符串格式化
  formatted_price: 'if(price, price.toFixed(2) + " 元")'

  # 日期格式化
  created: 'file.ctime.format("YYYY-MM-DD")'

  # 计算距创建已过天数（Duration 需要先取 .days）
  days_old: '(now() - file.ctime).days'

  # 计算距离截止日期还剩多少天
  days_until_due: 'if(due_date, (date(due_date) - today()).days, "")'
```

## 常用函数

这里只列最常用的一部分。完整类型与函数列表见 [FUNCTIONS_REFERENCE.md](references/FUNCTIONS_REFERENCE.md)。

| 函数 | 签名 | 说明 |
|------|------|------|
| `date()` | `date(string): date` | 把字符串解析成日期，格式为 `YYYY-MM-DD HH:mm:ss` |
| `now()` | `now(): date` | 当前日期和时间 |
| `today()` | `today(): date` | 当前日期，时间部分为 `00:00:00` |
| `if()` | `if(condition, trueResult, falseResult?)` | 条件判断 |
| `duration()` | `duration(string): duration` | 解析持续时间字符串 |
| `file()` | `file(path): file` | 获取文件对象 |
| `link()` | `link(path, display?): Link` | 创建链接 |

### Duration 类型

两个日期相减后得到的是 **Duration**，不是普通数字。

**字段：** `duration.days`、`duration.hours`、`duration.minutes`、`duration.seconds`、`duration.milliseconds`

**重要**：Duration 不能直接调用 `.round()`、`.floor()`、`.ceil()`。必须先取出数值字段，再做数值运算。

```yaml
# 正确：先取天数
"(date(due_date) - today()).days"
"(now() - file.ctime).days"
"(date(due_date) - today()).days.round(0)"

# 错误：Duration 不是 number
# "((date(due) - today()) / 86400000).round(0)"
```

### 日期运算

```yaml
# Duration 单位：y/year/years, M/month/months, d/day/days,
#                w/week/weeks, h/hour/hours, m/minute/minutes, s/second/seconds
"now() + \"1 day\""          # 明天
"today() + \"7d\""           # 一周后
"now() - file.ctime"         # 返回 Duration
"(now() - file.ctime).days"  # 取数值天数
```

## 视图类型

### Table 视图

```yaml
views:
  - type: table
    name: "我的表格"
    order:
      - file.name
      - status
      - due_date
    summaries:
      price: Sum
      count: Average
```

### Cards 视图

```yaml
views:
  - type: cards
    name: "画廊"
    order:
      - file.name
      - cover_image
      - description
```

### List 视图

```yaml
views:
  - type: list
    name: "简单列表"
    order:
      - file.name
      - status
```

### Map 视图

需要经纬度属性，并依赖 Maps 社区插件。

```yaml
views:
  - type: map
    name: "地点"
    # 这里填写地图视图对应的经纬度配置
```

## 默认汇总公式

| 名称 | 输入类型 | 说明 |
|------|----------|------|
| `Average` | Number | 平均值 |
| `Min` | Number | 最小值 |
| `Max` | Number | 最大值 |
| `Sum` | Number | 总和 |
| `Range` | Number | 最大值减最小值 |
| `Median` | Number | 中位数 |
| `Stddev` | Number | 标准差 |
| `Earliest` | Date | 最早日期 |
| `Latest` | Date | 最晚日期 |
| `Range` | Date | 最晚日期减最早日期 |
| `Checked` | Boolean | `true` 数量 |
| `Unchecked` | Boolean | `false` 数量 |
| `Empty` | Any | 空值数量 |
| `Filled` | Any | 非空值数量 |
| `Unique` | Any | 去重后的值数量 |

## 完整示例

### 任务追踪 Base

```yaml
filters:
  and:
    - file.hasTag("task")
    - 'file.ext == "md"'

formulas:
  days_until_due: 'if(due, (date(due) - today()).days, "")'
  is_overdue: 'if(due, date(due) < today() && status != "done", false)'
  priority_label: 'if(priority == 1, "🔴 高", if(priority == 2, "🟡 中", "🟢 低"))'

properties:
  status:
    displayName: 状态
  formula.days_until_due:
    displayName: "距截止天数"
  formula.priority_label:
    displayName: 优先级

views:
  - type: table
    name: "进行中的任务"
    filters:
      and:
        - 'status != "done"'
    order:
      - file.name
      - status
      - formula.priority_label
      - due
      - formula.days_until_due
    groupBy:
      property: status
      direction: ASC
    summaries:
      formula.days_until_due: Average

  - type: table
    name: "已完成"
    filters:
      and:
        - 'status == "done"'
    order:
      - file.name
      - completed_date
```

### 阅读清单 Base

```yaml
filters:
  or:
    - file.hasTag("book")
    - file.hasTag("article")

formulas:
  reading_time: 'if(pages, (pages * 2).toString() + " 分钟", "")'
  status_icon: 'if(status == "reading", "📖", if(status == "done", "✅", "📚"))'
  year_read: 'if(finished_date, date(finished_date).year, "")'

properties:
  author:
    displayName: 作者
  formula.status_icon:
    displayName: ""
  formula.reading_time:
    displayName: "预计时长"

views:
  - type: cards
    name: "藏书库"
    order:
      - cover
      - file.name
      - author
      - formula.status_icon
    filters:
      not:
        - 'status == "dropped"'

  - type: table
    name: "待读列表"
    filters:
      and:
        - 'status == "to-read"'
    order:
      - file.name
      - author
      - pages
      - formula.reading_time
```

### Daily Notes 索引

```yaml
filters:
  and:
    - file.inFolder("Daily Notes")
    - '/^\d{4}-\d{2}-\d{2}$/.matches(file.basename)'

formulas:
  word_estimate: '(file.size / 5).round(0)'
  day_of_week: 'date(file.basename).format("dddd")'

properties:
  formula.day_of_week:
    displayName: "星期"
  formula.word_estimate:
    displayName: "~字数"

views:
  - type: table
    name: "最近笔记"
    limit: 30
    order:
      - file.name
      - formula.day_of_week
      - formula.word_estimate
      - file.mtime
```

## 在 Markdown 中嵌入 Base

```markdown
![[MyBase.base]]

<!-- 指定某个视图 -->
![[MyBase.base#View Name]]
```

## YAML 引号规则

- 公式中如果包含双引号，外层优先用单引号：`'if(done, "Yes", "No")'`
- 普通字符串优先用双引号：`"我的视图名"`
- 复杂表达式里要正确转义嵌套引号

## 故障排查

### YAML 语法错误

**未引用的特殊字符**：字符串中如果出现 `:`、`{`、`}`、`[`、`]`、`,`、`&`、`*`、`#`、`?`、`|`、`-`、`<`、`>`、`=`、`!`、`%`、`@`、`` ` ``，通常都应加引号。

```yaml
# 错误：带冒号的字符串未加引号
displayName: Status: Active

# 正确
displayName: "Status: Active"
```

**公式中的引号不匹配**：当公式内部包含双引号时，整个公式外层应使用单引号。

```yaml
# 错误：双引号内又直接嵌入双引号
formulas:
  label: "if(done, "Yes", "No")"

# 正确：外层单引号包裹
formulas:
  label: 'if(done, "Yes", "No")'
```

### 常见公式错误

**Duration 未先取字段就做数学运算**：日期相减得到的是 Duration，而不是 Number。

```yaml
# 错误
"(now() - file.ctime).round(0)"

# 正确
"(now() - file.ctime).days.round(0)"
```

**缺少空值保护**：属性不一定在每条笔记上都存在，先用 `if()` 做保护。

```yaml
# 错误：due_date 为空时会出错
"(date(due_date) - today()).days"

# 正确
'if(due_date, (date(due_date) - today()).days, "")'
```

**引用了未定义公式**：`order` 或 `properties` 里的 `formula.X` 必须在 `formulas` 段中有对应定义。

```yaml
# 若 total 没有定义，会静默失败
order:
  - formula.total

# 修复方式
formulas:
  total: "price * quantity"
```

## 参考资料

- [Bases Syntax](https://help.obsidian.md/bases/syntax)
- [函数](https://help.obsidian.md/bases/functions)
- [视图](https://help.obsidian.md/bases/views)
- [公式](https://help.obsidian.md/formulas)
- [完整函数参考](references/FUNCTIONS_REFERENCE.md)
