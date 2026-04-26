---
name: draw-image
description: 使用 GPT Image 2.0 / gpt-image-2 通过用户提供的非官方或 OpenAI 兼容 API 进行画图、绘图、图片生成和图片编辑。用户要求生成照片、插画、海报、封面、贴纸、头像、产品图、UI mockup、游戏素材、纹理、透明背景图片，或要求基于参考图改图、换背景、去除/替换对象、风格迁移、生成多版本视觉资产时使用。必须注意收集并使用用户提供的 base_url 和 API key，不要默认使用 OpenAI 官方端点。若用户要的是 Mermaid、Graphviz、SVG、JSON Canvas、流程图、架构图等可编辑结构图，优先使用结构化图表方式或 json-canvas。
---

# GPT Image 画图

用 GPT Image 2.0（模型名通常写作 `gpt-image-2`）通过用户提供的 API 服务生成或编辑位图资产。这个 skill 负责把用户的自然语言需求转成可执行的图像生成规格，并确保输出能落到当前项目或用户指定位置。

## API 约束

- 不要默认使用 OpenAI 官方 API 地址；默认假设用户使用的是非官方或 OpenAI 兼容转发服务。
- 执行前必须确认 `base_url`、API key 的来源、模型名、可用端点和接口兼容性。若用户已经在当前会话给出这些信息，直接使用；否则先询问。
- 用户只需要提供 `base_url` 和 API key；不要要求用户判断应该用 `/v1/images/generations`、`/v1/images/edits` 还是 `/v1/chat/completions`。
- API key 优先从环境变量读取，例如 `OPENAI_API_KEY`、`GPT_IMAGE_API_KEY` 或用户指定名称；不要把密钥写入仓库、日志、文档或最终回复。
- `base_url` 可以写入本地配置、临时命令参数或环境变量，但不要和密钥一起提交到仓库。
- 如果服务是 OpenAI 兼容接口，使用 OpenAI SDK 时必须显式设置 `base_url`，不要只设置 `api_key`。
- 不要假设图片模型固定走某一个端点。提供商可能同时或分别暴露 `POST /v1/images/generations`、`POST /v1/images/edits`、`POST /v1/chat/completions` 等端点；每次按当前提供商页面或文档选择。
- 如果提供商的图片接口路径、请求字段或返回字段与 OpenAI 官方不完全一致，先检查已有脚本、用户文档或最小 curl 示例，再适配调用方式。

## 工作流

1. 判断任务类型：新图生成、基于参考图生成、编辑现有图片、多版本批量生成或透明背景资产。
2. 明确交付物：用途、尺寸/比例、风格、主体、构图、文字内容、禁用项、保存路径。
3. 选择执行路径：
   - 用户明确要求 API、CLI、模型参数、批量脚本或固定使用 `gpt-image-2` 时，使用项目或系统已有的 GPT Image CLI/API 流程，并显式传入 `base_url`。
   - 当前 Codex/VS Code 环境提供内置图像生成工具时，只在它能使用用户指定 API 服务时使用；否则不要走内置官方路径。
   - 如果当前环境没有图像工具或 API key，不要假装已生成图片；先说明缺失条件。
4. 若用户没有提供端点类型，自动探测可用端点，再选择调用方式。
5. 组织 prompt。保留用户明确要求，补足会提升出图质量的少量细节；不要擅自加入额外角色、品牌、标语或复杂背景。
6. 生成后检查结果：主体是否正确、构图是否符合用途、文字是否准确、参考图约束是否保留、是否有水印或多余元素。
7. 保存结果。项目资产必须移动或复制到工作区内；预览草图可以保留在生成工具默认输出位置。
8. 最终回复说明保存路径、使用的模型/路径、最终 prompt，以及任何未满足的约束。

## Prompt 模板

按需使用这些字段，不要为了完整而堆长 prompt：

```text
用途：<照片 / 插画 / 海报 / 产品图 / UI mockup / 游戏素材 / 透明贴纸 / 纹理 / 头像>
核心需求：<用户核心需求>
资产去向：<使用场景和保存位置>
主体：<主体、数量、关键特征>
场景/背景：<环境或背景>
风格/媒介：<摄影、3D、矢量感插画、水彩、像素风等>
构图：<镜头、比例、主体位置、留白>
光线/氛围：<光线和氛围>
色彩：<主色和禁用色>
文字："<必须逐字出现的文字>"
参考图：<每张图的角色：编辑目标 / 风格参考 / 构图参考 / 角色参考>
约束：<必须保留、必须避免、不能改变的部分>
避免：<水印、乱码文字、多余手指、品牌 logo 等>
```

## API 调用要点

使用 OpenAI 兼容 Python SDK 时，调用形态通常是：

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["GPT_IMAGE_API_KEY"],
    base_url=os.environ["GPT_IMAGE_BASE_URL"],
)
```

调用图片接口前先确认当前 SDK 和服务端支持的方法名、参数名和返回结构。常见差异包括 `images.generate` / `images.edit` / `responses.create` / `chat.completions.create`、图片数据字段名、尺寸枚举、质量参数、透明背景参数和编辑接口的 multipart 约定。

按提供商端点选择调用方式：

| 提供商显示端点 | 适用任务 | 常见 SDK 方式 |
| --- | --- | --- |
| `POST /v1/images/generations` | 文生图、参考较少的新图生成 | `client.images.generate(...)` |
| `POST /v1/images/edits` | 基于输入图片编辑、局部修改、换背景 | `client.images.edit(...)` |
| `POST /v1/chat/completions` | 聊天补全兼容封装的图片模型 | `client.chat.completions.create(...)` |

如果页面显示 `dall-e-3 格式`，优先尝试 `/v1/images/generations` 或 `/v1/images/edits` 的图片接口形态。若页面只显示聊天补全端点，再走 `chat.completions`。

文生图端点示例：

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ["GPT_IMAGE_API_KEY"],
    base_url=os.environ["GPT_IMAGE_BASE_URL"],
)

response = client.images.generate(
    model="gpt-image-2",
    prompt="一张 1:1 构图的简单图片：白色背景上的红苹果。",
    size="1024x1024",
)
```

图片编辑端点示例：

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ["GPT_IMAGE_API_KEY"],
    base_url=os.environ["GPT_IMAGE_BASE_URL"],
)

with open("input.png", "rb") as image_file:
    response = client.images.edit(
        model="gpt-image-2",
        image=image_file,
        prompt="把背景替换为干净的白色摄影棚背景，保持主体不变。",
    )
```

如果提供商页面显示端点为 `POST /v1/chat/completions`，先用最小请求探测：

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ["GPT_IMAGE_API_KEY"],
    base_url=os.environ["GPT_IMAGE_BASE_URL"],
)

response = client.chat.completions.create(
    model="gpt-image-2",
    messages=[
        {"role": "user", "content": "生成一张 1:1 构图的简单图片：白色背景上的红苹果。"}
    ],
)
```

然后检查 `response` 中图片实际出现的位置，再写下载或 base64 解码逻辑。不要在没有确认响应格式时硬编码解析字段。

命令行或脚本应优先使用环境变量：

```bash
export GPT_IMAGE_BASE_URL="https://example.com/v1"
export GPT_IMAGE_API_KEY="..."
```

如果必须临时传参，命令输出和最终回复中不要回显 API key。

## 端点自动探测

当用户只提供 `base_url` 和 API key 时，先自动探测，不要追问端点类型。

优先使用本 skill 的脚本：

```bash
GPT_IMAGE_BASE_URL="https://example.com/v1" \
GPT_IMAGE_API_KEY="..." \
python "${CODEX_HOME:-$HOME/.codex}/skills/draw-image/scripts/probe_provider.py" --model gpt-image-2
```

探测规则：

1. 标准化 `base_url`：若用户给的是服务根路径，尝试追加 `/v1`；若已经以 `/v1` 结尾，直接使用。
2. 先做低成本验证探测，不直接生成图片：
   - `POST /v1/images/generations`，只传 `model`，若返回缺少 `prompt` 一类的 400/422 错误，视为该端点可用。
   - `POST /v1/images/edits`，只传 `model`，若返回缺少 `image` / `prompt` 或 multipart 一类的 400/415/422 错误，视为该端点可用。
   - `POST /v1/chat/completions`，只传 `model`，若返回缺少 `messages` 一类的 400/422 错误，视为该端点可用。
3. 若多个端点都可用，文生图优先 `/images/generations`，图片编辑优先 `/images/edits`，只有图片端点不可用时才尝试 `/chat/completions`。
4. 若所有探测都返回 401/403，说明 key、分组权限或模型授权有问题；不要继续猜测端点。
5. 若只有 `/chat/completions` 可用，第一次真实调用后必须检查响应里的图片位置，可能是 URL、base64、Markdown 图片链接或自定义字段。
6. 探测结果可以在当前会话中复用；不要把 API key 写入任何探测报告或配置文件。

## 新图生成

- 用户只给一句很泛的需求时，补充用途、构图和风格，但保持目标简洁。
- 海报、封面、广告图要先确认或显式写出文字；图像模型不适合凭空猜长文案。
- 产品图要写清材质、视角、背景、阴影、是否需要包装或标签。
- UI mockup 要说明这是视觉 mockup，不是可运行界面；需要代码实现时改走前端实现流程。
- 游戏素材要说明视角、尺寸感、背景是否透明、是否要 sprite sheet。

## 图片编辑

编辑现有图片时，把不应改变的内容写成明确约束：

```text
只编辑：<要改变的区域或对象>
保留：<人物身份、姿势、构图、背景、光照、文字、品牌元素等>
不要改变：<必须保持不变的细节>
```

常见编辑类型：

- 去除或替换对象：说明对象位置、替换物、背景补全要求。
- 换背景：保留主体比例、边缘、光照方向和透视。
- 风格迁移：说明参考图只用于风格，不改变主体身份或构图。
- 文字替换：给出逐字文本，并要求保持原有排版、字号、材质和透视。
- 合成：标明每张输入图的角色，要求统一光照、透视、尺度和接触阴影。

## 透明背景

- 如果工具原生支持透明背景，用 PNG 或 WebP 透明输出。
- 如果当前 `gpt-image-2` 路径不支持原生透明背景，先生成纯色可抠背景，再做本地抠图；复杂边缘如头发、玻璃、烟雾、半透明材质需要提前说明风险。
- 透明资产 prompt 要求背景是完全纯色、无阴影、无渐变、无地面、主体边缘清晰且留足边距。

示例：

```text
在完全平坦的纯色 #00ff00 抠图背景上生成目标主体，方便后续移除背景。
背景必须是单一均匀颜色，不要阴影、渐变、纹理、反射、地面或光照变化。
主体要和背景完全分离，边缘清晰，并保留足够边距。
主体内部不要使用 #00ff00。
不要水印；除非明确要求，否则不要文字。
```

## 批量和多版本

- 多个不同资产要分别写 prompt；不要用一个宽泛 prompt 一次性生成所有内容。
- 同一资产的多版本要标清差异，例如颜色、镜头、风格、表情或布局。
- 批量输出时使用稳定文件名：`asset-name-v1.png`、`asset-name-v2.png` 或按角色/用途命名。
- 生成后只保留用户需要的最终版本；草稿和失败版本除非用户要求，否则不要接入项目。

## 验证

每次交付前检查：

- 文件存在，格式和扩展名一致。
- 图像能打开，尺寸/比例适合目标用途。
- 项目引用的资产已经在工作区内，不只留在临时目录或系统默认生成目录。
- 图中文字与用户给定文本一致；若模型文字有明显错误，重新生成或说明限制。
- 编辑任务没有破坏用户要求保留的人物、构图、品牌元素或背景。

## 当前环境提示

skill 只能指导 Codex 如何调用已有能力，不能单独给 VS Code 扩展增加新的图像生成工具。若当前扩展没有可配置 `base_url` 的图像生成工具，则需要可用的 GPT Image API/CLI、`base_url` 和 API key 才能真正出图。
