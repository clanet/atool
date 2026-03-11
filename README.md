# ATOOL

ATOOL is an AI-driven ops CLI that turns natural-language requests into step-by-step system operations.

It is a single-file Python tool designed for day-to-day terminal work such as inspecting logs, checking disk usage, reading files, editing files, and running shell commands with confirmation prompts.

## Features

- Natural-language ops workflow from the terminal
- Supports `openai`, `claude`, and `codex` providers
- Single-file Python script with no external dependencies
- Built-in confirmation flow for risky actions
- Conversation context persistence for multi-step tasks
- Optional custom system prompt via `~/.atool/ATOOL.md`
- Proxy support for HTTP/HTTPS and SOCKS5
- Interactive first-run setup wizard

## How It Works

ATOOL sends your task description to a model and lets the model use a small set of local tools:

- `execute_command`: run shell commands
- `read_file`: read local files
- `write_file`: write local files

The tool runs in a loop:

1. Send your task to the selected model
2. Receive tool calls from the model
3. Ask for confirmation before executing actions
4. Feed the execution result back to the model
5. Continue until the task is complete or the iteration limit is reached

## Requirements

- Linux, macOS, or another Unix-like environment with Python 3
- A supported model provider account
- Valid API credentials or OAuth token, depending on provider

## Installation

Clone the repository and make the script executable if needed:

```bash
git clone https://github.com/clanet/atool.git
cd atool
chmod +x atool
```

You can also run it directly with Python:

```bash
python3 atool --help
```

## Quick Start

Run a task directly:

```bash
./atool "check disk usage"
./atool "show recent nginx errors"
./atool "read /etc/hosts"
```

Continue the previous conversation context:

```bash
./atool -c "continue troubleshooting the service"
```

Skip confirmation prompts:

```bash
./atool -y "clean temporary files older than 7 days"
```

Choose a provider explicitly:

```bash
./atool -p claude "inspect system load"
./atool -p codex "find large files under /var/log"
```

## Command-Line Options

```text
usage: atool [-h] [-y] [-c] [-p {openai,claude,codex}] [--api-url API_URL]
             [--api-key API_KEY] [--model MODEL] [--proxy PROXY]
             [task ...]
```

Options:

- `-y`, `--yes`: skip all confirmations
- `-c`, `--continue`: continue previous conversation
- `-p`, `--provider`: choose `openai`, `claude`, or `codex`
- `--api-url`: override API base URL
- `--api-key`: set API key on the command line
- `--model`: override model name
- `--proxy`: set proxy, including `http://`, `https://`, `socks5://`, or `socks5h://`

If no task is passed and the session is interactive, ATOOL prompts for one.

## First-Run Setup

On first launch, ATOOL starts an interactive setup wizard and writes configuration to:

- `~/.atool/config.ini`

The config file is expected to be owned by the current user. ATOOL ignores the file if ownership looks unsafe.

## Configuration Priority

Configuration is merged in this order:

1. CLI arguments
2. Environment variables
3. `~/.atool/config.ini`
4. Built-in defaults

## Default Providers and Models

Current built-in defaults are:

- `openai`: API URL `https://api.openai.com/v1`, model `gpt-5.4`
- `claude`: API URL `https://api.anthropic.com/v1`, model `claude-sonnet-4-20250514`
- `codex`: API URL `https://api.openai.com/v1`, model `gpt-5.4`

## Environment Variables

For `openai` and `codex`:

- `OPENAI_API_BASE`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

For `claude`:

- `ANTHROPIC_API_URL`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

## Example Config

Example `~/.atool/config.ini`:

```ini
[default]
provider = openai
api_url = https://api.openai.com/v1
api_key = YOUR_API_KEY
model = gpt-5.4
proxy =
auth_type = key
confirm_default = y
max_tokens = 8192
language = en
```

Notes:

- `confirm_default` controls the default answer for confirmations
- `auth_type` supports `key` and `oauth`
- CLI `--api-key` works, but environment variables or config are safer because command-line arguments may be visible in the process list

## OAuth Token Loading

When `auth_type = oauth` and no API key is stored in config, ATOOL attempts to load tokens from local provider files.

This is mainly intended for local CLI-based workflows where authentication has already been performed by another tool.

## Files Used by ATOOL

- `~/.atool/config.ini`: main configuration
- `~/.atool/context.json`: saved conversation state for `--continue`
- `~/.atool/ATOOL.md`: optional custom system prompt additions

## Safety Model

ATOOL is designed to be useful without being fully hands-off.

Key behaviors:

- Commands are executed through explicit tool calls
- Risky actions can be reviewed before execution
- Config ownership is checked before loading secrets
- Reading the config file through the model tool is blocked to avoid leaking API keys
- The main loop has an iteration cap to prevent runaway sessions

That said, ATOOL can still execute real system commands. Review actions carefully, especially when using `-y`.

## Typical Use Cases

- Check disk, memory, process, or network status
- Inspect logs and service behavior
- Read or update local project files
- Troubleshoot developer environments
- Perform small, guided admin tasks from natural language

## Limitations

- No test suite is included right now
- Primarily built for terminal-based Unix-like environments
- Network/API behavior depends on the selected provider
- Tool access is intentionally limited to command execution and file read/write

## Development

This repository currently centers around one executable script:

- `atool`

Supporting project files:

- `CLAUDE.md`: contributor and agent guidance
- `.gitignore`: ignored local cache artifacts

## License

No license file is included in the repository at the moment. Add one before publishing if you want to define reuse terms.
