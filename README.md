# herdr-indicators

[![plugin](https://img.shields.io/badge/plugin-local.state--icons-6f42c1)](https://github.com/ExLuna-rs/herdr-indicators)
[![version](https://img.shields.io/badge/version-0.1.3-blue)](https://github.com/ExLuna-rs/herdr-indicators/releases)
[![herdr](https://img.shields.io/badge/herdr-%3E%3D0.8.2-0ea5e9)](https://github.com/withherdr/herdr)
[![python](https://img.shields.io/badge/python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![platforms](https://img.shields.io/badge/platforms-windows%20%7C%20macos%20%7C%20linux-22c55e)](https://github.com/ExLuna-rs/herdr-indicators)

Animated status icons for the [HerdR](https://github.com/withherdr/herdr) sidebar.
Each agent pane and each workspace shows whether the agent is **working**, **done**,
**blocked**, **idle** or **unknown**, with a per-agent spinner (Claude, Copilot, GPT...).

![HerdR sidebar demo](assets/sidebar-live.gif)

## Features

- Animated spinner while an agent is working, with a different style per agent.
- Stays on **working** while the agent waits on a background shell command, instead of
  flashing a false "done" when it pauses for the shell output.
- "Done" icon held for a few seconds after a task finishes so you notice it.
- Agent logo and display name in the sidebar.
- Works on Windows, macOS and Linux. Only needs Python 3.11+.
- Portable defaults: standard Unicode symbols, no special font required.

## Requirements

- HerdR `>= 0.8.2`
- Python `>= 3.11` available as `python` on your `PATH`

## Quick start

### 1. Install and enable

```bash
herdr plugin install ExLuna-rs/herdr-indicators --yes
herdr plugin enable local.state-icons
```

Check that it is enabled:

```bash
herdr plugin list
```

You should see `local.state-icons ... enabled`.

### 2. Show the icons in the sidebar

The plugin publishes the icons as sidebar **tokens**, but HerdR only displays them if your
`config.toml` references those tokens. Add this to your HerdR config
(Windows: `%USERPROFILE%\.config\herdr\config.toml`, macOS/Linux: `~/.config/herdr/config.toml`):

```toml
[ui.sidebar.spaces]
rows = [
  [
    { token = "$space_working_line", fg = "#ffc799", bold = true },
    { token = "$space_done_line", fg = "#66ddcc", bold = true },
    { token = "$space_blocked_line", fg = "#ff3b5c", bold = true },
    { token = "$space_idle_line", fg = "#39ff88", bold = true },
    { token = "$space_unknown_line", fg = "#5c5c5c", bold = true },
  ],
  ["branch", "git_status"],
]

[ui.sidebar.agents]
rows = [
  [
    { token = "$state_working_line", fg = "#ffc799", bold = true },
    { token = "$state_done_line", fg = "#66ddcc", bold = true },
    { token = "$state_blocked_line", fg = "#ff3b5c", bold = true },
    { token = "$state_idle_line", fg = "#39ff88", bold = true },
    { token = "$state_unknown_line", fg = "#5c5c5c", bold = true },
    "tab",
  ],
  ["agent", "$harness"],
]
```

Only one of the `*_line` tokens is active at a time (the one matching the current status),
so each status can have its own color. Adjust the colors and rows to taste.

### 3. Reload

```bash
herdr server reload-config
herdr plugin action invoke local.state-icons.refresh
```

The plugin also starts by itself on HerdR startup and on every agent status change.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Nothing shows in the sidebar | Step 2 is missing: add the `$state_*` / `$space_*` tokens to `config.toml`, then `herdr server reload-config`. |
| Plugin listed as `disabled` | `herdr plugin enable local.state-icons` |
| Icons appear as empty boxes or `?` | Your terminal font lacks those glyphs. Keep the default config, or use the ASCII preset (see [Fonts and glyphs](#fonts-and-glyphs)). |
| Config changes are ignored | `herdr plugin action invoke local.state-icons.refresh` |
| Spinner stuck after a crash | `herdr plugin action invoke local.state-icons.stop`, then `refresh`. |
| `python` not found | Install Python 3.11+ and make sure `python` is on your `PATH`. |

## Update and uninstall

```bash
herdr plugin update local.state-icons
herdr plugin action invoke local.state-icons.refresh

herdr plugin uninstall local.state-icons
```

## Actions

| Action | What it does |
|---|---|
| `local.state-icons.refresh` | Start the animator and re-read the config |
| `local.state-icons.stop` | Stop the animator and clear all icons |

```bash
herdr plugin action list
herdr plugin action invoke local.state-icons.stop
```

## Sidebar tokens

| Scope | Tokens |
|---|---|
| Agent rows | `$state_working_line`, `$state_done_line`, `$state_blocked_line`, `$state_idle_line`, `$state_unknown_line` |
| Workspace rows | `$space_working_line`, `$space_done_line`, `$space_blocked_line`, `$space_idle_line`, `$space_unknown_line` |
| Agent identity | `$agent_logo_line` (logo glyph), `$harness` (display name) |

## Configuration

The plugin creates a ready-to-use config on first run. Existing values are never overwritten;
only missing keys are appended.

| OS | Path |
|---|---|
| Windows | `%USERPROFILE%\.config\herdr\plugins\config\local.state-icons\config.toml` |
| macOS / Linux | `~/.config/herdr/plugins/config/local.state-icons/config.toml` |

Default config:

```toml
[icons]
working = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
done = "✓"
blocked = "✗"
idle = "·"
unknown = "?"
needs-input = "?"

[agent-working-frames]
claude = ["·", "✢", "*", "✻", "✽"]
copilot = ["○", "◎", "◉", "●"]
gpt = ["◈", "◇", "◈", "◇"]

[agent-label-icons]
claude = "✻"
copilot = "◎"
gpt = "◇"

[agent-harness-labels]
claude = "Claude"
copilot = "Copilot"
gpt = "GPT"

[animation]
frame-seconds = 0.06
done-hold-seconds = 5.0
```

### Sections

| Section | Purpose |
|---|---|
| `[icons]` | Glyph for each status. `working` is a list of spinner frames and is the fallback for all agents. |
| `[agent-working-frames]` | Per-agent spinner frames, overriding `[icons].working`. The key is the lowercase agent name. |
| `[agent-label-icons]` | Logo shown next to the agent name (`$agent_logo_line`). |
| `[agent-harness-labels]` | Display name shown for the agent (`$harness`). Unknown agents show their raw name. |
| `[animation]` | `frame-seconds`: delay between spinner frames. `done-hold-seconds`: how long "done" stays visible. |

Status resolution:

- `working` uses the agent's spinner from `[agent-working-frames]`, or `[icons].working` if the agent has none.
- `done`, `blocked`, `idle`, `unknown` and `needs-input` use `[icons]` for all agents.
- When an agent goes from `working` to `idle`/`done`, `done` is shown for `done-hold-seconds`.
- If HerdR still reports a pending completion (for example while a background shell is running),
  the status stays `working` until it is really finished.

To start over, delete `config.toml` and run `herdr plugin action invoke local.state-icons.refresh`.

## Fonts and glyphs

Glyphs are drawn by **your terminal's font**, not by the plugin, and a plugin cannot ship a font.
For that reason the default config only uses standard Unicode symbols, which render with
any modern terminal font.

| Preset | Needs | File |
|---|---|---|
| Default (Unicode) | Any modern font | auto-generated |
| ASCII | Nothing, works everywhere | `config.example.toml` |
| Nerd Font | A [Nerd Font](https://www.nerdfonts.com) set as the terminal font | `config.nerd-font.example.toml` |

Apply a preset (Windows):

```bash
copy config.nerd-font.example.toml %USERPROFILE%\.config\herdr\plugins\config\local.state-icons\config.toml
herdr plugin action invoke local.state-icons.refresh
```

Apply a preset (macOS / Linux):

```bash
cp config.nerd-font.example.toml ~/.config/herdr/plugins/config/local.state-icons/config.toml
herdr plugin action invoke local.state-icons.refresh
```

If you see empty boxes with the Nerd Font preset, your terminal font is not a Nerd Font.

## Local development

```bash
git clone https://github.com/ExLuna-rs/herdr-indicators
cd herdr-indicators
herdr plugin link . --enabled
```

After editing `state_icons.py`, run `herdr plugin action invoke local.state-icons.stop` then `refresh`
to restart the animator.

## License

MIT
