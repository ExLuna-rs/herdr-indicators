# herdr-indicators

Cross-platform HerdR state-icons plugin scaffold (Windows/macOS/Linux).

![HerdR sidebar demo](assets/sidebar-live.gif)

## Local dev

```bash
cd C:\Temp\DEV\herdr-indicators
herdr plugin link . --enabled
```

## Actions

- `local.state-icons.refresh`
- `local.state-icons.stop`

## Sidebar tokens

- Agent: `$state_working_line`, `$state_done_line`, `$state_blocked_line`, `$state_idle_line`, `$state_unknown_line`
- Space: `$space_working_line`, `$space_done_line`, `$space_blocked_line`, `$space_idle_line`, `$space_unknown_line`

## Configuration

Config path (after plugin link):

- Windows: `%USERPROFILE%\.config\herdr\plugins\config\local.state-icons\config.toml`
- macOS/Linux: `~/.config/herdr/plugins/config/local.state-icons/config.toml`

The plugin now auto-creates this file on first run with a ready-to-use default
config (icons, per-agent working frames, agent logos, and animation timings).
If a config already exists, the plugin keeps user values and only appends missing
keys/sections required by the plugin.

The plugin reads two sections:

```toml
[icons]
working = ["|", "/", "-", "\\"]
done = "+"
blocked = "!"
idle = "."
unknown = "?"
needs-input = "?"

[animation]
frame-seconds = 0.15
done-hold-seconds = 6.0
```

### Fallback vs per-agent working frames

`[icons]` is the global fallback for all statuses, and also the default `working` spinner.
`[agent-working-frames]` overrides only `working` for matching agents.

```toml
[icons]
# default spinner for unmapped agents
working = ["⠋", "⠙", "⠹", "⠸"]
# always used for non-working statuses
done = "✓"
blocked = "✗"
idle = "·"
unknown = "?"
needs-input = "?"

[agent-working-frames]
# custom working spinner for Copilot
copilot = ["○", "◎", "◉", "●"]
# custom working spinner for Claude
claude = ["·", "✢", "*", "✻", "✽"]
```

Behavior:
- Copilot/Claude in `working` -> uses `agent-working-frames`
- Any other agent in `working` -> uses `[icons].working`
- `done/blocked/idle/unknown/needs-input` -> uses `[icons]` for all agents

### Agent logos and display names

You do not need extra config to run the plugin, but you **do** need these sections if you want
custom logos and custom display names in the sidebar.

```toml
[agent-label-icons]
claude = ""
copilot = ""
gpt = "\U000F9000"

[agent-harness-labels]
claude = "Claude"
copilot = "Copilot"
gpt = "GPT"
```

Behavior:
- `agent-label-icons` sets the logo glyph shown next to the agent name
- `agent-harness-labels` sets the displayed text label
- if omitted, plugin defaults are used

## Presets

- `config.example.toml`: ASCII-safe preset (works everywhere)
- `config.nerd-font.example.toml`: Nerd Font preset with a smoother spinner

To apply a preset:

```bash
copy C:\Temp\DEV\herdr-indicators\config.nerd-font.example.toml %USERPROFILE%\.config\herdr\plugins\config\local.state-icons\config.toml
herdr plugin action invoke local.state-icons.refresh
```

If you want to recreate a fresh default config automatically, delete the file
and run:

```bash
herdr plugin action invoke local.state-icons.refresh
```

## License

MIT
