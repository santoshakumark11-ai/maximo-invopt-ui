<#
.SYNOPSIS
  End-to-end OpenShift deployment for the Inventory Optimisation Agent
  (FastAPI + React) from a developer laptop using oc + helm.

.DESCRIPTION
  Steps performed:
    1. Verifies oc + helm CLIs are installed and you're logged in.
    2. Creates / switches into the target namespace.
    3. Creates Postgres (optional — only when -DeployPostgres is set).
    4. Creates the Secret with Maximo + JWT + audit + LLM credentials.
    5. Creates an OpenShift BuildConfig for each image and starts a binary
       build from your local source — no docker push from the laptop needed.
    6. Helm upgrade --install for invopt-api and invopt-ui.
    7. Prints the Route URLs and a smoke-test command.

.PARAMETER Namespace
  OpenShift project (namespace).  Defaults to 'invopt'.

.PARAMETER ImageTag
  Tag applied to the built images.  Defaults to a timestamped value so a
  rerun always triggers a rolling restart.

.PARAMETER MaximoBaseUrl
  Full Maximo URL with /maximo suffix.

.PARAMETER MaximoApiKey
  Service-account API key used by the backend for MIF data calls.

.PARAMETER JwtSecret
  HS256 signing secret for the JWT (use a long random string).

.PARAMETER AuditHmacSecret
  HMAC secret for the WORM audit chain.

.PARAMETER DatabaseUrl
  postgresql+asyncpg://user:pass@host:5432/dbname

.PARAMETER LlmProvider
  Optional.  One of: mock | openai | azure_openai | watsonx.

.PARAMETER LlmApiKey
  Optional.

.PARAMETER LlmEndpoint
  Optional (required for azure_openai and watsonx).

.PARAMETER DeployPostgres
  If set, deploys a single-replica Postgres in the same namespace using
  OpenShift's built-in postgresql-persistent template.  Suitable for dev /
  PoC only — production should use a managed Postgres or the Crunchy operator.

.EXAMPLE
  .\scripts\deploy-openshift.ps1 `
    -Namespace invopt-dev `
    -MaximoBaseUrl "https://manage.maspoc.apps.maspoc.zpih.p1.openshiftapps.com/maximo" `
    -MaximoApiKey "abc..." `
    -JwtSecret (-join ((1..64) | % { [char](Get-Random -Min 97 -Max 122) })) `
    -AuditHmacSecret (-join ((1..64) | % { [char](Get-Random -Min 97 -Max 122) })) `
    -DatabaseUrl "postgresql+asyncpg://invopt:invopt@postgresql:5432/invopt" `
    -LlmProvider openai `
    -LlmApiKey "sk-..." `
    -DeployPostgres
#>

param(
  [Parameter(Mandatory=$false)]
  [string]$Namespace = "invopt",

  [Parameter(Mandatory=$false)]
  [string]$ImageTag = (Get-Date -Format "yyyyMMdd-HHmmss"),

  [Parameter(Mandatory=$true)]
  [string]$MaximoBaseUrl,

  [Parameter(Mandatory=$true)]
  [string]$MaximoApiKey,

  [Parameter(Mandatory=$true)]
  [string]$JwtSecret,

  [Parameter(Mandatory=$true)]
  [string]$AuditHmacSecret,

  [Parameter(Mandatory=$true)]
  [string]$DatabaseUrl,

  [string]$LlmProvider = "mock",
  [string]$LlmApiKey  = "",
  [string]$LlmEndpoint = "",
  [string]$LlmModel = "",

  [switch]$DeployPostgres,

  [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host "--> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Die($msg)  { Write-Host "  [ERROR] $msg" -ForegroundColor Red; exit 1 }

# ── 0. Prerequisites ────────────────────────────────────────────────────────
Step "Verifying CLIs"
foreach ($cli in @("oc", "helm")) {
  if (-not (Get-Command $cli -ErrorAction SilentlyContinue)) {
    Die "$cli not found on PATH. Install it and rerun."
  }
}
Ok "oc + helm present"

try { oc whoami | Out-Null } catch { Die "Not logged in to OpenShift. Run 'oc login' first." }
$user = oc whoami
$server = oc whoami --show-server
Ok "Logged in as ${user} at $server"

# ── 1. Namespace ────────────────────────────────────────────────────────────
Step "Namespace '$Namespace'"
if (-not (oc get project $Namespace --ignore-not-found)) {
    oc new-project $Namespace --description="Inventory Optimisation Agent" | Out-Null
    Ok "Created project $Namespace"
} else {
    oc project $Namespace | Out-Null
    Ok "Switched to existing project $Namespace"
}

# ── 2. Deploying Postgres ───────────────────────────────────────────────────
if ($DeployPostgres) {
    Step "Deploying Postgres in ${Namespace} (DEV - not for production)"
    $pgExists = oc get deploymentconfig postgresql --ignore-not-found
    if ($pgExists) {
        Ok "Postgres already present - skipping creation"
    } else {
        oc new-app --template=postgresql-persistent `
          -p POSTGRESQL_USER=invopt `
          -p POSTGRESQL_PASSWORD=invopt `
          -p POSTGRESQL_DATABASE=invopt `
          -p POSTGRESQL_VERSION=15-el8 `
          -p VOLUME_CAPACITY=4Gi | Out-Null
        Ok "Postgres deployment started - waiting for ready..."
        oc rollout status deploymentconfig/postgresql --timeout=180s | Out-Null
        Ok "Postgres ready"
        Warn "Set -DatabaseUrl 'postgresql+asyncpg://invopt:invopt@postgresql:5432/invopt' on your next deploy"
    }
}

# ── 3. Secret ───────────────────────────────────────────────────────────────
Step "Creating / updating Secret 'invopt-api-secrets'"
$secretArgs = @(
  "create", "secret", "generic", "invopt-api-secrets",
  "--from-literal=MAXIMO_API_KEY=$MaximoApiKey",
  "--from-literal=JWT_SECRET=$JwtSecret",
  "--from-literal=AUDIT_HMAC_SECRET=$AuditHmacSecret",
  "--from-literal=DATABASE_URL=$DatabaseUrl",
  "--dry-run=client", "-o", "yaml"
)
if ($LlmApiKey)  { $secretArgs += "--from-literal=LLM_API_KEY=$LlmApiKey" }
if ($LlmEndpoint){ $secretArgs += "--from-literal=LLM_ENDPOINT=$LlmEndpoint" }
& oc @secretArgs | oc apply -f - | Out-Null
Ok "Secret applied"

# ── 4. Build images on-cluster (no docker on the laptop required) ───────────
function EnsureBinaryBuild($name, $contextDir, $dockerfileRel) {
  $bcExists = oc get buildconfig $name --ignore-not-found
  if (-not $bcExists) {
    Step "Creating BuildConfig '$name'"
    oc new-build --binary --name=$name --strategy=docker | Out-Null
    Ok "BuildConfig $name created"
  }
  Step "Starting build for '$name' (context: $contextDir)"
  oc start-build $name --from-dir=$contextDir --follow | Out-Null
  Ok "Build $name complete"

  Step "Tagging image as :$ImageTag"
  oc tag "${name}:latest" "${name}:${ImageTag}" | Out-Null
  Ok "${name}:${ImageTag} ready"
}

EnsureBinaryBuild -name "invopt-api" -contextDir (Join-Path $RepoRoot "api") -dockerfileRel "Dockerfile"

# UI build context is repo root (the Dockerfile copies from web/dashboard/).
EnsureBinaryBuild -name "invopt-ui"  -contextDir $RepoRoot -dockerfileRel "Dockerfile"

# ── 5. Helm: API ────────────────────────────────────────────────────────────
Step "helm upgrade --install invopt-api"
$apiImage = "image-registry.openshift-image-registry.svc:5000/$Namespace/invopt-api"
helm upgrade --install invopt-api (Join-Path $RepoRoot "helm/invopt-api") `
  --namespace $Namespace `
  --set image.repository=$apiImage `
  --set image.tag=$ImageTag `
  --set image.pullPolicy=Always `
  --set "config.MAXIMO_BASE_URL=$MaximoBaseUrl" `
  --set "config.LLM_PROVIDER=$LlmProvider" `
  --set "config.LLM_MODEL=$LlmModel" `
  --set "config.CORS_ORIGINS=https://invopt-ui-${Namespace}.apps.$( ($server -replace 'https://api\.','') -replace ':6443.*','')" `
  --wait --timeout 5m | Write-Host
Ok "invopt-api deployed"

# ── 6. Helm: UI ─────────────────────────────────────────────────────────────
Step "helm upgrade --install invopt-ui"
$uiImage = "image-registry.openshift-image-registry.svc:5000/$Namespace/invopt-ui"
helm upgrade --install invopt-ui (Join-Path $RepoRoot "helm/invopt-ui") `
  --namespace $Namespace `
  --set image.repository=$uiImage `
  --set image.tag=$ImageTag `
  --set image.pullPolicy=Always `
  --wait --timeout 5m | Write-Host
Ok "invopt-ui deployed"

# ── 7. Smoke-test info ──────────────────────────────────────────────────────
Step "Routes"
$apiHost = oc get route invopt-api -o jsonpath='{.spec.host}'
$uiHost  = oc get route invopt-ui  -o jsonpath='{.spec.host}'
Write-Host "  API : https://$apiHost"
Write-Host "  UI  : https://$uiHost"

Step "Smoke test"
Write-Host "  curl -s https://$apiHost/healthz"
Write-Host "  Open https://$uiHost in a browser and log in with your Maximo credentials."

Step "Done"
Write-Host "Pods:" -ForegroundColor Cyan
oc get pods -l 'app.kubernetes.io/name in (invopt-api,invopt-ui)' -o wide
