# Hermes Agent on Fly.io

Deploy [Hermes Agent](https://github.com/NousResearch/hermes-agent) — the self-improving AI agent from [Nous Research](https://nousresearch.com) — as a Fly.io Machine app, so you can chat with it from Telegram, Discord, Slack, WhatsApp, or Signal no matter where you are.

**Cost:** [roughly](https://fly.io/calculator) **~$15/month** on the default config (`shared-cpu-2x` / 2 GB RAM / 10 GB volume, running 24/7) depending on your region. Can be scaled up or down, turned off when you're not using it. You're charged for running machine time and volume storage.

**Time to first message:** a few minutes, most of it waiting for the initial Docker build.

---

## What you need before you start

- **flyctl** installed and logged in: [install guide](https://fly.io/docs/flyctl/install/), then `fly auth login`
- **A Fly.io account** with a card on file (Machines and volumes aren't in the always-free tier)
- **An LLM API key.** Easiest is [OpenRouter](https://openrouter.ai/keys) — one key, hundreds of models. Anthropic, OpenAI, and [Nous Portal](https://portal.nousresearch.com) also work.
- **A Telegram bot token.** Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow prompts → copy the `123456:ABC…` token.
- **Your Telegram user ID.** Message [@userinfobot](https://t.me/userinfobot) → it replies with your numeric ID. You'll need this so the bot only talks to you.

(Prefer Discord, Slack, or something else? Skip the two Telegram bullets and see the [Hermes messaging docs](https://hermes-agent.nousresearch.com/docs/user-guide/messaging) for platform-specific credential setup.)

---

## Deploy

**1. Clone this repo and Hermes itself:**

```bash
git clone https://github.com/fly-apps/hermes-flyio.git
cd hermes-flyio
git clone https://github.com/NousResearch/hermes-agent.git
```

**2. Pick an app name.** Fly app names are globally unique, so add some randomness:

```bash
export APP="hermes-$(whoami)-$(openssl rand -hex 3)"
sed -i.bak "s/my-hermes/$APP/" fly.toml && rm fly.toml.bak
echo "App name: $APP"
```

(If you'd rather pick by hand, edit `fly.toml`'s `app = …` line and `export APP=your-name` so the rest of the commands work.)

**3. Create the app and its volume:**

```bash
fly apps create $APP
fly volumes create hermes_data --region sjc --size 10 --yes --app $APP
```

Both commands are idempotent enough — if `fly apps create` says the name is taken, re-run step 2 to pick a new one.

**4. Set your secrets:**

```bash
fly secrets set OPENROUTER_API_KEY=sk-or-your-key-here --app $APP
fly secrets set TELEGRAM_BOT_TOKEN=123456:ABC-your-token-here --app $APP
```

**5. Deploy:**

```bash
git -C hermes-agent checkout -- Dockerfile \
  && cp fly.toml hermes-agent/ \
  && cp hermes-shim hermes-agent/ \
  && cat Dockerfile.append >> hermes-agent/Dockerfile \
  && fly deploy hermes-agent/ --app $APP
```

Grab a coffee — the first build takes a few minutes. It's installing `uv`, Node, Playwright's Chromium, and every Python dependency in Hermes's `[all]` extra. Subsequent deploys are much faster thanks to layer caching.

**You'll know it worked** when `fly logs` shows:

```
⚕ Hermes Gateway Starting...
```

followed by a warning about no user allowlists — that's expected; you haven't run setup yet.

> **No public IP by default.** The shipped `fly.toml` doesn't expose any ports — Telegram, Discord, Slack, and friends are all outbound-only, so the machine talks out to the platform APIs and doesn't need to be reachable from the internet. There's nothing to browse at `https://<your-app>.fly.dev`; that's intentional. See [Webhooks](#webhooks-github-stripe-etc) further down if you *do* want inbound HTTP.

---

## First-run setup (one time only)

Run Hermes's interactive setup wizard over SSH. It walks through provider + model, personality, optional tool API keys, and messaging platform config in one flow:

```bash
fly ssh console --pty --app $APP -C "hermes setup"
```

* Pick **Quick Setup**
* When it asks **"Which tools would you like to configure?"** (Exa, Firecrawl, Browserbase, FAL, ElevenLabs, Tinker, …)
  - Just hit `ENTER` with nothing selected — they're all optional
* Select Telegram as the messaging platform
  * Paste the bot token when prompted (should already be in env — it should offer to reuse it)
  * When it asks for allowed users, paste the numeric Telegram ID you got from @userinfobot

Restart the gateway so it picks up the new config:

> **Note:** At the end of setup, Hermes asks "Do you want to restart the gateway?" — you can say yes, but **you still need to run `fly apps restart` below.** That prompt restarts the gateway *process inside the SSH session*, which ends when your SSH session closes. `fly apps restart` restarts the actual Machine so the gateway comes up fresh with your new config.

```bash
fly apps restart $APP
```

Finally, find your bot on Telegram (search for the username you gave @BotFather), send `/start`, and chat.

```bash
fly logs --app $APP    # tail the gateway while you test
```

> **If SSH fails** with "connection refused" or similar: the gateway is crash-looping. Run `fly logs --app $APP` first to see the error — don't retry SSH blindly.

---

## Updating Hermes

```bash
git -C hermes-agent pull
git -C hermes-agent checkout -- Dockerfile \
  && cp fly.toml hermes-agent/ \
  && cp hermes-shim hermes-agent/ \
  && cat Dockerfile.append >> hermes-agent/Dockerfile \
  && fly deploy hermes-agent/ --app $APP
```

Your config, memories, skills, and session history live on the volume at `/opt/data` and roll forward untouched. Bundled skills are reconciled on boot without overwriting your own edits.

## Backups

Everything Hermes learns — memories, skills, SOUL.md, session DB, cron jobs — lives on the `hermes_data` volume. Fly automatically takes **daily snapshots** of every volume and keeps them for **5 days** by default, so you don't need to schedule anything yourself. Retention can be set anywhere from 1 to 60 days.

To bump retention on your existing volume:

```bash
fly volumes list --app $APP
fly volumes update <volume-id> --snapshot-retention 30 --app $APP
```

Or bake it into `fly.toml` under `[mounts]` so every new volume picks up the same setting:

```toml
[mounts]
  source = "hermes_data"
  destination = "/opt/data"
  snapshot_retention = 30
```

To see what snapshots exist, or restore one into a new volume:

```bash
fly volumes snapshots list <volume-id> --app $APP
fly volumes create hermes_data_restored \
  --snapshot-id <snapshot-id> --size 10 --app $APP
```

Snapshot storage is free for the first 10 GB, then [$0.08/GB/month](https://fly.io/docs/about/pricing/#volume-snapshots) on the incremental stored size (not the full volume). A Hermes deployment usually sits well inside the free tier at the default retention — worth a glance at [pricing](https://fly.io/docs/about/pricing/#volume-snapshots) if you bump retention way up or run a very active volume. See the [volume snapshots docs](https://fly.io/docs/volumes/snapshots/) for the full details.

One important caveat: snapshots are daily, so anything Hermes learned between the last snapshot and a host failure is lost. For extra safety against that window, pull a local archive with Hermes's own backup command:

```bash
fly ssh console --pty --app $APP -C "hermes backup create /opt/data/backup.tar.gz"
fly sftp get /opt/data/backup.tar.gz --app $APP
```

## Chatting with the bot

Most of the time you'll chat with Hermes through whichever messaging platform you set up — Telegram, Discord, Slack, WhatsApp, Signal. That's the whole point of running the gateway: your agent is reachable from your phone, your desktop, wherever.

But you can also drop into Hermes's native terminal UI directly on the machine — useful for ad-hoc debugging, running `hermes doctor`, or just grabbing a quick session when you don't want to pull out your phone:

```bash
fly ssh console --pty --app $APP -C "hermes"
```

Exit with `/quit`. The TUI and the gateway share the same `/opt/data` volume, so memories, skills, and session history are unified — a conversation you start over SSH shows up in your history the same as one you had over Telegram.

## Scaling

`shared-cpu-2x` / 2 GB is fine for one person and a few platforms. Heavy skill execution, Playwright browsing, or RL work wants more:

```bash
fly scale vm shared-cpu-4x --memory 4096 --app $APP
fly volumes extend <volume-id> --size 20 --app $APP
```

The default `fly.toml` keeps the machine running 24/7 (`min_machines_running = 1`, `auto_stop_machines = "off"`) because the gateway needs to be online to catch incoming messages. If you're on a pure webhook-only setup and want the machine to suspend when idle, set `auto_stop_machines = "suspend"` and drop `min_machines_running`.

## Webhooks (GitHub, Stripe, etc.)

The default config has **no public ingress** — no HTTP service, no allocated IPs. Messaging platforms don't need it, so nothing listens on the public hostname.

If you *do* want to receive inbound webhooks (GitHub, Stripe, Telegram webhook mode, custom integrations), opt in:

**1. Uncomment the `[http_service]` block in `fly.toml`**, and add this under `[env]`:

```toml
[env]
  HERMES_HOME = "/opt/data"
  WEBHOOK_HOST = "0.0.0.0"
  WEBHOOK_PORT = "8644"
```

**2. Enable the webhook platform** in Hermes so port 8644 actually has a listener:

```bash
fly ssh console --pty --app $APP -C "hermes gateway setup"
# select "webhook" in addition to your other platforms
```

**3. Redeploy and allocate IPs:**

```bash
git -C hermes-agent checkout -- Dockerfile \
  && cp fly.toml hermes-agent/ \
  && cp hermes-shim hermes-agent/ \
  && cat Dockerfile.append >> hermes-agent/Dockerfile \
  && fly deploy hermes-agent/ --app $APP
fly ips allocate-v6 --app $APP
fly ips allocate-v4 --shared --app $APP
```

External services can now POST to `https://<your-app-name>.fly.dev/webhooks/<route-name>`. Define routes with `hermes webhook subscribe …` or statically in `config.yaml` under `platforms.webhook.extra.routes`. See the [webhook docs](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/webhooks) for route syntax and HMAC validation.

## Configuration reference

Secrets always via `fly secrets set` (never committed). Non-secret tunables live in `fly.toml` under `[env]`.

| Variable | Set via | Purpose |
|----------|---------|---------|
| `OPENROUTER_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `NOUS_API_KEY` / … | `fly secrets set` | LLM provider credentials (pick whichever you use) |
| `TELEGRAM_BOT_TOKEN` | `fly secrets set` | Telegram bot token |
| `DISCORD_TOKEN` | `fly secrets set` | Discord bot token |
| `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` | `fly secrets set` | Slack Socket Mode credentials |
| `WEBHOOK_SECRET` | `fly secrets set` | HMAC secret for inbound webhooks (only if webhook adapter enabled) |
| `HERMES_HOME` | `fly.toml` | Pinned to `/opt/data` so Hermes writes onto the volume |
| `WEBHOOK_HOST` / `WEBHOOK_PORT` | `fly.toml` | Only set if you uncomment `[http_service]` for inbound webhooks |

Full list: [Hermes environment variables reference](https://hermes-agent.nousresearch.com/docs/reference/environment-variables).

## How it works

`fly deploy hermes-agent/` builds upstream's Dockerfile with the cloned Hermes repo as the build context. Before deploying, `fly.toml` and a short `Dockerfile.append` are copied in. The append does two things:

1. **Adds a `/usr/local/bin/hermes` shim** that drops to the `hermes` user via `gosu` and invokes the venv's `hermes` binary — so `fly ssh console -C "hermes ..."` works without needing to activate the venv or know about the internal user.
2. **Sets `CMD ["gateway", "run"]`** so the machine boots straight into the messaging gateway in foreground mode. (`gateway start` is for installing a systemd/launchd unit on a host and fails inside a container.)

Everything else is upstream:

- **Entrypoint** (`docker/entrypoint.sh`) runs as root, chowns `/opt/data` (Fly volumes mount as root), drops to the `hermes` user via `gosu`, seeds `.env`, `config.yaml`, and `SOUL.md` from the in-image examples, syncs bundled skills, then `exec`s `hermes gateway run`.
- **Volume** `/opt/data` is `HERMES_HOME` — config, memories, skills, session DB, cron jobs, hooks, plans, workspace, and per-profile `$HOME` for spawned tools.
- **Playwright's Chromium** is installed at `/opt/hermes/.playwright` during build so the volume overlay doesn't hide it at runtime.

For anything past this Fly deployment, see the [Hermes docs](https://hermes-agent.nousresearch.com/docs/).
