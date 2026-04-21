# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Does

This repo deploys [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) to Fly.io. It does not contain application code — it wraps the upstream Hermes Agent (tracked as a git submodule) with Fly.io configuration and a GitHub Actions workflow for one-click sync + deploy.

## Repo Structure

| File/Dir | Purpose |
|----------|---------|
| `hermes-agent/` | Git submodule pointing to `NousResearch/hermes-agent` (branch: `main`) |
| `fly.toml` | Fly.io app config — app name `very-hermes`, region `sin`, 2GB shared-cpu-2x VM, `/opt/data` mount |
| `Dockerfile.append` | Appended to upstream `hermes-agent/Dockerfile` at deploy time — adds the shim and sets `CMD ["gateway", "run"]` |
| `hermes-shim` | Shell script (`exec gosu hermes /opt/hermes/.venv/bin/hermes "$@"`) copied to `/usr/local/bin/hermes` so `fly ssh console` works |
| `.github/workflows/deploy.yml` | Manual `workflow_dispatch` workflow: sync submodule → prepare files → flyctl deploy → commit ref |
| `docs/superpowers/` | Design spec and implementation plan for the workflow |

## Deploy Workflow

The workflow (`.github/workflows/deploy.yml`) replicates these manual steps:

```bash
# 1. Update submodule
cd hermes-agent && git fetch origin main && git checkout origin/main && cd ..

# 2. Reset upstream Dockerfile (discard local changes)
git -C hermes-agent checkout -- Dockerfile

# 3. Overlay Fly.io-specific files
cp fly.toml hermes-agent/
cp hermes-shim hermes-agent/
cat Dockerfile.append >> hermes-agent/Dockerfile

# 4. Deploy
flyctl deploy hermes-agent/ --app <FLY_APP_NAME>

# 5. Commit updated submodule ref
git add hermes-agent && git commit -m "chore: update hermes-agent submodule to <sha>"
```

## Required GitHub Secrets

| Secret | Value |
|--------|-------|
| `FLY_API_TOKEN` | `fly tokens create deploy` |
| `FLY_APP_NAME` | Fly.io app name (e.g. `very-hermes`) |

To trigger: GitHub → Actions → "Deploy Hermes to Fly.io" → Run workflow → type `deploy`.

## Submodule Management

```bash
# Initialize after clone
git submodule update --init --recursive

# Update to latest upstream main
git submodule update --remote --merge
```

## Fly.io Notes

- No inbound HTTP service by default — Hermes uses outbound connections to Telegram/Discord/Slack
- Data persisted in `hermes_data` volume mounted at `/opt/data` (set via `HERMES_HOME`)
- To enable inbound webhooks, uncomment the `[http_service]` block in `fly.toml`
- SSH into running machine: `fly ssh console --app very-hermes`; the `hermes` shim is available there

## Local Manual Deploy

```bash
flyctl deploy hermes-agent/ --app very-hermes
```
