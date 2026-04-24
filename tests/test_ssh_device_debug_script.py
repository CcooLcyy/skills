from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "ssh-device-debug" / "scripts" / "ssh_device.py"

FAKE_PARAMIKO_INIT = textwrap.dedent(
    """
    import json
    import os
    from pathlib import Path


    class SSHException(Exception):
        pass


    class AuthenticationException(SSHException):
        pass


    def _normalize(value):
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return {key: _normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_normalize(item) for item in value]
        return value.__class__.__name__


    def _record(event, **fields):
        log_path = os.environ.get("FAKE_PARAMIKO_LOG")
        if not log_path:
            return
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"event": event}
        payload.update({key: _normalize(value) for key, value in fields.items()})
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\\n")


    class AutoAddPolicy:
        pass


    class RejectPolicy:
        pass


    class WarningPolicy:
        pass


    class _KeyBase:
        def __init__(self, filename):
            self.filename = filename

        @classmethod
        def from_private_key_file(cls, filename, password=None):
            _record(
                "pkey.load",
                key_type=cls.__name__,
                filename=filename,
                password=password,
            )
            return cls(filename)


    class RSAKey(_KeyBase):
        pass


    class Ed25519Key(_KeyBase):
        pass


    class ECDSAKey(_KeyBase):
        pass


    class DSSKey(_KeyBase):
        pass


    class _Channel:
        def recv_exit_status(self):
            return int(os.environ.get("FAKE_PARAMIKO_EXIT_STATUS", "0"))

        def exit_status_ready(self):
            return True

        def shutdown_write(self):
            _record("channel.shutdown_write")


    class _Stream:
        def __init__(self, text):
            self._data = text.encode("utf-8")
            self.channel = _Channel()

        def read(self):
            return self._data

        def readline(self):
            return self._data

        def readlines(self):
            return [self._data] if self._data else []

        def write(self, data):
            _record("stream.write", data=data)
            return len(str(data))

        def flush(self):
            _record("stream.flush")

        def __iter__(self):
            return iter(self.readlines())


    class SFTPClient:
        def __init__(self):
            _record("sftp.init")

        @classmethod
        def from_transport(cls, transport):
            _record("sftp.from_transport", transport=transport)
            return cls()

        def put(self, localpath, remotepath):
            _record("sftp.put", localpath=localpath, remotepath=remotepath)

        def putfo(self, fileobj, remotepath):
            _record("sftp.putfo", remotepath=remotepath)

        def mkdir(self, path):
            _record("sftp.mkdir", path=path)

        def stat(self, path):
            _record("sftp.stat", path=path)
            raise FileNotFoundError(path)

        def close(self):
            _record("sftp.close")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False


    class Transport:
        def __init__(self, sock):
            self.sock = sock
            _record("transport.init", sock=sock)

        def connect(self, username=None, password=None, pkey=None):
            _record(
                "transport.connect",
                username=username,
                password=password,
                pkey=pkey,
            )

        def close(self):
            _record("transport.close")


    class SSHClient:
        def __init__(self):
            _record("ssh_client.init")

        def load_system_host_keys(self):
            _record("ssh_client.load_system_host_keys")

        def set_missing_host_key_policy(self, policy):
            _record(
                "ssh_client.set_missing_host_key_policy",
                policy=policy.__class__.__name__,
            )

        def connect(
            self,
            hostname=None,
            port=None,
            username=None,
            password=None,
            pkey=None,
            timeout=None,
            **kwargs,
        ):
            _record(
                "ssh_client.connect",
                hostname=hostname,
                port=port,
                username=username,
                password=password,
                pkey=pkey,
                timeout=timeout,
                extra_kwargs=kwargs,
            )

        def exec_command(self, command, timeout=None, get_pty=False, environment=None):
            _record(
                "ssh_client.exec_command",
                command=command,
                timeout=timeout,
                get_pty=get_pty,
                environment=environment,
            )
            return (
                _Stream(""),
                _Stream(os.environ.get("FAKE_PARAMIKO_STDOUT", "")),
                _Stream(os.environ.get("FAKE_PARAMIKO_STDERR", "")),
            )

        def open_sftp(self):
            _record("ssh_client.open_sftp")
            return SFTPClient()

        def get_transport(self):
            _record("ssh_client.get_transport")
            return Transport(("fake-host", 22))

        def close(self):
            _record("ssh_client.close")
    """
)

FAKE_PARAMIKO_CLIENT = "from . import AutoAddPolicy, RejectPolicy, SSHClient, WarningPolicy\n"
FAKE_PARAMIKO_SFTP = "from . import SFTPClient\n"
FAKE_PARAMIKO_TRANSPORT = "from . import Transport\n"
FAKE_PARAMIKO_EXCEPTIONS = "from . import AuthenticationException, SSHException\n"

BLOCK_PARAMIKO_SITE = textwrap.dedent(
    """
    import importlib.abc
    import importlib.machinery
    import sys


    class _BlockedLoader(importlib.abc.Loader):
        def create_module(self, spec):
            raise ModuleNotFoundError("paramiko blocked by test")

        def exec_module(self, module):
            raise ModuleNotFoundError("paramiko blocked by test")


    class _BlockParamiko(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "paramiko" or fullname.startswith("paramiko."):
                return importlib.machinery.ModuleSpec(fullname, _BlockedLoader())
            return None


    sys.meta_path.insert(0, _BlockParamiko())
    """
)


class SshDeviceDebugScriptTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.fake_log = self.root / "fake-paramiko-log.jsonl"
        self.base_env = os.environ.copy()
        self.base_env.setdefault("PYTHONUTF8", "1")

    def _run_cli(
        self,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.assertTrue(SCRIPT_PATH.exists(), f"缺少脚本: {SCRIPT_PATH}")
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args],
            cwd=str(REPO_ROOT),
            env=env or self.base_env,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def _join_pythonpath(self, prefix: Path, current: str | None) -> str:
        if current:
            return str(prefix) + os.pathsep + current
        return str(prefix)

    def _write_temp_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _make_fake_paramiko_env(self) -> dict[str, str]:
        package_root = self.root / "fake-paramiko"
        self._write_temp_file(package_root / "paramiko" / "__init__.py", FAKE_PARAMIKO_INIT)
        self._write_temp_file(package_root / "paramiko" / "client.py", FAKE_PARAMIKO_CLIENT)
        self._write_temp_file(package_root / "paramiko" / "sftp_client.py", FAKE_PARAMIKO_SFTP)
        self._write_temp_file(package_root / "paramiko" / "transport.py", FAKE_PARAMIKO_TRANSPORT)
        self._write_temp_file(
            package_root / "paramiko" / "ssh_exception.py",
            FAKE_PARAMIKO_EXCEPTIONS,
        )

        env = self.base_env.copy()
        env["PYTHONPATH"] = self._join_pythonpath(package_root, env.get("PYTHONPATH"))
        env["FAKE_PARAMIKO_LOG"] = str(self.fake_log)
        env["FAKE_PARAMIKO_EXIT_STATUS"] = "0"
        env["FAKE_PARAMIKO_STDOUT"] = "ok\n"
        env["FAKE_PARAMIKO_STDERR"] = ""
        return env

    def _make_blocked_paramiko_env(self) -> dict[str, str]:
        blocked_root = self.root / "blocked-paramiko"
        self._write_temp_file(blocked_root / "sitecustomize.py", BLOCK_PARAMIKO_SITE)
        env = self.base_env.copy()
        env["PYTHONPATH"] = self._join_pythonpath(blocked_root, env.get("PYTHONPATH"))
        return env

    def _common_args(self, *, auth_mode: str = "password") -> list[str]:
        args = [
            "--host",
            "device.example.test",
            "--port",
            "2222",
            "--user",
            "debugger",
            "--auth-mode",
            auth_mode,
            "--connect-timeout",
            "7",
        ]
        if auth_mode == "key":
            key_path = self.root / "id_ed25519"
            key_path.write_text("not-a-real-private-key\n", encoding="utf-8")
            args.extend(["--key-path", str(key_path)])
        return args

    def _read_fake_events(self) -> list[dict[str, object]]:
        if not self.fake_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.fake_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _find_event(
        self,
        events: list[dict[str, object]],
        name: str,
    ) -> dict[str, object]:
        for event in events:
            if event.get("event") == name:
                return event
        self.fail(f"未找到事件: {name}\n已有事件: {events}")

    def _assert_ok_json(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        if result.returncode != 0:
            self.fail(f"命令失败\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"stdout 不是合法 JSON: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        self.assertIsInstance(payload, dict)
        return payload

    def _assert_common_json(
        self,
        payload: dict[str, object],
        *,
        command: str,
        auth_mode: str,
    ) -> None:
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload.get("command"), command)
        self.assertEqual(payload.get("host"), "device.example.test")
        self.assertEqual(payload.get("port"), 2222)
        self.assertEqual(payload.get("user"), "debugger")
        self.assertEqual(payload.get("auth_mode"), auth_mode)

    def _assert_secret_not_echoed(self, secret: str, result: subprocess.CompletedProcess[str]) -> None:
        combined = "\n".join([result.stdout, result.stderr])
        self.assertNotIn(secret, combined)

    def test_help_works_without_paramiko_installed(self) -> None:
        env = self._make_blocked_paramiko_env()

        result = self._run_cli(["--help"], env=env)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("check", result.stdout)
        self.assertIn("run", result.stdout)
        self.assertIn("deploy", result.stdout)
        self.assertIn("container", result.stdout)

    def test_rejects_password_argument_without_echoing_secret(self) -> None:
        secret = "cli-secret-should-not-leak"

        result = self._run_cli(
            ["check", *self._common_args(), "--password", secret],
            env=self.base_env,
        )

        self.assertNotEqual(result.returncode, 0)
        self._assert_secret_not_echoed(secret, result)

    def test_check_uses_password_from_environment_and_emits_stable_json(self) -> None:
        secret = "env-secret-value"
        env = self._make_fake_paramiko_env()
        env["SSH_DEVICE_PASSWORD"] = secret

        result = self._run_cli(["check", *self._common_args(), "--json"], env=env)

        payload = self._assert_ok_json(result)
        self._assert_common_json(payload, command="check", auth_mode="password")
        self.assertNotIn("password", payload)
        self._assert_secret_not_echoed(secret, result)
        self.assertNotIn(secret, json.dumps(payload, ensure_ascii=False))

        connect_event = self._find_event(self._read_fake_events(), "ssh_client.connect")
        self.assertEqual(connect_event.get("hostname"), "device.example.test")
        self.assertEqual(connect_event.get("port"), 2222)
        self.assertEqual(connect_event.get("username"), "debugger")
        self.assertEqual(connect_event.get("password"), secret)
        self.assertEqual(connect_event.get("timeout"), 7)

    def test_check_reads_password_from_stdin_without_echoing_secret(self) -> None:
        secret = "stdin-secret-value"
        env = self._make_fake_paramiko_env()

        result = self._run_cli(
            ["check", *self._common_args(), "--password-stdin", "--json"],
            env=env,
            input_text=secret,
        )

        payload = self._assert_ok_json(result)
        self._assert_common_json(payload, command="check", auth_mode="password")
        self._assert_secret_not_echoed(secret, result)
        self.assertNotIn(secret, json.dumps(payload, ensure_ascii=False))

        connect_event = self._find_event(self._read_fake_events(), "ssh_client.connect")
        self.assertEqual(connect_event.get("password"), secret)

    def test_check_supports_key_auth_without_password_echo(self) -> None:
        env = self._make_fake_paramiko_env()
        args = ["check", *self._common_args(auth_mode="key"), "--json"]
        key_path = str(self.root / "id_ed25519")

        result = self._run_cli(args, env=env)

        payload = self._assert_ok_json(result)
        self._assert_common_json(payload, command="check", auth_mode="key")
        self.assertNotIn("password", payload)

        events = self._read_fake_events()
        connect_event = self._find_event(events, "ssh_client.connect")
        self.assertIsNone(connect_event.get("password"))
        self.assertTrue(
            any(
                event.get("event") == "pkey.load" and event.get("filename") == key_path
                for event in events
            )
            or connect_event.get("pkey") is not None
            or (
                isinstance(connect_event.get("extra_kwargs"), dict)
                and connect_event["extra_kwargs"].get("key_filename") == key_path
            )
        )

    def test_run_executes_remote_command_and_emits_stable_json(self) -> None:
        secret = "run-secret"
        env = self._make_fake_paramiko_env()
        env["SSH_DEVICE_PASSWORD"] = secret

        result = self._run_cli(
            ["run", *self._common_args(), "--json", "--", "echo", "hello-from-run"],
            env=env,
        )

        payload = self._assert_ok_json(result)
        self._assert_common_json(payload, command="run", auth_mode="password")
        self._assert_secret_not_echoed(secret, result)
        self.assertNotIn(secret, json.dumps(payload, ensure_ascii=False))

        commands = [
            str(event.get("command"))
            for event in self._read_fake_events()
            if event.get("event") == "ssh_client.exec_command"
        ]
        self.assertTrue(commands, "run 子命令没有触发远端命令执行")
        self.assertTrue(
            any("echo" in command and "hello-from-run" in command for command in commands),
            commands,
        )

    def test_deploy_recursive_and_post_command_emit_stable_json(self) -> None:
        secret = "deploy-secret"
        env = self._make_fake_paramiko_env()
        env["SSH_DEVICE_PASSWORD"] = secret

        src_dir = self.root / "payload"
        (src_dir / "nested").mkdir(parents=True)
        (src_dir / "root.txt").write_text("root\n", encoding="utf-8")
        (src_dir / "nested" / "child.txt").write_text("child\n", encoding="utf-8")

        result = self._run_cli(
            [
                "deploy",
                *self._common_args(),
                "--src",
                str(src_dir),
                "--dest",
                "/remote/app",
                "--recursive",
                "--post-cmd",
                "ls -la /remote/app",
                "--json",
            ],
            env=env,
        )

        payload = self._assert_ok_json(result)
        self._assert_common_json(payload, command="deploy", auth_mode="password")
        self.assertEqual(payload.get("src"), str(src_dir))
        self.assertEqual(payload.get("dest"), "/remote/app")
        self.assertEqual(payload.get("recursive"), True)
        self._assert_secret_not_echoed(secret, result)

        events = self._read_fake_events()
        upload_events = [
            event
            for event in events
            if event.get("event") in {"sftp.put", "sftp.putfo"}
        ]
        self.assertGreaterEqual(len(upload_events), 2, upload_events)
        self.assertTrue(
            any(str(event.get("remotepath", "")).endswith("/root.txt") for event in upload_events),
            upload_events,
        )
        self.assertTrue(
            any(str(event.get("remotepath", "")).endswith("/nested/child.txt") for event in upload_events),
            upload_events,
        )
        self.assertTrue(
            any(
                event.get("event") == "ssh_client.exec_command"
                and "ls -la /remote/app" in str(event.get("command"))
                for event in events
            ),
            events,
        )

    def test_container_exec_action_emits_stable_json_and_compose_command(self) -> None:
        secret = "container-secret"
        env = self._make_fake_paramiko_env()
        env["SSH_DEVICE_PASSWORD"] = secret

        result = self._run_cli(
            [
                "container",
                *self._common_args(),
                "--action",
                "exec",
                "--target",
                "web",
                "--compose-file",
                "docker-compose.yml",
                "--workdir",
                "/srv/app",
                "--exec-cmd",
                "id -u",
                "--json",
            ],
            env=env,
        )

        payload = self._assert_ok_json(result)
        self._assert_common_json(payload, command="container", auth_mode="password")
        self.assertEqual(payload.get("action"), "exec")
        self.assertEqual(payload.get("target"), "web")
        self.assertEqual(payload.get("compose_file"), "docker-compose.yml")
        self.assertEqual(payload.get("workdir"), "/srv/app")
        self._assert_secret_not_echoed(secret, result)

        commands = [
            str(event.get("command"))
            for event in self._read_fake_events()
            if event.get("event") == "ssh_client.exec_command"
        ]
        self.assertTrue(commands, "container 子命令没有触发远端命令执行")
        self.assertTrue(
            any("docker compose" in command or "docker-compose" in command for command in commands),
            commands,
        )
        self.assertTrue(any("exec" in command for command in commands), commands)
        self.assertTrue(any("web" in command for command in commands), commands)
        self.assertTrue(any("docker-compose.yml" in command for command in commands), commands)
        self.assertTrue(any("/srv/app" in command for command in commands), commands)
        self.assertTrue(any("id -u" in command for command in commands), commands)


if __name__ == "__main__":
    unittest.main()
