# 函数参考

## 全局函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `date()` | `date(string): date` | 把字符串解析成日期，格式为 `YYYY-MM-DD HH:mm:ss` |
| `duration()` | `duration(string): duration` | 解析持续时间字符串 |
| `now()` | `now(): date` | 当前日期和时间 |
| `today()` | `today(): date` | 当前日期，时间为 `00:00:00` |
| `if()` | `if(condition, trueResult, falseResult?)` | 条件判断 |
| `min()` | `min(n1, n2, ...): number` | 最小值 |
| `max()` | `max(n1, n2, ...): number` | 最大值 |
| `number()` | `number(any): number` | 转成数字 |
| `link()` | `link(path, display?): Link` | 创建链接 |
| `list()` | `list(element): List` | 若不是列表则包装成列表 |
| `file()` | `file(path): file` | 获取文件对象 |
| `image()` | `image(path): image` | 创建可渲染的图片对象 |
| `icon()` | `icon(name): icon` | 通过名称获取 Lucide 图标 |
| `html()` | `html(string): html` | 作为 HTML 渲染 |
| `escapeHTML()` | `escapeHTML(string): string` | 转义 HTML 字符 |

## 任意类型通用函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `isTruthy()` | `any.isTruthy(): boolean` | 转成布尔值 |
| `isType()` | `any.isType(type): boolean` | 检查类型 |
| `toString()` | `any.toString(): string` | 转成字符串 |

## 日期函数与字段

**字段：** `date.year`、`date.month`、`date.day`、`date.hour`、`date.minute`、`date.second`、`date.millisecond`

| 函数 | 签名 | 说明 |
|------|------|------|
| `date()` | `date.date(): date` | 去掉时间部分 |
| `format()` | `date.format(string): string` | 使用 Moment.js 模式格式化 |
| `time()` | `date.time(): string` | 取时间字符串 |
| `relative()` | `date.relative(): string` | 返回人类可读的相对时间 |
| `isEmpty()` | `date.isEmpty(): boolean` | 对日期始终为 `false` |

## Duration 类型

两个日期相减得到的是 **Duration**，不是数字。它有独立的字段和方法。

**字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `duration.days` | Number | 持续时间总天数 |
| `duration.hours` | Number | 持续时间总小时数 |
| `duration.minutes` | Number | 持续时间总分钟数 |
| `duration.seconds` | Number | 持续时间总秒数 |
| `duration.milliseconds` | Number | 持续时间总毫秒数 |

**重要**：Duration 不能直接调用 `.round()`、`.floor()`、`.ceil()`。必须先取数值字段，再做数值函数。

```yaml
# 正确：计算两个日期之间的天数
"(date(due_date) - today()).days"
"(now() - file.ctime).days"

# 正确：取出数值后再 round
"(date(due_date) - today()).days.round(0)"
"(now() - file.ctime).hours.round(0)"

# 错误：Duration 不能先除法再 round
# "((date(due) - today()) / 86400000).round(0)"
```

## 日期运算

```yaml
# Duration 单位：y/year/years, M/month/months, d/day/days,
#                w/week/weeks, h/hour/hours, m/minute/minutes, s/second/seconds

# 加减持续时间
"date + \"1M\""           # 加 1 个月
"date - \"2h\""           # 减 2 小时
"now() + \"1 day\""       # 明天
"today() + \"7d\""        # 一周后

# 日期相减返回 Duration
"now() - file.ctime"
"(now() - file.ctime).days"
"(now() - file.ctime).hours"

# 复杂 Duration 运算
"now() + (duration('1d') * 2)"
```

## 字符串函数

**字段：** `string.length`

| 函数 | 签名 | 说明 |
|------|------|------|
| `contains()` | `string.contains(value): boolean` | 是否包含子串 |
| `containsAll()` | `string.containsAll(...values): boolean` | 是否同时包含全部子串 |
| `containsAny()` | `string.containsAny(...values): boolean` | 是否包含任意一个子串 |
| `startsWith()` | `string.startsWith(query): boolean` | 是否以前缀开头 |
| `endsWith()` | `string.endsWith(query): boolean` | 是否以后缀结尾 |
| `isEmpty()` | `string.isEmpty(): boolean` | 是否为空或不存在 |
| `lower()` | `string.lower(): string` | 转小写 |
| `title()` | `string.title(): string` | 转 Title Case |
| `trim()` | `string.trim(): string` | 去首尾空白 |
| `replace()` | `string.replace(pattern, replacement): string` | 替换内容 |
| `repeat()` | `string.repeat(count): string` | 重复字符串 |
| `reverse()` | `string.reverse(): string` | 反转字符串 |
| `slice()` | `string.slice(start, end?): string` | 截取子串 |
| `split()` | `string.split(separator, n?): list` | 分割成列表 |

## 数字函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `abs()` | `number.abs(): number` | 绝对值 |
| `ceil()` | `number.ceil(): number` | 向上取整 |
| `floor()` | `number.floor(): number` | 向下取整 |
| `round()` | `number.round(digits?): number` | 按位数四舍五入 |
| `toFixed()` | `number.toFixed(precision): string` | 固定小数位输出 |
| `isEmpty()` | `number.isEmpty(): boolean` | 是否不存在 |

## 列表函数

**字段：** `list.length`

| 函数 | 签名 | 说明 |
|------|------|------|
| `contains()` | `list.contains(value): boolean` | 是否包含元素 |
| `containsAll()` | `list.containsAll(...values): boolean` | 是否包含全部元素 |
| `containsAny()` | `list.containsAny(...values): boolean` | 是否包含任意一个元素 |
| `filter()` | `list.filter(expression): list` | 过滤元素，表达式中可用 `value`、`index` |
| `map()` | `list.map(expression): list` | 映射元素，表达式中可用 `value`、`index` |
| `reduce()` | `list.reduce(expression, initial): any` | 聚合为单值，表达式中可用 `value`、`index`、`acc` |
| `flat()` | `list.flat(): list` | 扁平化嵌套列表 |
| `join()` | `list.join(separator): string` | 连接为字符串 |
| `reverse()` | `list.reverse(): list` | 反转顺序 |
| `slice()` | `list.slice(start, end?): list` | 截取子列表 |
| `sort()` | `list.sort(): list` | 升序排序 |
| `unique()` | `list.unique(): list` | 去重 |
| `isEmpty()` | `list.isEmpty(): boolean` | 是否无元素 |

## 文件函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `asLink()` | `file.asLink(display?): Link` | 转成链接 |
| `hasLink()` | `file.hasLink(otherFile): boolean` | 是否链接到另一个文件 |
| `hasTag()` | `file.hasTag(...tags): boolean` | 是否拥有任一标签 |
| `hasProperty()` | `file.hasProperty(name): boolean` | 是否拥有指定属性 |
| `inFolder()` | `file.inFolder(folder): boolean` | 是否位于指定文件夹或其子目录 |

## 链接函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `asFile()` | `link.asFile(): file` | 获取对应文件对象 |
| `linksTo()` | `link.linksTo(file): boolean` | 是否链接到某文件 |

## 对象函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `isEmpty()` | `object.isEmpty(): boolean` | 是否没有属性 |
| `keys()` | `object.keys(): list` | 返回所有 key |
| `values()` | `object.values(): list` | 返回所有 value |

## 正则表达式函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `matches()` | `regexp.matches(string): boolean` | 检查字符串是否匹配 |
