Snow is a local-first tool for running literature reviews with snowballing.

## Development

Start the API for a project:

```sh
uv run snow serve --project /tmp/demo-review
```

Start the Angular UI:

```sh
cd ui
npm run start
```

Open the UI in Electron:

```sh
cd ui
npm run electron
```

Or run the full local development stack with one command:

```sh
cd ui
SNOW_PROJECT=/tmp/demo-review npm run electron:dev
```

`SNOW_PROJECT` must point to a Snow project directory containing `project.yml`.
When it is omitted, the dev script uses `/tmp/demo-review` if it exists, then falls back to the repository root.
