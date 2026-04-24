# SSH 设备调试配方

## 基础连通性排查

- 先用 `check` 子命令验证 SSH 连接。
- 固定关注：
  - `hostname`
  - `uname -a`
  - `id`
  - `docker --version` 是否可用

## 远端命令执行

- 一次只执行一条 `remote_command`。
- 需要复合命令时，用 `sh -lc '...'` 包住整段命令，保持输入稳定。
- 对高风险命令保持保守，优先诊断命令、状态查询和日志读取。

## 文件上传与部署

- 单文件替换：
  - 上传到目标路径
  - 需要时通过 `post_cmd` 执行 `systemctl restart <service>`
- 目录上传：
  - 使用 `deploy --recursive`
  - 目标目录按相对路径逐文件创建
- 常见 `post_cmd`：
  - `systemctl daemon-reload`
  - `systemctl restart <service>`
  - `systemctl status <service> --no-pager`
  - `journalctl -u <service> -n 100 --no-pager`

## Docker 容器操作

- `ps`
  - 查看容器列表
- `logs`
  - `docker logs --tail 200 <container>`
- `exec`
  - `docker exec <container> sh -lc '<command>'`
- `restart`
  - `docker restart <container>`
- `up`
  - 在远端工作目录执行 `docker compose up -d`
  - 如果指定 compose 文件，使用 `docker compose -f <file> up -d`

## 固定输出要求

- 优先保留原始 stdout、stderr 和退出码。
- 不要在参考命令中拼接明文密码。
