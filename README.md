# herdr-indicators

[![plugin](https://img.shields.io/badge/plugin-local.state--icons-6f42c1)](https://github.com/ExLuna-rs/herdr-indicators)
[![version](https://img.shields.io/badge/version-0.1.5-blue)](https://github.com/ExLuna-rs/herdr-indicators/releases)
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
- Portable defaults and 8 icon presets (Unicode, ASCII animations, blocks, Nerd Font): no special font required.

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

### 2. Auto-configure the sidebar

The plugin publishes the icons as sidebar **tokens**, but HerdR only displays them if your
`config.toml` references those tokens. One action does it for you:

```bash
herdr plugin action invoke local.state-icons.setup
```

It adds `[ui.sidebar.agents]` and `[ui.sidebar.spaces]` rows using the plugin tokens, saves a backup
(`config.toml.state-icons.bak`), reloads HerdR's config and starts the animator. It is safe to run
again: sections that already use the tokens are skipped, and sections you customized
(with your own `rows`) are left untouched and reported, so you can add the tokens manually.

<details>
<summary>Manual setup (if you prefer, or have custom rows)</summary>

Add this to your HerdR config
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

Then run `herdr server reload-config`.

</details>

Only one of the `*_line` tokens is active at a time (the one matching the current status),
so each status can have its own color. Adjust the colors and rows to taste.

The plugin also starts by itself on HerdR startup and on every agent status change.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Nothing shows in the sidebar | Run `herdr plugin action invoke local.state-icons.setup` (adds the `$state_*` / `$space_*` tokens to `config.toml`). |
| Plugin listed as `disabled` | `herdr plugin enable local.state-icons` |
| Icons appear as empty boxes or `?` | Your terminal font lacks those glyphs. Set `preset = "ascii"` (or another `ascii*` preset), see [Presets](#presets). |
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
| `local.state-icons.setup` | Add the sidebar token rows to HerdR's `config.toml` (with backup), then start the animator |
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
preset = "unicode"

[agent-harness-labels]
claude = "Claude"
copilot = "Copilot"
gpt = "GPT"

[animation]
done-hold-seconds = 5.0
```

The easiest customization is to change `preset` (see [Presets](#presets)), then run
`herdr plugin action invoke local.state-icons.refresh`.

### Overrides

Anything in these optional sections overrides the preset. Remove a key to fall back to the preset.

| Section | Purpose |
|---|---|
| `[icons]` | Glyph for each status (`done`, `blocked`, `idle`, `unknown`, `needs-input`). `working` is a list of spinner frames and is the fallback for all agents. |
| `[agent-working-frames]` | Per-agent spinner frames, overriding `[icons].working`. The key is the lowercase agent name. |
| `[agent-label-icons]` | Logo shown next to the agent name (`$agent_logo_line`). |
| `[agent-harness-labels]` | Display name shown for the agent (`$harness`). Unknown agents show their raw name. |
| `[animation]` | `frame-seconds`: delay between spinner frames (default depends on the preset). `done-hold-seconds`: how long "done" stays visible. |

```toml
preset = "unicode"

[icons]
done = "OK"

[agent-working-frames]
copilot = ["○", "◎", "◉", "●"]

[animation]
frame-seconds = 0.1
```

`config.example.toml` is a commented reference with every option.

> **Upgrading from 0.1.3 or older?** Those versions wrote explicit `[icons]`, `[agent-working-frames]`
> and `[agent-label-icons]` sections into your config, and they override the preset. Delete them (or
> delete `config.toml` and run `refresh`) to use a preset.

Status resolution:

- `working` uses the agent's spinner from `[agent-working-frames]`, or `[icons].working` if the agent has none.
- `done`, `blocked`, `idle`, `unknown` and `needs-input` use `[icons]` for all agents.
- When an agent goes from `working` to `idle`/`done`, `done` is shown for `done-hold-seconds`.
- If HerdR still reports a pending completion (for example while a background shell is running),
  the status stays `working` until it is really finished.

## Presets

Glyphs are drawn by **your terminal's font**, not by the plugin, and a plugin cannot ship a font.
The default `unicode` preset only uses standard symbols that render with any modern terminal font.
The `ascii*` presets only use keyboard characters and work everywhere, even over SSH.

| Preset | Spinner | Done / blocked / idle | Font needed |
|---|---|---|---|
| `unicode` (default) | `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`, per-agent spinners and logos | `✓ ✗ ·` | Any modern font |
| `ascii` | `\| / - \` | `+ ! .` | None |
| `ascii-dots` | `.  ` `.. ` `...` ` ..` | `[+] [!] [.]` | None |
| `ascii-bar` | `[=  ]` `[ = ]` `[  =]` | `[ + ] [ ! ] [ . ]` | None |
| `ascii-bounce` | `o  ` ` o ` `  o` | `[+] [!] [.]` | None |
| `blocks` | `░▒▓█▓▒` | `■ ▲ □` | Almost any font |
| `pulse` | `○◎●◎` | `■ ▲ □` | Almost any font |
| `nerd` | Nerd Font circles, per-agent logos | Nerd Font icons | A [Nerd Font](https://www.nerdfonts.com) as terminal font |

Pick one by editing `config.toml`:

```toml
preset = "ascii-bar"
```

```bash
herdr plugin action invoke local.state-icons.refresh
```

If you see empty boxes, your terminal font lacks those glyphs: switch to an `ascii*` preset.

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
