#!/usr/bin/env python3
"""Check and repair Codex context-window configuration.

This script is intentionally self-contained and uses only the Python standard
library so it can run from Windows, WSL, Linux remotes, and VS Code Server.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONTEXT_WINDOW = 1_000_000
DEFAULT_EFFECTIVE_PERCENT = 100
DEFAULT_AUTO_COMPACT = 800_000
DEFAULT_TARGET_MODEL = "gpt-5.5"


@dataclass(frozen=True)
class Candidate:
    path: Path
    source: str
    priority: int
    pid: str | None = None


def main() -> int:
    args = parse_args()
    codex_home = resolve_codex_home(args.codex_home, args.config_path)
    config_path = Path(args.config_path).expanduser() if args.config_path else codex_home / "config.toml"
    catalog_path = (
        Path(args.catalog_path).expanduser()
        if args.catalog_path
        else codex_home / f"model-catalog-{args.context_window // 1000}k.json"
    )
    target_model = args.target_model or read_top_level_string(config_path, "model") or DEFAULT_TARGET_MODEL
    auto_compact = args.auto_compact if args.auto_compact is not None else min(DEFAULT_AUTO_COMPACT, int(args.context_window * 0.8))

    candidates = find_codex_candidates(args.surface, args.codex)
    if not candidates:
        print("ERROR: no Codex CLI candidate found.", file=sys.stderr)
        print("Use --codex /path/to/codex if Codex is installed in a custom location.", file=sys.stderr)
        return 2

    selected = candidates[0]
    print(f"Selected Codex CLI: {selected.path}")
    print(f"Selected source: {selected.source}" + (f" pid={selected.pid}" if selected.pid else ""))
    version = run_text([str(selected.path), "--version"], env_for_codex(codex_home), timeout=15)
    if version:
        print(f"Version: {version.strip()}")

    if args.list_candidates:
        print("Candidates:")
        for item in candidates:
            suffix = f" pid={item.pid}" if item.pid else ""
            print(f"- {item.source}{suffix}: {item.path}")

    before = load_effective_model(selected.path, codex_home, target_model)
    print_model_state("Before", before)

    needs_repair = model_needs_repair(before, args.context_window, args.effective_percent)
    config_needs_repair = config_needs_changes(config_path, args.context_window, auto_compact)
    if config_needs_repair:
        needs_repair = True

    if args.force:
        needs_repair = True
        print("Status: forced repair requested.")
    elif not needs_repair:
        print("Status: OK. Current Codex configuration already matches the requested context window.")
        print_restart_note(selected, candidates)
        return 0

    if not args.force:
        print("Status: repair needed.")
    if not args.repair:
        print("No files were changed. Re-run with --repair to update the user-level Codex configuration.")
        return 1 if args.strict else 0

    bundled_catalog = load_catalog_for_repair(selected.path, codex_home, target_model)
    patch_catalog(bundled_catalog, target_model, args.context_window, args.effective_percent)
    if not args.dry_run:
        ensure_dir(catalog_path.parent)
        catalog_path.write_text(json.dumps(bundled_catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        update_config(config_path, catalog_path, args.context_window, auto_compact)
    else:
        print("Dry run: no files were written.")

    after = load_effective_model(selected.path, codex_home, target_model) if not args.dry_run else None
    if after:
        print_model_state("After", after)
        if model_needs_repair(after, args.context_window, args.effective_percent):
            print("ERROR: repair completed, but Codex still reports a mismatched context window.", file=sys.stderr)
            return 3

    if not args.dry_run:
        print(f"Wrote catalog: {catalog_path}")
        print(f"Updated config: {config_path}")
    print_restart_note(selected, candidates)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check and repair Codex context-window configuration.")
    parser.add_argument("--repair", action="store_true", help="Write config.toml and model catalog fixes.")
    parser.add_argument("--force", action="store_true", help="Regenerate the catalog even when the current values look correct.")
    parser.add_argument("--dry-run", action="store_true", help="Compute changes without writing files.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when check-only mode finds drift.")
    parser.add_argument("--surface", choices=["auto", "vscode", "path"], default="vscode", help="Which Codex surface to target.")
    parser.add_argument("--codex", help="Explicit Codex CLI path to use.")
    parser.add_argument("--codex-home", help="Codex home directory. Defaults to CODEX_HOME or ~/.codex.")
    parser.add_argument("--config-path", help="Path to config.toml. Defaults to CODEX_HOME/config.toml.")
    parser.add_argument("--catalog-path", help="Path for the generated JSON model catalog.")
    parser.add_argument("--target-model", help=f"Model slug to patch. Defaults to config model or {DEFAULT_TARGET_MODEL}.")
    parser.add_argument("--context-window", type=int, default=DEFAULT_CONTEXT_WINDOW, help="Desired model context window.")
    parser.add_argument("--effective-percent", type=int, default=DEFAULT_EFFECTIVE_PERCENT, help="Desired effective context percent.")
    parser.add_argument("--auto-compact", type=int, default=None, help="Desired model_auto_compact_token_limit.")
    parser.add_argument("--list-candidates", action="store_true", help="Print all detected Codex CLI candidates.")
    return parser.parse_args()


def resolve_codex_home(raw_home: str | None, raw_config: str | None) -> Path:
    if raw_home:
        return Path(raw_home).expanduser()
    if raw_config:
        return Path(raw_config).expanduser().parent
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser()
    return Path.home() / ".codex"


def env_for_codex(codex_home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    return env


def find_codex_candidates(surface: str, explicit: str | None) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[str] = set()

    def add(path: Path | str | None, source: str, priority: int, pid: str | None = None) -> None:
        if not path:
            return
        item = Path(path).expanduser()
        if not item.exists() or not item.is_file():
            return
        key = norm_path(item)
        if key in seen:
            return
        seen.add(key)
        candidates.append(Candidate(item, source, priority, pid))

    if explicit:
        add(explicit, "explicit --codex", 0)

    if surface in {"auto", "vscode"}:
        for proc in find_running_app_servers():
            add(proc["path"], "running VS Code Codex app-server", 10, proc.get("pid"))
        for path in find_vscode_extension_codex_binaries():
            add(path, "VS Code extension bundled Codex", 20)

    if surface in {"auto", "path"} or not candidates:
        add(shutil.which("codex"), "PATH codex", 50)
        add(shutil.which("codex.exe"), "PATH codex.exe", 50)

    candidates.sort(key=lambda c: (c.priority, -safe_mtime(c.path), str(c.path).lower()))
    return candidates


def find_running_app_servers() -> list[dict[str, str]]:
    if os.name == "nt":
        return find_running_app_servers_windows()
    return find_running_app_servers_posix()


def find_running_app_servers_windows() -> list[dict[str, str]]:
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        return []
    command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match '^codex(\\.exe)?$' -and $_.CommandLine -match 'app-server' } | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            [shell, "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception:
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    rows = data if isinstance(data, list) else [data]
    found = []
    for row in rows:
        cmdline = str(row.get("CommandLine") or "")
        exe = extract_exe_before_app_server(cmdline, windows=True)
        if exe:
            found.append({"pid": str(row.get("ProcessId") or ""), "path": exe})
    return found


def find_running_app_servers_posix() -> list[dict[str, str]]:
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception:
        return []
    found = []
    for line in proc.stdout.splitlines():
        if "codex" not in line or "app-server" not in line:
            continue
        match = re.match(r"\s*(\d+)\s+(.*)$", line)
        if not match:
            continue
        pid, cmdline = match.groups()
        exe = extract_exe_before_app_server(cmdline, windows=False)
        if exe:
            found.append({"pid": pid, "path": exe})
    return found


def extract_exe_before_app_server(cmdline: str, windows: bool) -> str | None:
    text = cmdline.strip()
    if not text:
        return None
    if windows:
        quoted = re.match(r'^"([^"]+codex(?:\.exe)?)"\s+app-server\b', text, re.IGNORECASE)
        if quoted:
            return quoted.group(1)
        plain = re.match(r"^(.*?codex(?:\.exe)?)\s+app-server\b", text, re.IGNORECASE)
        return plain.group(1) if plain else None
    try:
        parts = re.split(r"\s+", text)
    except ValueError:
        return None
    for index, part in enumerate(parts):
        if part == "app-server" and index > 0:
            return parts[0]
    return None


def find_vscode_extension_codex_binaries() -> list[Path]:
    home = Path.home()
    roots = [
        home / ".vscode" / "extensions",
        home / ".vscode-insiders" / "extensions",
        home / ".vscode-server" / "extensions",
        home / ".vscode-server-insiders" / "extensions",
        home / ".cursor" / "extensions",
        home / ".cursor-server" / "extensions",
        home / ".windsurf" / "extensions",
        home / ".windsurf-server" / "extensions",
    ]
    env_roots = [
        os.environ.get("VSCODE_EXTENSIONS"),
        os.environ.get("VSCODE_SERVER_EXTENSIONS"),
    ]
    for raw in env_roots:
        if raw:
            roots.append(Path(raw).expanduser())

    binaries: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for ext in root.glob("openai.chatgpt-*"):
            for binary in ext.glob("bin/*/codex*"):
                if binary.is_file() and is_codex_binary_name(binary.name) and is_current_platform_binary(binary):
                    binaries.append(binary)
    return sorted(binaries, key=lambda p: (-safe_mtime(p), str(p).lower()))


def is_codex_binary_name(name: str) -> bool:
    lowered = name.lower()
    return lowered == "codex" or lowered == "codex.exe"


def is_current_platform_binary(path: Path) -> bool:
    platform_dir = path.parent.name.lower()
    system = platform.system().lower()
    if system == "windows":
        return "windows" in platform_dir and path.name.lower().endswith(".exe")
    if system == "linux":
        return "linux" in platform_dir and not path.name.lower().endswith(".exe")
    if system == "darwin":
        return ("macos" in platform_dir or "darwin" in platform_dir) and not path.name.lower().endswith(".exe")
    return True


def load_effective_model(codex: Path, codex_home: Path, target_model: str) -> dict[str, Any] | None:
    try:
        catalog = run_codex_json(codex, ["debug", "models"], codex_home)
    except RuntimeError as exc:
        print(f"WARNING: failed to read configured model catalog: {exc}", file=sys.stderr)
        return None
    return find_model(catalog, target_model)


def load_catalog_for_repair(codex: Path, codex_home: Path, target_model: str) -> dict[str, Any]:
    errors: list[str] = []
    for args in (["debug", "models", "--bundled"], ["debug", "models"]):
        try:
            catalog = run_codex_json(codex, args, codex_home)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        if find_model(catalog, target_model):
            return catalog
    details = "; ".join(errors) if errors else "target model not found"
    raise SystemExit(f"ERROR: could not load a model catalog containing {target_model}: {details}")


def run_codex_json(codex: Path, args: list[str], codex_home: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [str(codex), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env_for_codex(codex_home),
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"exit {proc.returncode}").strip())
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON from codex {' '.join(args)}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise RuntimeError("model catalog JSON does not contain a models array")
    return data


def run_text(command: list[str], env: dict[str, str], timeout: int) -> str:
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
        )
    except Exception:
        return ""
    return proc.stdout or proc.stderr


def find_model(catalog: dict[str, Any], target_model: str) -> dict[str, Any] | None:
    for item in catalog.get("models", []):
        if isinstance(item, dict) and item.get("slug") == target_model:
            return item
    return None


def patch_catalog(catalog: dict[str, Any], target_model: str, context_window: int, effective_percent: int) -> None:
    model = find_model(catalog, target_model)
    if not model:
        raise SystemExit(f"ERROR: model {target_model} not found in catalog")
    model["context_window"] = context_window
    model["max_context_window"] = context_window
    model["effective_context_window_percent"] = effective_percent


def model_needs_repair(model: dict[str, Any] | None, context_window: int, effective_percent: int) -> bool:
    if not model:
        return True
    return (
        int(model.get("context_window") or 0) != context_window
        or int(model.get("max_context_window") or 0) != context_window
        or int(model.get("effective_context_window_percent") or 0) != effective_percent
    )


def print_model_state(label: str, model: dict[str, Any] | None) -> None:
    if not model:
        print(f"{label}: model state unavailable")
        return
    context_window = int(model.get("context_window") or 0)
    max_context_window = int(model.get("max_context_window") or 0)
    percent = int(model.get("effective_context_window_percent") or 0)
    effective = int(context_window * percent / 100) if percent else context_window
    print(
        f"{label}: slug={model.get('slug')} context_window={context_window} "
        f"max_context_window={max_context_window} effective_percent={percent} "
        f"effective_window={effective}"
    )


def config_needs_changes(config_path: Path, context_window: int, auto_compact: int) -> bool:
    raw = read_text_if_exists(config_path)
    return (
        read_top_level_int_from_text(raw, "model_context_window") != context_window
        or read_top_level_int_from_text(raw, "model_auto_compact_token_limit") != auto_compact
    )


def update_config(config_path: Path, catalog_path: Path, context_window: int, auto_compact: int) -> None:
    ensure_dir(config_path.parent)
    raw = read_text_if_exists(config_path)
    raw = set_top_level_key(raw, "model_catalog_json", quote_toml_string(path_for_toml(catalog_path)))
    raw = set_top_level_key(raw, "model_context_window", str(context_window))
    raw = set_top_level_key(raw, "model_auto_compact_token_limit", str(auto_compact))
    config_path.write_text(raw, encoding="utf-8")


def set_top_level_key(raw: str, key: str, value_literal: str) -> str:
    lines = raw.splitlines()
    first_table = len(lines)
    key_re = re.compile(rf"^(\s*){re.escape(key)}\s*=.*$")
    for index, line in enumerate(lines):
        if re.match(r"^\s*\[", line):
            first_table = index
            break
        if key_re.match(line):
            lines[index] = f"{key} = {value_literal}"
            return "\n".join(lines).rstrip() + "\n"

    insert_at = first_table
    while insert_at > 0 and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    lines.insert(insert_at, f"{key} = {value_literal}")
    return "\n".join(lines).rstrip() + "\n"


def read_top_level_string(config_path: Path, key: str) -> str | None:
    return read_top_level_string_from_text(read_text_if_exists(config_path), key)


def read_top_level_string_from_text(raw: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*(['\"])(.*?)\1\s*(?:#.*)?$", top_level_text(raw))
    return match.group(2) if match else None


def read_top_level_int_from_text(raw: str, key: str) -> int | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*([0-9_]+)\s*(?:#.*)?$", top_level_text(raw))
    return int(match.group(1).replace("_", "")) if match else None


def top_level_text(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        if re.match(r"^\s*\[", line):
            break
        lines.append(line)
    return "\n".join(lines)


def read_text_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return ""


def quote_toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def path_for_toml(path: Path) -> str:
    return str(path).replace("\\", "/")


def print_restart_note(selected: Candidate, candidates: list[Candidate]) -> None:
    running = [item for item in candidates if item.source.startswith("running ")]
    if running:
        print("Note: a VS Code Codex app-server is already running. Reload the VS Code window or restart the Codex extension before expecting VS Code UI sessions to pick up startup-only catalog changes.")
    elif selected.source.startswith("VS Code"):
        print("Note: VS Code extension sessions load model_catalog_json on app-server startup. Reload VS Code after repair if the sidebar was already open.")
    else:
        print("Note: non-VS Code CLI sessions should pick up the config on the next new Codex process.")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def norm_path(path: Path) -> str:
    try:
        return str(path.resolve()).lower() if os.name == "nt" else str(path.resolve())
    except OSError:
        return str(path).lower() if os.name == "nt" else str(path)


if __name__ == "__main__":
    if platform.system() == "Windows":
        # Make UTF-8 output more predictable when launched from PowerShell/cmd.
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    raise SystemExit(main())
