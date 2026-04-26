---
name: git-commit
description: 用于在本地仓库完成 git 提交流程：分析未暂存改动、询问排除文件、暂存修改、按功能点拆分提交、根据仓库现有规范生成提交信息、执行提交并在提交后同步远端。用户提到 git 提交、提交信息、提交规范、提交后同步或提交失败需要重试等场景时使用。
---

# Git 提交

## 工作流

- 固定顺序：先划分改动点，再暂存关联改动，再生成提交信息，提交后同步远端。
- 强制要求：调用本技能时必须完成“暂存修改”和“生成提交信息”两步，不要跳过。
- 优先使用 `scripts/git_commit_helper.py` 固化机械步骤；拆分提交、排除文件、提交信息语义仍由 agent 判断。

## 脚本化辅助

- `python3 <skill_dir>/scripts/git_commit_helper.py --repo <repo> inspect`：收集状态、暂存/未暂存文件、diff stat、疑似排除文件、提交规范候选、最近提交与 upstream 状态。
- `python3 <skill_dir>/scripts/git_commit_helper.py --repo <repo> inspect --include-diff`：需要完整核对时输出截断后的 `git diff` 与 `git diff --cached`。
- `python3 <skill_dir>/scripts/git_commit_helper.py --repo <repo> commit --message-file <file>`：用 UTF-8 无 BOM 临时文件执行 `git commit -F`，避免中文或非 ASCII 提交信息在不同 shell 下乱码。
- `python3 <skill_dir>/scripts/git_commit_helper.py --repo <repo> sync`：提交完成后执行最终同步，包含 `fetch --prune`、ahead/behind 检查、必要的 `pull --rebase` 与 `push`。
- 脚本失败时读取错误信息并回到人工判断；不要用脚本跳过用户确认、拆分提交或风险说明。

1. 读取状态与未暂存改动
   - 优先执行 `git_commit_helper.py inspect`；必要时补充 `git_commit_helper.py inspect --include-diff` 或直接执行 `git diff`。
   - 若存在已暂存改动，列出并确认是否保留或需要拆分。
   - 先按修改点/功能点归类，作为后续暂存分组依据。

2. 询问排除文件
   - 列出未暂存文件清单。
   - 主动按类型提示可能不提交的文件，例如：JSON 配置、密钥、生成物、日志、大文件。
   - 获取用户确认的排除列表；如需长期忽略，更新 `.gitignore`。

3. 按功能点拆分提交
   - 按前面划分的修改点分组暂存，优先使用 `git add -p` 或逐文件暂存，确保完成暂存。
   - 每个批次暂存后展示 `git diff --cached` 并确认内容完整。
   - 暂存完成后再生成该批次提交信息，避免先写提交信息再补改动。
   - 若存在多批次，逐批次生成提交信息草稿但先汇总，等所有批次准备完后一次性输出。

4. 发现仓库提交规范
   - 优先参考 `git_commit_helper.py inspect` 输出的规范候选。
   - 必要时继续查找规范与模板：`CONTRIBUTING.md`、`README.md`、`docs/`、`.gitmessage*`、`.commitlintrc*`、`commitlint.config.*`、`package.json` 中的 commitlint/commitizen 配置、`git config commit.template`。
   - 若存在模板或规范，严格遵循。
   - 若找不到规范，参考仓库最近提交信息的格式/风格；若无可参考内容，直接生成简洁一致的提交信息。

5. 生成提交信息
   - 根据规范或既有提交信息风格生成标题/正文/脚注，按仓库语言要求编写，必须给出提交信息候选。
   - 提交信息必须使用真实换行，禁止输出字面量 `\n` 作为换行符；标题与正文之间保留一个空行，正文每条要点独占一行。
   - 提交信息文本必须以 `UTF-8` 编码保存；若通过消息文件提交，优先使用 `UTF-8` 无 BOM，避免在不同 shell 或平台下出现乱码。
   - 提交信息需要详细：标题概括改动主题，正文列出本批次改动点/影响范围/关键原因，确保读者无需查看 diff 也能理解变化。
   - 需要工单号或 issue id 时，主动询问并补齐。
   - 若为多批次提交，一次性输出所有批次的提交信息候选，统一确认与调整。

6. 提交
   - 优先将提交信息写入 `UTF-8` 无 BOM 消息文件，并使用 `git_commit_helper.py commit --message-file <file>` 提交该批次。
   - 若不用脚本，在 Windows 下提交中文或其他非 ASCII 提交信息时，不要依赖 shell 管道或 `git commit -m` 直接传参；优先写入 `UTF-8` 无 BOM 临时消息文件，再用 `git commit -F <file>` 提交。
   - 若有多批次，重复第 3-6 步。

7. 最终同步
   - 所有提交完成后优先执行 `git_commit_helper.py sync`。
   - 若不用脚本，先执行 `git status -sb` 和 `git log -1 --oneline`，确认本地提交结果与工作区状态。
   - 再执行 `git fetch --prune`，检查当前分支与上游分支的 ahead/behind 状态。
   - 若当前分支没有 upstream，优先使用 `git push -u origin HEAD` 建立跟踪并推送；若没有 `origin` 或远端目标不明确，先询问用户远端与分支名。
   - 若本地仅领先上游，执行 `git push`。
   - 若本地落后或与上游分叉，优先使用 `git pull --rebase` 同步后再 `git push`；若工作区仍有未提交或被排除的改动，先说明风险并询问是否临时储藏这些改动后继续。
   - 若 rebase、push 或 hook 失败，读取错误信息，修正冲突/提交信息/同步策略后重试；无法安全自动处理时停止并报告当前状态。
   - 若用户明确要求只保留本地提交或不要同步远端，跳过本步骤并说明未同步状态。

## 质量与安全

- 在执行可能耗时的测试或格式化前，先询问用户是否需要运行。
- 若提交失败（如 hook/commitlint），读取错误信息，修正提交信息或拆分策略后重试。
