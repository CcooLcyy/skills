#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path, PurePosixPath

try:
    import paramiko
except ImportError:  # pragma: no cover - 通过测试 mock 覆盖
    paramiko = None


DEFAULT_PORT = 22
DEFAULT_CONNECT_TIMEOUT = 8
DEFAULT_ENCODING = "utf-8"
DEFAULT_DOCKER_LOG_LINES = 200
PASSWORD_ENV = "SSH_DEVICE_PASSWORD"


class UsageError(Exception):
    pass


def _require_paramiko():
    if paramiko is None:
        raise RuntimeError(
            "缺少依赖 paramiko，请先运行 `python -m pip install -r "
            "skills/ssh-device-debug/requirements.txt`。"
        )


def _read_password_from_stdin():
    return sys.stdin.read().rstrip("\r\n")


def _build_payload(ok, command, host, port, user, auth_mode, summary, details=None):
    payload = {
        "ok": ok,
        "command": command,
        "host": host,
        "port": port,
        "user": user,
        "auth_mode": auth_mode,
        "summary": summary,
    }
    if details:
        payload.update(details)
    return payload


def _print_json(payload, stream=None):
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=stream or sys.stdout)


def _normalize_remote_path(path):
    return str(PurePosixPath(str(path).replace("\\", "/")))


def _ensure_remote_dir(sftp, remote_dir):
    remote_dir = _normalize_remote_path(remote_dir)
    parts = [part for part in PurePosixPath(remote_dir).parts if part not in ("", ".")]
    current = PurePosixPath("/")
    for part in parts:
        current /= part
        current_str = str(current)
        try:
            sftp.stat(current_str)
        except OSError:
            sftp.mkdir(current_str)


def _run_remote_command(client, command, timeout):
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    if stdin is not None and hasattr(stdin, "close"):
        stdin.close()
    exit_status = stdout.channel.recv_exit_status()
    return {
        "command": command,
        "exit_status": exit_status,
        "stdout": stdout.read().decode(DEFAULT_ENCODING, errors="replace"),
        "stderr": stderr.read().decode(DEFAULT_ENCODING, errors="replace"),
    }


def _upload_path(sftp, src, dest, recursive):
    local_path = Path(src)
    if not local_path.exists():
        raise UsageError(f"本地路径不存在: {local_path}")

    uploaded = []
    remote_dest = PurePosixPath(_normalize_remote_path(dest))
    if local_path.is_dir():
        if not recursive:
            raise UsageError("上传目录时必须显式传入 --recursive。")
        _ensure_remote_dir(sftp, str(remote_dest))
        for file_path in sorted(path for path in local_path.rglob("*") if path.is_file()):
            relative = file_path.relative_to(local_path).as_posix()
            remote_file = remote_dest / PurePosixPath(relative)
            _ensure_remote_dir(sftp, str(remote_file.parent))
            sftp.put(str(file_path), str(remote_file))
            uploaded.append(str(remote_file))
        return uploaded

    _ensure_remote_dir(sftp, str(remote_dest.parent))
    sftp.put(str(local_path), str(remote_dest))
    uploaded.append(str(remote_dest))
    return uploaded


def _build_container_command(args):
    action = args.action
    target = args.target
    compose_prefix = "docker compose"
    if args.compose_file:
        compose_prefix += f" -f {shlex.quote(args.compose_file)}"

    if action == "ps":
        command = f"{compose_prefix} ps" if args.compose_file else "docker ps"
        if target:
            if args.compose_file:
                command += f" {shlex.quote(target)}"
            else:
                command += f" --filter name={shlex.quote(target)}"
    elif action == "logs":
        if not target:
            raise UsageError("container logs 操作需要 --target。")
        if args.compose_file:
            command = (
                f"{compose_prefix} logs --tail {DEFAULT_DOCKER_LOG_LINES} "
                f"{shlex.quote(target)}"
            )
        else:
            command = f"docker logs --tail {DEFAULT_DOCKER_LOG_LINES} {shlex.quote(target)}"
    elif action == "exec":
        if not target:
            raise UsageError("container exec 操作需要 --target。")
        if not args.exec_cmd:
            raise UsageError("container exec 操作需要 --exec-cmd。")
        if args.compose_file:
            command = (
                f"{compose_prefix} exec {shlex.quote(target)} "
                f"sh -lc {shlex.quote(args.exec_cmd)}"
            )
        else:
            command = f"docker exec {shlex.quote(target)} sh -lc {shlex.quote(args.exec_cmd)}"
    elif action == "restart":
        if not target:
            raise UsageError("container restart 操作需要 --target。")
        if args.compose_file:
            command = f"{compose_prefix} restart {shlex.quote(target)}"
        else:
            command = f"docker restart {shlex.quote(target)}"
    elif action == "up":
        command = f"{compose_prefix} up -d"
    else:  # pragma: no cover - argparse 已限制
        raise UsageError(f"不支持的 container action: {action}")

    if args.workdir:
        return f"cd {shlex.quote(args.workdir)} && {command}"
    return command


def _create_client(args):
    _require_paramiko()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs = {
        "hostname": args.host,
        "port": args.port,
        "username": args.user,
        "timeout": args.connect_timeout,
        "banner_timeout": args.connect_timeout,
        "auth_timeout": args.connect_timeout,
        "look_for_keys": False,
        "allow_agent": False,
    }

    if args.auth_mode == "password":
        password = os.environ.get(PASSWORD_ENV)
        if not password and getattr(args, "password_stdin", False):
            password = _read_password_from_stdin()
        if not password:
            raise UsageError(
                f"密码认证需要设置环境变量 {PASSWORD_ENV} 或传入 --password-stdin。"
            )
        connect_kwargs["password"] = password
    else:
        connect_kwargs["key_filename"] = args.key_path

    client.connect(**connect_kwargs)
    return client


def handle_check(args):
    client = _create_client(args)
    try:
        return _build_payload(
            True,
            "check",
            args.host,
            args.port,
            args.user,
            args.auth_mode,
            "SSH 连接成功，可在当前会话中继续后续操作。",
            {"connected": True},
        )
    finally:
        client.close()


def handle_run(args):
    client = _create_client(args)
    try:
        result = _run_remote_command(client, args.remote_command, args.connect_timeout)
        return _build_payload(
            True,
            "run",
            args.host,
            args.port,
            args.user,
            args.auth_mode,
            "远端命令执行完成。",
            {"result": result},
        )
    finally:
        client.close()


def handle_deploy(args):
    client = _create_client(args)
    sftp = None
    try:
        sftp = client.open_sftp()
        uploaded = _upload_path(sftp, args.src, args.dest, args.recursive)
        post_result = None
        if args.post_cmd:
            post_result = _run_remote_command(client, args.post_cmd, args.connect_timeout)
        return _build_payload(
            True,
            "deploy",
            args.host,
            args.port,
            args.user,
            args.auth_mode,
            "文件上传完成。",
            {
                "src": str(Path(args.src)),
                "dest": _normalize_remote_path(args.dest),
                "recursive": bool(args.recursive),
                "uploaded": uploaded,
                "post_cmd": args.post_cmd or "",
                "post_result": post_result,
            },
        )
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        client.close()


def handle_container(args):
    command = _build_container_command(args)
    client = _create_client(args)
    try:
        result = _run_remote_command(client, command, args.connect_timeout)
        return _build_payload(
            True,
            "container",
            args.host,
            args.port,
            args.user,
            args.auth_mode,
            f"Docker 操作完成：{args.action}",
            {
                "action": args.action,
                "target": args.target or "",
                "compose_file": args.compose_file or "",
                "workdir": args.workdir or "",
                "exec_cmd": args.exec_cmd or "",
                "result": result,
            },
        )
    finally:
        client.close()


def build_parser():
    parser = argparse.ArgumentParser(description="SSH 设备连接 CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    def add_common_arguments(subparser):
        subparser.add_argument("--host", required=True)
        subparser.add_argument("--port", type=int, default=DEFAULT_PORT)
        subparser.add_argument("--user", required=True)
        subparser.add_argument(
            "--auth-mode",
            required=True,
            choices=("password", "key"),
        )
        subparser.add_argument("--key-path", default="")
        subparser.add_argument("--connect-timeout", type=int, default=DEFAULT_CONNECT_TIMEOUT)
        subparser.add_argument("--json", action="store_true")
        subparser.add_argument("--password", default="", help=argparse.SUPPRESS)
        subparser.add_argument("--password-stdin", action="store_true")

    check_parser = subparsers.add_parser("check", help="验证 SSH 连接")
    add_common_arguments(check_parser)
    check_parser.set_defaults(handler=handle_check)

    run_parser = subparsers.add_parser("run", help="执行远端命令")
    add_common_arguments(run_parser)
    run_parser.add_argument("--remote-command", default="")
    run_parser.add_argument("remote_command_parts", nargs=argparse.REMAINDER)
    run_parser.set_defaults(handler=handle_run)

    deploy_parser = subparsers.add_parser("deploy", help="上传文件或目录")
    add_common_arguments(deploy_parser)
    deploy_parser.add_argument("--src", required=True)
    deploy_parser.add_argument("--dest", required=True)
    deploy_parser.add_argument("--recursive", action="store_true")
    deploy_parser.add_argument("--post-cmd", default="")
    deploy_parser.set_defaults(handler=handle_deploy)

    container_parser = subparsers.add_parser("container", help="执行 Docker 相关操作")
    add_common_arguments(container_parser)
    container_parser.add_argument(
        "--action",
        required=True,
        choices=("ps", "logs", "exec", "restart", "up"),
    )
    container_parser.add_argument("--target", default="")
    container_parser.add_argument("--compose-file", default="")
    container_parser.add_argument("--workdir", default="")
    container_parser.add_argument("--exec-cmd", default="")
    container_parser.set_defaults(handler=handle_container)
    return parser


def validate_args(args):
    if getattr(args, "password", ""):
        raise UsageError(
            f"不要通过 --password 传递密码，请改用环境变量 {PASSWORD_ENV} 或 --password-stdin。"
        )

    if args.auth_mode == "key" and not args.key_path:
        raise UsageError("密钥认证需要提供 --key-path。")

    if args.auth_mode == "password" and args.key_path:
        raise UsageError("密码认证时不要传入 --key-path。")

    if getattr(args, "port", DEFAULT_PORT) <= 0:
        raise UsageError("--port 必须为正整数。")

    if getattr(args, "connect_timeout", DEFAULT_CONNECT_TIMEOUT) <= 0:
        raise UsageError("--connect-timeout 必须为正整数。")

    if args.subcommand == "run":
        if not args.remote_command:
            parts = list(getattr(args, "remote_command_parts", []))
            if parts and parts[0] == "--":
                parts = parts[1:]
            if not parts:
                raise UsageError("run 操作需要提供远端命令。")
            args.remote_command = shlex.join(parts)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        validate_args(args)
        payload = args.handler(args)
    except Exception as exc:
        payload = _build_payload(
            False,
            getattr(args, "subcommand", ""),
            getattr(args, "host", ""),
            getattr(args, "port", DEFAULT_PORT),
            getattr(args, "user", ""),
            getattr(args, "auth_mode", ""),
            str(exc),
            {"error_type": exc.__class__.__name__},
        )
        _print_json(payload, stream=sys.stderr)
        return 1

    _print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
