# Deploying to OpenShift from a laptop

End-to-end deployment of the Inventory Optimisation Agent (FastAPI + React)
to an OpenShift cluster, using nothing on your laptop except `oc` and
`helm`. No `docker push` from your machine — images are built on the
cluster from your local source.

## What you need

| Tool | Min version | Install |
|---|---|---|
| OpenShift CLI (`oc`) | 4.14+ | https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/ |
| Helm (`helm`) | 3.12+ | `winget install Helm.Helm` |
| PowerShell | 5.1+ or 7+ | ships with Windows |
| Cluster access | a kubeadmin-level token OR a developer account with `admin` on the target namespace | `oc login --token=... --server=...` |

You do **not** need Docker Desktop, Podman, or any local container runtime.
OpenShift builds the images for you via BuildConfig + `oc start-build`.

## Architecture in OpenShift

```
                ┌─────────────────┐
   Route ──TLS──┤   invopt-ui     │  nginx + static React bundle
                │   (deployment)  │
                └────────┬────────┘
                         │ /v1/*  via nginx proxy (or direct fetch from browser)
                         ▼
                ┌─────────────────┐
   Route ──TLS──┤   invopt-api    │  FastAPI + uvicorn workers
                │   (deployment)  │
                └────────┬────────┘
                         │
            ┌────────────┼─────────────┬──────────────┐
            ▼            ▼             ▼              ▼
        Postgres     Maximo MIF    OpenAI / watsonx   /metrics (Prometheus)
        (in-cluster) (out-of-     (out-of-cluster)
                     cluster)
```

The API needs egress to:
- the Maximo cluster (MIF reads + writebacks)
- the configured LLM provider (OpenAI / Azure OpenAI / watsonx) — only if `LLM_PROVIDER != mock`
- Postgres (in-cluster or managed)

## One-time prep

### 1. Pick or create a target namespace

```powershell
oc login --token=<your-token> --server=https://api.<cluster>:6443
oc new-project invopt-dev --description="Inventory Optimisation Agent (dev)"
```

(or pick an existing namespace with `oc project invopt-dev`)

### 2. Decide where Postgres lives

The API persists recommendations, audit chain, forecasts and planner
feedback in Postgres. Two paths:

**Path A — quick dev / PoC**: let the deployment script provision a
single-replica Postgres in the same namespace using the built-in
`postgresql-persistent` template. Pass `-DeployPostgres`. Connection
string becomes `postgresql+asyncpg://invopt:invopt@postgresql:5432/invopt`.

**Path B — production**: provision Postgres with the Crunchy Postgres
Operator (recommended) or use a managed Postgres (IBM Cloud Databases,
Azure Database for PostgreSQL, RDS, etc.). Provide the full DSN to the
script via `-DatabaseUrl`.

For first-time deployment Path A is the smallest change. Plan a swap to
Path B before any tenant signs off.

### 3. Generate two secrets

```powershell
$jwt   = -join ((1..64) | % { '{0:x}' -f (Get-Random -Min 0 -Max 15) })
$audit = -join ((1..64) | % { '{0:x}' -f (Get-Random -Min 0 -Max 15) })
```

Keep these somewhere safe — rotating either invalidates issued JWTs and
makes pre-rotation audit entries no longer verify against the new key
(rows written before rotation still verify against the old key if you
re-deploy with it).

## Deploy

```powershell
cd D:\GitRepo\maximo-invopt-ui

.\scripts\deploy-openshift.ps1 `
  -Namespace invopt-dev `
  -MaximoBaseUrl "https://manage.maspoc.apps.maspoc.zpih.p1.openshiftapps.com/maximo" `
  -MaximoApiKey  "<your-service-account-api-key>" `
  -JwtSecret     $jwt `
  -AuditHmacSecret $audit `
  -DatabaseUrl   "postgresql+asyncpg://invopt:invopt@postgresql:5432/invopt" `
  -LlmProvider   "openai" `
  -LlmApiKey     "sk-..." `
  -LlmModel      "gpt-4o-mini" `
  -DeployPostgres
```

What the script does, in order:

1. Verifies `oc` + `helm` are installed and you are logged in.
2. Creates or switches to the namespace.
3. (Optional) Creates Postgres from the OpenShift template.
4. Creates / updates the `invopt-api-secrets` Secret with Maximo, JWT,
   audit, database, and LLM credentials.
5. Creates a `BuildConfig` for each image and runs `oc start-build` with
   your local source as the binary input. OpenShift builds the image in
   the cluster, pushes to the internal registry, tags it with the
   timestamp `ImageTag`.
6. `helm upgrade --install invopt-api` and then `invopt-ui` using the
   chart templates in `helm/invopt-api/` and `helm/invopt-ui/`.
7. Prints the Route URLs for both services and a smoke-test command.

End-to-end the first run takes about 6–10 minutes (most of it pulling
base images and building the Python + Node bundles). Subsequent runs
are 2–4 minutes because layer caches are warm.

## Verify

```powershell
$apiHost = oc get route invopt-api -o jsonpath='{.spec.host}'
$uiHost  = oc get route invopt-ui  -o jsonpath='{.spec.host}'

curl -k "https://$apiHost/healthz"      # → {"status":"ok"}
curl -k "https://$apiHost/readyz"       # → {"ready":true,"checks":{"db":true,"maximo":true}}
```

Then open `https://$uiHost` in a browser and log in with your Maximo
username and API key. The dashboard should render against live data
once you've run the first batch:

```powershell
# get a JWT
$login = Invoke-RestMethod -Method Post -Uri "https://$apiHost/auth/login" `
  -ContentType "application/json" `
  -Body (@{username="MAXADMIN"; api_key="<your-key>"} | ConvertTo-Json) `
  -SkipCertificateCheck

$headers = @{ Authorization = "Bearer $($login.access_token)" }

# trigger the orchestrator
Invoke-RestMethod -Method Post -Uri "https://$apiHost/v1/recommendations:run" `
                  -Headers $headers -SkipCertificateCheck
```

## What to flip after the first successful deploy

These all live in `helm/invopt-api/values.yaml` (override via
`--set config.X=Y` on the helm command, or commit a per-env values file):

| Setting | Default | Flip to |
|---|---|---|
| `WRITEBACK_ENABLED` | `false` | `true` once the MXINV_INVENTORY_V1 Object Structure and sigoptions are approved in Maximo. |
| `SCHEDULER_ENABLED` | `false` | `true` once the first manual `:run` looks correct. The default cron is `0 2 * * *`. |
| `AGENT_AUTO_APPLY_ENABLED` | `false` | `true` once `WRITEBACK_ENABLED` is on AND the recommendation quality is signed off by a planner. Start with `AGENT_ALLOWED_CRITICALITIES=LOW` and `AGENT_MAX_DELTA_WC=5000`. |
| `LLM_PROVIDER` | `mock` | `openai` / `azure_openai` / `watsonx` once the API key is in the Secret. |

## Day-2 operations

### Roll a new build without changing config

Just re-run the same script with a new `-ImageTag` (the default uses
the current timestamp). The Deployment's `checksum/config` annotation
is unchanged, so only the image rolls.

### Roll a config change

Edit values and re-run. The `checksum/config` annotation on the pod
template will change with the ConfigMap content, which triggers a rolling
restart automatically — no manual `oc rollout restart` needed.

### Read logs

```powershell
oc logs -l app.kubernetes.io/name=invopt-api --tail=200 -f
oc logs -l app.kubernetes.io/name=invopt-ui  --tail=200 -f
```

Structured JSON logs include `correlation_id` for every request, which
matches the `X-Correlation-Id` header on the response, so you can join
client logs to server logs.

### View metrics

The API exposes Prometheus at `/metrics`. The OpenShift built-in
user-workload monitoring scrapes pods labelled `monitoring.openshift.io/scrape=true`;
add the label to the Deployment template if you want the cluster
Prometheus to pull from `invopt-api`.

### Rollback

```powershell
helm history invopt-api -n invopt-dev
helm rollback invopt-api <revision-number> -n invopt-dev
```

Helm tracks every revision, so a bad config change can be reverted in
seconds without rebuilding any images.

## Common issues

**Pods are CrashLoopBackOff with `pydantic_settings.exceptions.SettingsError`.**
The Secret didn't get applied or one of `MAXIMO_BASE_URL`, `MAXIMO_API_KEY`,
`JWT_SECRET` is missing. `oc describe secret invopt-api-secrets` and
verify all five keys are present.

**`/readyz` returns `"db": false`.**
DATABASE_URL is wrong or the in-cluster Postgres pod is not ready.
`oc get pods | grep postgres`, then `oc logs postgresql-...`.

**`/readyz` returns `"maximo": false`.**
The pod cannot reach the Maximo URL. Most common cause is missing egress
from the namespace — either approve a NetworkPolicy or run `oc edit
egressnetworkpolicy` to allow the Maximo host.

**Browser shows `CORS error`.**
The UI Route host is not in the API's `CORS_ORIGINS`. Re-run the deploy
script — it auto-computes `CORS_ORIGINS` from the cluster's apps domain.
Alternatively `--set config.CORS_ORIGINS="https://<your-ui-host>"`.

**Build fails: `pip install` cannot reach PyPI.**
The cluster build pod is offline. Either configure a PyPI mirror (set
`PIP_INDEX_URL` as a `BuildConfig` env), or push pre-built images to an
external registry and switch the `image.repository` value.
