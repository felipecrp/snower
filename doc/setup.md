# Setup

## Prerequisites

### Git

Snow uses your **git global identity** as your researcher identity. Before starting Snow, you must have git installed and configured:

```bash
# Verify git is installed
git --version

# Configure your identity (if not already done)
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

If git is not installed or your identity is not configured, `snow serve` will exit with a helpful error message.

### Why git identity?

Your git `user.email` is used as your researcher identifier throughout Snow:

- **Decision files** are named `decisions_{email}.yml` inside each set directory.
- **OpenAlex polite pool** — when triggering snowballing, Snow sends your email in the `User-Agent` and `mailto` parameter, giving your requests priority access and higher rate limits (~10 req/s).
- **Identification section** in the Project view shows your current identity and confirms which email OpenAlex will use.

## Starting the server

```bash
uv run snow serve
# or with a specific project
uv run snow serve --project /path/to/project
```

Snow checks git identity at startup and exits early if it is missing.

## Researcher auto-detection

When you **create** or **open** a project, Snow automatically:

1. Reads `git config --global user.name` and `git config --global user.email`.
2. Creates a researcher entry (`researchers/{email}.yml`) if one does not already exist.
3. Selects that researcher in the topbar so you can start reviewing immediately.

## Researcher storage

Each researcher is stored as a separate YAML file inside the project:

```
<project>/
  researchers/
    alice@example.com.yml   # {name: "Alice Smith"}
    bob@example.com.yml     # {name: "Bob Jones"}
```

The email address is the unique identifier; the file contains only the display name. This layout makes it easy to version-control researcher membership with git.

## Multi-researcher setup

Multiple researchers can work on the same project by sharing the project directory (e.g., via a shared filesystem or git). Each researcher:

1. Must have git configured with their own email.
2. Will be auto-added to `researchers/` when they first open the project.
3. Selects themselves in the topbar dropdown; their decisions are stored in `decisions_{email}.yml` per set.
