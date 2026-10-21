#!/usr/bin/env python3
"""Cross-platform HerdR state icon reporter for sidebar tokens."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

TOKENS = {
    "working": "state_working_line",
    "done": "state_done_line",
    "blocked": "state_blocked_line",
    "idle": "state_idle_line",
    "unknown": "state_unknown_line",
}
SPACE_TOKENS = {status: token.replace("state_", "space_", 1) for status, token in TOKENS.items()}
LEGACY_TOKENS = ("state_icon_custom", "state_line_custom")
BLANK_ICON = " "
DEFAULT_FRAMES = ("|", "/", "-", "\\")
DEFAULT_ICONS = {
    "done": "+",
    "blocked": "!",
    "idle": ".",
    "unknown": "?",
    "needs-input": "?",
}
DEFAULT_AGENT_ICONS = {
    "claude": "✳",
    "copilot": "",
    "gpt": "🤖",
    "chatgpt": "🤖",
}


@dataclass(frozen=True)
class Settings:
    frames: tuple[str, ...] = DEFAULT_FRAMES
    icons: tuple[tuple[str, str], ...] = tuple(DEFAULT_ICONS.items())
    agent_icons: tuple[tuple[str, str], ...] = tuple(DEFAULT_AGENT_ICONS.items())
    frame_seconds: float = 0.15
    done_hold_seconds: float = 6.0

    def glyph(self, status: str, frame: int, agent_name: str = "") -> str:
        if status == "working":
            base = self.frames[frame % len(self.frames)]
            agent_icon = self.icon_for_agent(agent_name)
            return f"{agent_icon}{base}" if agent_icon else base
        return dict(self.icons).get(status, dict(self.icons)["unknown"])

    def icon_for_agent(self, agent_name: str) -> str:
        if not agent_name:
            return ""
        normalized = agent_name.strip().lower()
        return dict(self.agent_icons).get(normalized, "")


class CrossPlatformLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.fd: int | None = None

    def acquire(self) -> bool:
        if self.path.exists():
            try:
                stale_pid = int(self.path.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                stale_pid = -1
            if stale_pid <= 0 or not pid_is_running(stale_pid):
                self.path.unlink(missing_ok=True)
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(self.fd, str(os.getpid()).encode("utf-8"))
            return True
        except FileExistsError:
            return False

    def release(self) -> None:
        try:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
        finally:
            self.path.unlink(missing_ok=True)


def config_path() -> Path:
    config_dir = os.environ.get("HERDR_PLUGIN_CONFIG_DIR")
    if config_dir:
        return Path(config_dir) / "config.toml"
    return Path.home() / ".config/herdr/plugins/config/local.state-icons/config.toml"


def load_settings(path: Path | None = None) -> Settings:
    target = path or config_path()
    if not target.is_file():
        return Settings()

    with target.open("rb") as config_file:
        config = tomllib.load(config_file)

    icon_config = config.get("icons", {})
    agent_icon_config = config.get("agent-icons", {})
    animation = config.get("animation", {})

    frames = icon_config.get("working", DEFAULT_FRAMES)
    if not isinstance(frames, list) or not frames or not all(isinstance(x, str) and x for x in frames):
        frames = DEFAULT_FRAMES

    icons = {
        state: icon_config.get(state, default)
        if isinstance(icon_config.get(state, default), str)
        else default
        for state, default in DEFAULT_ICONS.items()
    }
    agent_icons = {
        agent: agent_icon_config.get(agent, default)
        if isinstance(agent_icon_config.get(agent, default), str)
        else default
        for agent, default in DEFAULT_AGENT_ICONS.items()
    }
    for raw_key, raw_value in agent_icon_config.items() if isinstance(agent_icon_config, dict) else []:
        if isinstance(raw_key, str) and isinstance(raw_value, str) and raw_key.strip() and raw_key not in agent_icons:
            agent_icons[raw_key.strip().lower()] = raw_value

    frame_seconds = animation.get("frame-seconds", 0.15)
    done_hold_seconds = animation.get("done-hold-seconds", 6.0)

    return Settings(
        frames=tuple(frames),
        icons=tuple(icons.items()),
        agent_icons=tuple(agent_icons.items()),
        frame_seconds=frame_seconds if isinstance(frame_seconds, (int, float)) and frame_seconds > 0 else 0.15,
        done_hold_seconds=done_hold_seconds if isinstance(done_hold_seconds, (int, float)) and done_hold_seconds >= 0 else 6.0,
    )


def herdr(*args: str) -> dict:
    command = [os.environ.get("HERDR_BIN_PATH", "herdr"), *args]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout = result.stdout or ""
    if result.returncode != 0 or not stdout.strip():
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {}


def agents() -> list[tuple[str, str, str, str]]:
    data = herdr("agent", "list")
    out: list[tuple[str, str, str, str]] = []
    for agent in data.get("result", {}).get("agents", []):
        pane = agent.get("pane_id")
        status = agent.get("agent_status")
        workspace = agent.get("workspace_id")
        tab = agent.get("tab_id")
        agent_name = agent.get("agent")
        if isinstance(pane, str) and isinstance(status, str):
            tab_id = tab if isinstance(tab, str) else ""
            workspace_id = workspace if isinstance(workspace, str) else tab_id.partition(":")[0]
            out.append((pane, status, workspace_id, agent_name if isinstance(agent_name, str) else ""))
    return out


def workspaces() -> list[tuple[str, str, str]]:
    data = herdr("workspace", "list")
    out: list[tuple[str, str, str]] = []
    for ws in data.get("result", {}).get("workspaces", []):
        wid = ws.get("workspace_id")
        label = ws.get("label")
        status = ws.get("agent_status")
        if all(isinstance(v, str) for v in (wid, label, status)):
            out.append((wid, label, status))
    return out


def resolve_status(status: str, previous: str | None, done_deadline: float, now: float, hold: float) -> tuple[str, float]:
    if status == "working":
        return status, 0.0
    if previous == "working" and status in ("idle", "done"):
        done_deadline = now + hold
    if now < done_deadline:
        return "done", done_deadline
    return status, 0.0


def compose_line(glyph: str, workspace: str) -> str:
    return " ".join(part for part in (glyph, workspace) if part)


def compose_workspace_line(settings: Settings, status: str, frame: int, label: str) -> str:
    glyph = BLANK_ICON if status == "unknown" else settings.glyph(status, frame)
    return compose_line(glyph, label)


def frame_delay(started_at: float, now: float, interval: float) -> float:
    return max(0.0, interval - (now - started_at))


def report(source: str, pane: str, line: str | None, status: str | None = None) -> None:
    args = ["pane", "report-metadata", pane, "--source", source]
    for token in LEGACY_TOKENS:
        args += ["--clear-token", token]

    active = TOKENS.get(status or "")
    for token in TOKENS.values():
        if line is not None and token == active:
            args += ["--token", f"{token}={line}"]
        else:
            args += ["--clear-token", token]
    herdr(*args)


def report_workspace(source: str, workspace: str, line: str | None, status: str | None = None) -> None:
    args = ["workspace", "report-metadata", workspace, "--source", source]
    active = SPACE_TOKENS.get(status or "")
    for token in SPACE_TOKENS.values():
        if line is not None and token == active:
            args += ["--token", f"{token}={line}"]
        else:
            args += ["--clear-token", token]
    herdr(*args)


def state_dir() -> Path:
    plugin_id = os.environ.get("HERDR_PLUGIN_ID", "local.state-icons")
    plugin_slug = "".join(ch if ch.isalnum() else "-" for ch in plugin_id).strip("-").lower()
    if not plugin_slug:
        plugin_slug = "local-state-icons"

    base = os.environ.get("HERDR_PLUGIN_STATE_DIR")
    if not base:
        if os.name == "nt":
            base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or str(Path.home())
        else:
            base = os.environ.get("TMPDIR", "/tmp")
    directory = Path(base) / f"herdr-{plugin_slug}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def process_is_running(pid_file: Path) -> bool:
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError, OSError):
        return False


def pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def spawn_animator() -> None:
    pid_file = state_dir() / "animator.pid"
    if process_is_running(pid_file):
        return
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--animate"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def animate(source: str, settings: Settings) -> int:
    lock = CrossPlatformLock(state_dir() / "animator.lock")
    if not lock.acquire():
        return 0

    pid_file = state_dir() / "animator.pid"
    stop_file = state_dir() / "animator.stop"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    stop_file.unlink(missing_ok=True)

    pane_previous: dict[str, str] = {}
    pane_shown: dict[str, str] = {}
    pane_done_until: dict[str, float] = {}
    workspace_previous: dict[str, str] = {}
    workspace_shown: dict[str, str] = {}
    workspace_done_until: dict[str, float] = {}
    frame = 0

    def exit_cleanly(*_: object) -> None:
        stop_file.touch()

    signal.signal(signal.SIGTERM, exit_cleanly)

    try:
        while not stop_file.exists():
            frame_started = time.monotonic()
            now = frame_started
            current_workspaces = workspaces()
            labels = {wid: label for wid, label, _ in current_workspaces}
            current_agents = agents()
            live_panes = {pane for pane, _, _, _ in current_agents}
            live_workspaces = {wid for wid, _, _ in current_workspaces}
            keep_running = False

            for pane, status, workspace_id, agent_name in current_agents:
                display_status, deadline = resolve_status(
                    status,
                    pane_previous.get(pane),
                    pane_done_until.get(pane, 0.0),
                    now,
                    settings.done_hold_seconds,
                )
                pane_previous[pane] = status
                if deadline:
                    pane_done_until[pane] = deadline
                else:
                    pane_done_until.pop(pane, None)

                line = compose_line(settings.glyph(display_status, frame, agent_name), labels.get(workspace_id, ""))
                if pane_shown.get(pane) != line:
                    report(source, pane, line, display_status)
                    pane_shown[pane] = line

                keep_running |= display_status == "working" or pane in pane_done_until

            for pane in set(pane_shown) - live_panes:
                report(source, pane, None)
                pane_shown.pop(pane, None)
                pane_previous.pop(pane, None)
                pane_done_until.pop(pane, None)

            for wid, label, status in current_workspaces:
                display_status, deadline = resolve_status(
                    status,
                    workspace_previous.get(wid),
                    workspace_done_until.get(wid, 0.0),
                    now,
                    settings.done_hold_seconds,
                )
                workspace_previous[wid] = status
                if deadline:
                    workspace_done_until[wid] = deadline
                else:
                    workspace_done_until.pop(wid, None)

                line = compose_workspace_line(settings, display_status, frame, label)
                if workspace_shown.get(wid) != line:
                    report_workspace(source, wid, line, display_status)
                    workspace_shown[wid] = line

                keep_running |= display_status == "working" or wid in workspace_done_until

            for wid in set(workspace_shown) - live_workspaces:
                report_workspace(source, wid, None)
                workspace_shown.pop(wid, None)
                workspace_previous.pop(wid, None)
                workspace_done_until.pop(wid, None)

            if not keep_running:
                break

            frame += 1
            time.sleep(frame_delay(frame_started, time.monotonic(), settings.frame_seconds))
    finally:
        pid_file.unlink(missing_ok=True)
        stop_file.unlink(missing_ok=True)
        lock.release()

    return 0


def stop(source: str) -> None:
    pid_file = state_dir() / "animator.pid"
    (state_dir() / "animator.stop").touch()

    if process_is_running(pid_file):
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGTERM)

    for pane, _, _, _ in agents():
        report(source, pane, None)
    for wid, _, _ in workspaces():
        report_workspace(source, wid, None)


def main() -> int:
    plugin_id = os.environ.get("HERDR_PLUGIN_ID", "local.state-icons")
    source = f"plugin:{plugin_id}"
    arg = sys.argv[1] if len(sys.argv) > 1 else ""

    if arg == "--animate":
        return animate(source, load_settings())
    if arg == "--stop":
        stop(source)
        return 0

    spawn_animator()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
