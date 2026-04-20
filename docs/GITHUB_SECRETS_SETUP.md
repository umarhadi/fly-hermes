# GitHub Secrets Setup

Sebelum menjalankan workflow deploy, setup secrets berikut di repository settings:

## Required Secrets

### 1. `FLY_API_TOKEN`

Token untuk deploy ke Fly.io.

**How to get:**
1. Install flyctl: https://fly.io/docs/flyctl/install/
2. Login: `fly auth login`
3. Create token: `fly tokens create deploy`
4. Copy token (starts with `FlyV1 ...`)

**Add to GitHub:**
1. Repo Settings → Secrets and variables → Actions
2. New repository secret
3. Name: `FLY_API_TOKEN`
4. Value: (paste token)

### 2. `FLY_APP_NAME`

Nama Fly.io app yang akan di-deploy.

**How to get:**
1. Kalau sudah deploy manual: `fly apps list`
2. Kalau belum: create app dengan `fly apps create <name>`
3. Copy nama app (contoh: `hermes-umar-abc123`)

**Add to GitHub:**
1. Repo Settings → Secrets and variables → Actions
2. New repository secret
3. Name: `FLY_APP_NAME`
4. Value: (nama app kamu)

## Usage

Setelah secrets di-setup:
1. Go to Actions tab di GitHub
2. Pilih "Deploy Hermes to Fly.io"
3. Klik "Run workflow"
4. Type "deploy" di confirmation field
5. Klik "Run workflow"
