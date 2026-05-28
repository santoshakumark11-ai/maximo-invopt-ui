<#
.SYNOPSIS
  Verifies that the LLM gateway is wired to a real provider (not the mock fallback).

.DESCRIPTION
  1. Logs into the API with your Maximo credentials.
  2. Calls /v1/diagnostics/llm with a known prompt.
  3. Prints the active driver, model, latency, and response.
  4. Exits with non-zero if the mock driver answered.

.PARAMETER ApiHost
  Base URL of the API.  Defaults to http://localhost:8000.

.PARAMETER MaximoUser
.PARAMETER MaximoApiKey
  Credentials for the /auth/login call.  Defaults to env vars MAXIMO_USER and MAXIMO_API_KEY.

.EXAMPLE
  .\scripts\check_llm.ps1 -MaximoUser MAXADMIN -MaximoApiKey abcdef...
#>

param(
  [string]$ApiHost      = "http://localhost:8000",
  [string]$MaximoUser   = $env:MAXIMO_USER,
  [string]$MaximoApiKey = $env:MAXIMO_API_KEY,
  [string]$Prompt       = "In one short sentence, state the formula for Economic Order Quantity."
)

if (-not $MaximoUser -or -not $MaximoApiKey) {
  Write-Host "Set -MaximoUser and -MaximoApiKey (or env MAXIMO_USER / MAXIMO_API_KEY)." -ForegroundColor Yellow
  exit 2
}

# ── 1. Login ────────────────────────────────────────────────────────────────
Write-Host "Logging in as $MaximoUser..." -ForegroundColor Cyan
try {
  $login = Invoke-RestMethod -Method Post -Uri "$ApiHost/auth/login" `
    -ContentType "application/json" `
    -Body (@{username=$MaximoUser; api_key=$MaximoApiKey} | ConvertTo-Json)
} catch {
  Write-Host "Login failed: $_" -ForegroundColor Red
  exit 3
}

$jwt = $login.access_token
if (-not $jwt) {
  Write-Host "No access_token in /auth/login response." -ForegroundColor Red
  exit 3
}
Write-Host "OK — JWT issued ($($jwt.Length) chars)" -ForegroundColor Green

# ── 2. Probe ────────────────────────────────────────────────────────────────
$headers = @{ Authorization = "Bearer $jwt" }
$encodedPrompt = [System.Web.HttpUtility]::UrlEncode($Prompt)
$probeUrl = "$ApiHost/v1/diagnostics/llm?prompt=$encodedPrompt"
Write-Host "Calling $probeUrl ..." -ForegroundColor Cyan

try {
  $probe = Invoke-RestMethod -Uri $probeUrl -Headers $headers
} catch {
  Write-Host "Probe failed: $_" -ForegroundColor Red
  exit 4
}

# ── 3. Report ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "─────────────────────────────────────────"   -ForegroundColor DarkGray
Write-Host "Configured provider : $($probe.configured_provider)"
Write-Host "Active driver       : $($probe.actual_driver)"
Write-Host "Model               : $($probe.model)"
Write-Host "Latency             : $($probe.elapsed_ms) ms"
Write-Host "─────────────────────────────────────────"   -ForegroundColor DarkGray
if ($probe.error)   { Write-Host "Error  : $($probe.error)"   -ForegroundColor Red }
if ($probe.warning) { Write-Host "Warning: $($probe.warning)" -ForegroundColor Yellow }
Write-Host ""
Write-Host "Response:" -ForegroundColor Cyan
Write-Host $probe.response
Write-Host ""

# ── 4. Exit code ────────────────────────────────────────────────────────────
if ($probe.actual_driver -eq "MockDriver" -and $probe.configured_provider -ne "mock") {
  Write-Host "FAIL — mock driver answered while LLM_PROVIDER='$($probe.configured_provider)'." -ForegroundColor Red
  Write-Host "       Check LLM_API_KEY (and LLM_ENDPOINT for azure_openai) in .env, then restart uvicorn." -ForegroundColor Yellow
  exit 1
}
if ($probe.error) {
  Write-Host "FAIL — driver returned an error." -ForegroundColor Red
  exit 1
}
Write-Host "PASS — LLM gateway is live." -ForegroundColor Green
exit 0
