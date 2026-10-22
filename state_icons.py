#!/usr/bin/env python3
"""Cross-platform HerdR state icon reporter for sidebar tokens."""

from __future__ import annotations

import json
import os
import re
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
def _icons(done: str, blocked: str, idle: str, unknown: str) -> dict[str, str]:
    return {"done": done, "blocked": blocked, "idle": idle, "unknown": unknown, "needs-input": unknown}


UNICODE_AGENT_FRAMES = {
    "claude": ("·", "✢", "*", "✻", "✽"),
    "copilot": ("○", "◎", "◉", "●"),
    "gpt": ("◈", "◇", "◈", "◇"),
}
UNICODE_LABEL_ICONS = {"claude": "✻", "copilot": "◎", "gpt": "◇"}
SAFE_ICONS = _icons("[+]", "[!]", "[.]", "[?]")
PRESETS: dict[str, dict] = {
    # Standard Unicode symbols: render with any modern terminal font.
    "unicode": {
        "frames": ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"),
        "icons": _icons("✓", "✗", "·", "?"),
        "agent_frames": UNICODE_AGENT_FRAMES,
        "label_icons": UNICODE_LABEL_ICONS,
        "frame_seconds": 0.06,
    },
    # Requires a Nerd Font set as the terminal font.
    "nerd": {
        "frames": tuple(chr(code) for code in range(0xF0A9E, 0xF0AA6)),
        "icons": _icons("\U000F012C", "\U000F0156", "\U000F0766", "\U000F02D7"),
        "agent_frames": UNICODE_AGENT_FRAMES,
        "label_icons": {"claude": "\uEC82", "copilot": "\uEC1E", "gpt": "\U000F9000"},
        "frame_seconds": 0.10,
    },
    # Pure ASCII presets: work everywhere, even over SSH or on bare consoles.
    "ascii": {
        "frames": ("|", "/", "-", "\\"),
        "icons": _icons("+", "!", ".", "?"),
        "agent_frames": {},
        "label_icons": {},
        "frame_seconds": 0.12,
    },
    "ascii-dots": {
        "frames": (".  ", ".. ", "...", " ..", "  ."),
        "icons": SAFE_ICONS,
        "agent_frames": {},
        "label_icons": {},
        "frame_seconds": 0.25,
    },
    "ascii-bar": {
        "frames": ("[=  ]", "[ = ]", "[  =]", "[ = ]"),
        "icons": _icons("[ + ]", "[ ! ]", "[ . ]", "[ ? ]"),
        "agent_frames": {},
        "label_icons": {},
        "frame_seconds": 0.12,
    },
    "ascii-bounce": {
        "frames": ("o  ", " o ", "  o", " o "),
        "icons": SAFE_ICONS,
        "agent_frames": {},
        "label_icons": {},
        "frame_seconds": 0.15,
    },
    # Block and geometric shapes found in nearly every font.
    "blocks": {
        "frames": ("░", "▒", "▓", "█", "▓", "▒"),
        "icons": _icons("■", "▲", "□", "?"),
        "agent_frames": {},
        "label_icons": {},
        "frame_seconds": 0.10,
    },
    "pulse": {
        "frames": ("○", "◎", "●", "◎"),
        "icons": _icons("■", "▲", "□", "?"),
        "agent_frames": {},
        "label_icons": {},
        "frame_seconds": 0.20,
    },
}
DEFAULT_PRESET = "unicode"
DEFAULT_AGENT_WORKING_FRAMES = UNICODE_AGENT_FRAMES
DEFAULT_AGENT_LABEL_ICONS = UNICODE_LABEL_ICONS
DEFAULT_AGENT_HARNESS_LABELS = {
    "claude": "Claude",
    "copilot": "Copilot",
    "gpt": "GPT",
}
AGENT_LABEL_TOKEN = "agent_logo_line"
HARNESS_TOKEN = "harness"
DEFAULT_CONFIG_TOML = f"""# Icon set. One of: {", ".join(PRESETS)}
# Values in [icons], [agent-working-frames], [agent-label-icons] and
# [animation] frame-seconds override the preset; remove them to use it as-is.
preset = "{DEFAULT_PRESET}"

[agent-harness-labels]
claude = "Claude"
copilot = "Copilot"
gpt = "GPT"

[animation]
done-hold-seconds = 5.0
"""
AUTOCONFIG_DEFAULTS = tomllib.loads(DEFAULT_CONFIG_TOML)


@dataclass(frozen=True)
class Settings:
    frames: tuple[str, ...] = DEFAULT_FRAMES
    icons: tuple[tuple[str, str], ...] = tuple(DEFAULT_ICONS.items())
    agent_working_frames: tuple[tuple[str, tuple[str, ...]], ...] = tuple(DEFAULT_AGENT_WORKING_FRAMES.items())
    agent_label_icons: tuple[tuple[str, str], ...] = tuple(DEFAULT_AGENT_LABEL_ICONS.items())
    agent_harness_labels: tuple[tuple[str, str], ...] = tuple(DEFAULT_AGENT_HARNESS_LABELS.items())
    frame_seconds: float = 0.15
    done_hold_seconds: float = 6.0

    def glyph(self, status: str, frame: int, agent_name: str = "") -> str:
        if status == "working":
            frames = self.frames_for_agent(agent_name)
            return frames[frame % len(frames)]
        return dict(self.icons).get(status, dict(self.icons)["unknown"])

    def frames_for_agent(self, agent_name: str) -> tuple[str, ...]:
        if not agent_name:
            return self.frames
        normalized = agent_name.strip().lower()
        return dict(self.agent_working_frames).get(normalized, self.frames)

    def label_icon_for_agent(self, agent_name: str) -> str:
        if not agent_name:
            return ""
        normalized = agent_name.strip().lower()
        return dict(self.agent_label_icons).get(normalized, "")

    def harness_for_agent(self, agent_name: str) -> str:
        if not agent_name:
            return ""
        normalized = agent_name.strip().lower()
        mapped = dict(self.agent_harness_labels).get(normalized)
        if mapped:
            return mapped
        return agent_name


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


def toml_literal(value: object) -> str:
    if isinstance(value, str):
        chunks: list[str] = []
        for ch in value:
            code = ord(ch)
            if ch == "\\":
                chunks.append("\\\\")
            elif ch == '"':
                chunks.append('\\"')
            elif ch == "\n":
                chunks.append("\\n")
            elif ch == "\t":
                chunks.append("\\t")
            elif code > 0xFFFF:
                chunks.append(f"\\U{code:08X}")
            else:
                chunks.append(ch)
        return '"' + "".join(chunks) + '"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(toml_literal(item) for item in value) + "]"
    return toml_literal(str(value))


def append_missing_keys_in_section(text: str, section: str, missing_items: list[tuple[str, object]]) -> str:
    if not missing_items:
        return text
    lines = text.splitlines(keepends=True)
    pattern = re.compile(r"^\[([^\]]+)\]\s*$")
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = pattern.match(line.strip())
        if match:
            starts.append((index, match.group(1)))

    target_range: tuple[int, int] | None = None
    for i, (start_idx, sec_name) in enumerate(starts):
        if sec_name == section:
            end_idx = starts[i + 1][0] if i + 1 < len(starts) else len(lines)
            target_range = (start_idx, end_idx)
            break

    if target_range is None:
        if text and not text.endswith("\n"):
            text += "\n"
        if text and not text.endswith("\n\n"):
            text += "\n"
        text += f"[{section}]\n"
        for key, value in missing_items:
            text += f"{key} = {toml_literal(value)}\n"
        return text

    _, end_idx = target_range
    insertion = [f"{key} = {toml_literal(value)}\n" for key, value in missing_items]
    lines[end_idx:end_idx] = insertion
    return "".join(lines)


def merge_missing_defaults(target: Path) -> None:
    try:
        original = target.read_text(encoding="utf-8")
        parsed = tomllib.loads(original)
    except (OSError, tomllib.TOMLDecodeError):
        return

    updated = original
    changed = False
    for section_name, section_defaults in AUTOCONFIG_DEFAULTS.items():
        if not isinstance(section_defaults, dict):
            continue
        current = parsed.get(section_name)
        if not isinstance(current, dict):
            current = {}
        missing: list[tuple[str, object]] = []
        for key, default_value in section_defaults.items():
            if key not in current:
                missing.append((key, default_value))
        if missing:
            updated = append_missing_keys_in_section(updated, section_name, missing)
            changed = True
            parsed_section = parsed.get(section_name)
            if not isinstance(parsed_section, dict):
                parsed_section = {}
                parsed[section_name] = parsed_section
            for key, default_value in missing:
                parsed_section[key] = default_value

    if changed and updated != original:
        target.write_text(updated, encoding="utf-8")


def ensure_default_config(target: Path) -> None:
    if target.is_file():
        merge_missing_defaults(target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")


def load_settings(path: Path | None = None) -> Settings:
    target = path or config_path()
    ensure_default_config(target)
    if not target.is_file():
        return Settings()
    try:
        with target.open("rb") as config_file:
            config = tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError):
        return Settings()

    icon_config = config.get("icons", {})
    agent_working_config = config.get("agent-working-frames", {})
    agent_label_config = config.get("agent-label-icons", {})
    agent_harness_config = config.get("agent-harness-labels", {})
    animation = config.get("animation", {})

    preset_name = config.get("preset", DEFAULT_PRESET)
    if not isinstance(preset_name, str) or preset_name.strip().lower() not in PRESETS:
        preset_name = DEFAULT_PRESET
    preset = PRESETS[preset_name.strip().lower()]

    if not isinstance(icon_config, dict):
        icon_config = {}
    if not isinstance(animation, dict):
        animation = {}

    frames = icon_config.get("working", preset["frames"])
    if not isinstance(frames, list) or not frames or not all(isinstance(x, str) and x for x in frames):
        frames = preset["frames"]

    icons = {
        state: icon_config.get(state, default)
        if isinstance(icon_config.get(state, default), str)
        else default
        for state, default in preset["icons"].items()
    }
    agent_working_frames: dict[str, tuple[str, ...]] = dict(preset["agent_frames"])
    if isinstance(agent_working_config, dict):
        for raw_key, raw_value in agent_working_config.items():
            if not isinstance(raw_key, str):
                continue
            if isinstance(raw_value, list):
                parsed = tuple(v for v in raw_value if isinstance(v, str) and v)
                if parsed:
                    agent_working_frames[raw_key.strip().lower()] = parsed

    agent_label_icons: dict[str, str] = dict(preset["label_icons"])
    if isinstance(agent_label_config, dict):
        for raw_key, raw_value in agent_label_config.items():
            if isinstance(raw_key, str) and isinstance(raw_value, str) and raw_value:
                agent_label_icons[raw_key.strip().lower()] = raw_value

    agent_harness_labels: dict[str, str] = dict(DEFAULT_AGENT_HARNESS_LABELS)
    if isinstance(agent_harness_config, dict):
        for raw_key, raw_value in agent_harness_config.items():
            if isinstance(raw_key, str) and isinstance(raw_value, str) and raw_value:
                agent_harness_labels[raw_key.strip().lower()] = raw_value

    frame_seconds = animation.get("frame-seconds", preset["frame_seconds"])
    done_hold_seconds = animation.get("done-hold-seconds", 6.0)

    return Settings(
        frames=tuple(frames),
        icons=tuple(icons.items()),
        agent_working_frames=tuple(agent_working_frames.items()),
        agent_label_icons=tuple(agent_label_icons.items()),
        agent_harness_labels=tuple(agent_harness_labels.items()),
        frame_seconds=frame_seconds if isinstance(frame_seconds, (int, float)) and frame_seconds > 0 else preset["frame_seconds"],
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


def agents() -> list[tuple[str, str, str, str, bool]]:
    data = herdr("agent", "list")
    out: list[tuple[str, str, str, str, bool]] = []
    for agent in data.get("result", {}).get("agents", []):
        pane = agent.get("pane_id")
        status = agent.get("agent_status")
        workspace = agent.get("workspace_id")
        tab = agent.get("tab_id")
        agent_name = agent.get("agent")
        completion_seq = agent.get("completion_seq")
        state_change_seq = agent.get("state_change_seq")
        if isinstance(pane, str) and isinstance(status, str):
            tab_id = tab if isinstance(tab, str) else ""
            workspace_id = workspace if isinstance(workspace, str) else tab_id.partition(":")[0]
            has_pending_completion = (
                isinstance(state_change_seq, int)
                and (
                    not isinstance(completion_seq, int)
                    or completion_seq < state_change_seq
                )
            )
            out.append(
                (
                    pane,
                    status,
                    workspace_id,
                    agent_name if isinstance(agent_name, str) else "",
                    has_pending_completion,
                )
            )
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


def resolve_status(
    status: str,
    previous: str | None,
    done_deadline: float,
    now: float,
    hold: float,
    has_pending_completion: bool = False,
) -> tuple[str, float]:
    if status == "working":
        return status, 0.0
    if previous == "working" and has_pending_completion:
        return "working", 0.0
    if previous == "working" and status in ("idle", "done"):
        done_deadline = now + hold
    if now < done_deadline:
        return "done", done_deadline
    return status, 0.0


def compose_line(glyph: str, workspace: str) -> str:
    return " ".join(part for part in (glyph, workspace) if part)


def compose_workspace_line(
    settings: Settings,
    status: str,
    frame: int,
    label: str,
    agent_name: str = "",
) -> str:
    glyph = BLANK_ICON if status == "unknown" else settings.glyph(status, frame, agent_name)
    return compose_line(glyph, label)


def frame_delay(started_at: float, now: float, interval: float) -> float:
    return max(0.0, interval - (now - started_at))


def report(
    source: str,
    pane: str,
    line: str | None,
    status: str | None = None,
    agent_label_icon: str = "",
    harness_label: str = "",
) -> None:
    args = ["pane", "report-metadata", pane, "--source", source]
    for token in LEGACY_TOKENS:
        args += ["--clear-token", token]

    active = TOKENS.get(status or "")
    for token in TOKENS.values():
        if line is not None and token == active:
            args += ["--token", f"{token}={line}"]
        else:
            args += ["--clear-token", token]

    if agent_label_icon:
        args += ["--token", f"{AGENT_LABEL_TOKEN}={agent_label_icon}"]
        display_agent = f"{agent_label_icon} {harness_label}".strip()
        args += ["--display-agent", display_agent]
    else:
        args += ["--clear-token", AGENT_LABEL_TOKEN]
        args += ["--clear-display-agent"]

    if harness_label:
        args += ["--token", f"{HARNESS_TOKEN}={harness_label}"]
    else:
        args += ["--clear-token", HARNESS_TOKEN]
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


SIDEBAR_STATUS_COLORS = (
    ("working", "#ffc799"),
    ("done", "#66ddcc"),
    ("blocked", "#ff3b5c"),
    ("idle", "#39ff88"),
    ("unknown", "#5c5c5c"),
)
SIDEBAR_PREFIXES = {"spaces": "space", "agents": "state"}


def herdr_config_path() -> Path:
    override = os.environ.get("HERDR_CONFIG_PATH")
    if override:
        return Path(override)
    return Path.home() / ".config/herdr/config.toml"


def sidebar_block(kind: str, newline: str = "\n") -> str:
    prefix = SIDEBAR_PREFIXES[kind]
    lines = [f"[ui.sidebar.{kind}]", "rows = ["]
    lines.append("  [")
    for status, color in SIDEBAR_STATUS_COLORS:
        lines.append(f'    {{ token = "${prefix}_{status}_line", fg = "{color}", bold = true }},')
    if kind == "agents":
        lines.append('    "tab",')
        lines.append("  ],")
        lines.append('  ["agent", "$harness"],')
    else:
        lines.append("  ],")
        lines.append('  ["branch", "git_status"],')
    lines.append("]")
    return newline.join(lines) + newline


def sidebar_has_tokens(parsed: dict, kind: str) -> bool:
    section = parsed.get("ui", {}).get("sidebar", {}).get(kind)
    if not isinstance(section, dict):
        return False
    prefix = SIDEBAR_PREFIXES[kind]
    return f"${prefix}_" in json.dumps(section.get("rows", []))


def sidebar_section_exists(parsed: dict, kind: str) -> bool:
    return isinstance(parsed.get("ui", {}).get("sidebar", {}).get(kind), dict)


def setup_sidebar(path: Path | None = None, reload: bool = True) -> list[str]:
    """Add the sidebar token rows to the HerdR config. Returns human-readable messages."""
    target = path or herdr_config_path()
    messages: list[str] = []
    if target.is_file():
        with target.open(encoding="utf-8", newline="") as handle:
            original = handle.read()
        try:
            parsed = tomllib.loads(original)
        except tomllib.TOMLDecodeError as error:
            return [f"Cannot parse {target}: {error}. Nothing changed."]
    else:
        original = ""
        parsed = {}

    newline = "\r\n" if "\r\n" in original else "\n"
    updated = original
    for kind in SIDEBAR_PREFIXES:
        if sidebar_has_tokens(parsed, kind):
            messages.append(f"[ui.sidebar.{kind}] already uses state-icons tokens: skipped.")
        elif sidebar_section_exists(parsed, kind):
            messages.append(
                f"[ui.sidebar.{kind}] already exists with custom rows: not modified. "
                f"Add the tokens manually (see README)."
            )
        else:
            if updated and not updated.endswith(newline):
                updated += newline
            if updated:
                updated += newline
            updated += sidebar_block(kind, newline)
            messages.append(f"[ui.sidebar.{kind}] added.")

    if updated == original:
        return messages

    target.parent.mkdir(parents=True, exist_ok=True)
    if original:
        backup = target.with_name(f"{target.name}.state-icons.bak")
        backup.write_text(original, encoding="utf-8", newline="")
        messages.append(f"Backup saved to {backup}.")
    with target.open("w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    messages.append(f"Updated {target}.")
    if reload:
        herdr("server", "reload-config")
        messages.append("Requested config reload.")
    return messages


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
    pane_logo_shown: dict[str, str] = {}
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
            workspace_working_agent: dict[str, str] = {}
            for _, agent_status, workspace_id, agent_name, _ in current_agents:
                if agent_status == "working" and workspace_id and workspace_id not in workspace_working_agent:
                    workspace_working_agent[workspace_id] = agent_name
            live_panes = {pane for pane, _, _, _, _ in current_agents}
            live_workspaces = {wid for wid, _, _ in current_workspaces}
            keep_running = False

            for pane, status, workspace_id, agent_name, has_pending_completion in current_agents:
                display_status, deadline = resolve_status(
                    status,
                    pane_previous.get(pane),
                    pane_done_until.get(pane, 0.0),
                    now,
                    settings.done_hold_seconds,
                    has_pending_completion,
                )
                pane_previous[pane] = status
                if deadline:
                    pane_done_until[pane] = deadline
                else:
                    pane_done_until.pop(pane, None)

                line = compose_line(settings.glyph(display_status, frame, agent_name), labels.get(workspace_id, ""))
                label_icon = settings.label_icon_for_agent(agent_name)
                harness_label = settings.harness_for_agent(agent_name)
                if pane_shown.get(pane) != line or pane_logo_shown.get(pane) != label_icon:
                    report(source, pane, line, display_status, label_icon, harness_label)
                    pane_shown[pane] = line
                    pane_logo_shown[pane] = label_icon

                keep_running |= display_status == "working" or pane in pane_done_until

            for pane in set(pane_shown) - live_panes:
                report(source, pane, None)
                pane_shown.pop(pane, None)
                pane_logo_shown.pop(pane, None)
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

                workspace_agent_name = workspace_working_agent.get(wid, "")
                line = compose_workspace_line(
                    settings,
                    display_status,
                    frame,
                    label,
                    workspace_agent_name,
                )
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
    if arg == "--setup":
        for message in setup_sidebar():
            print(message)
        spawn_animator()
        return 0

    spawn_animator()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
