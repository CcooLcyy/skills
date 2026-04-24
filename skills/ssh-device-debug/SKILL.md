---
name: ssh-device-debug
description: 通过用户提供的 `ip`、`port`、`user`、`passwd` 连接信息验证 SSH 设备可达性，并在当前会话中建立可继续使用的设备上下文。用于当用户希望先连上 Linux 或嵌入式设备，再在当前对话中继续执行命令、查看日志或排查问题时使用。此 skill 只负责收集连接参数和验证连接；连接成功后的具体操作不属于 skill 流程。
---

# SSH 设备连接

## 目标

- 只完成 SSH 连接信息收集与连接验证。
- 连接成功后，在当前会话中记住这台设备并结束 skill 流程。
- 不把 skill 扩展为部署、容器排查、systemd 运维或固定计划模式问卷。

## 输入约定

- 按 `ip`、`port`、`user`、`passwd` 的顺序收集连接信息。
- 如果用户在一条消息里已经按顺序给全，直接解析并继续，不要重复提问。
- 如果缺少字段，只追问缺失字段，且保持上述顺序。
- 如果用户未提供 `port`，默认使用 `22`，并在回复里明确这一默认值。
- 当前版本默认使用密码认证，不引导 `key_path` 或其他认证方式。

## 密码处理

- 允许用户在对话中直接提供密码。
- 后续所有展示、摘要、确认信息和错误信息中都不要回显明文密码，统一显示为 `[已隐藏]`。
- 实际执行时不要把密码拼进命令行参数。
- 只通过环境变量 `SSH_DEVICE_PASSWORD` 或 `--password-stdin` 把密码传给脚本。
- 不把密码写入文件、文档或普通调试输出。

## 执行流程

1. 收集 `ip`、`port`、`user`、`passwd`。
2. 标准化参数：默认 `port=22`，默认 `connect_timeout=8`。
3. 收齐参数后直接验证连接，不要求用户再填写整张表单，也不输出部署或调试计划。
4. 调用仓库内脚本执行连接校验：

```text
python skills/ssh-device-debug/scripts/ssh_device.py check --host "<ip>" --port "<port>" --user "<user>" --auth-mode password --connect-timeout 8 --json
```

- 如果使用密码认证，展示命令时只展示通过环境变量或标准输入传递密码的方式，不展示明文密码。
- 如果本机缺少 `paramiko`，先执行：

```text
python -m pip install -r skills/ssh-device-debug/requirements.txt
```

## 输出要求

- 只输出与当前连接相关的内容。
- 成功时，说明目标设备连接成功，并给出 `ip`、`port`、`user` 和连接状态。
- 失败时，返回简洁失败原因，并指出还缺什么信息或哪一步失败。
- 不输出旧版的固定四区块模板，不输出部署、容器或 systemd 相关建议，除非用户在 skill 结束后另行提出。
