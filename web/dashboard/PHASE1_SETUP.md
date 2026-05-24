# Phase 1 — Setup Instructions

Run these commands from `web/dashboard/` after copying the source files.

## 1. Install additional runtime dependencies

```powershell
pnpm add react-router-dom @tanstack/react-query oidc-client-ts react-intl clsx msw @carbon/charts-react @carbon/charts
```

## 2. Install additional dev dependencies

```powershell
pnpm add -D @playwright/test @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

## 3. Add scripts to package.json

Add the following entries to the `"scripts"` block:

```json
{
  "test:e2e": "playwright test",
  "test:e2e:ui": "playwright test --ui",
  "msw:init": "msw init public/ --save"
}
```

## 4. Initialise MSW service worker

This copies `mockServiceWorker.js` into `public/` so the browser worker can be loaded:

```powershell
pnpm msw:init
```

## 5. Verify the dev server works

```powershell
$env:VITE_USE_MSW = "true"; pnpm dev
```

Visit http://localhost:5173 — you should see the Executive Dashboard with four KPI cards
populated from MSW fixture data.

## 6. Run unit tests

```powershell
pnpm test
```

Expected: all tests pass (KpiCard, KpiStrip, formatters).

## 7. Run E2E tests

```powershell
pnpm test:e2e
```

Playwright will start the dev server automatically and run the smoke tests.

## 8. Build for production

```powershell
pnpm build
```

## 9. Build the Docker image (from repo root)

```powershell
docker build `
  --build-arg VITE_API_BASE_URL=/v1 `
  --build-arg VITE_OIDC_AUTHORITY=https://your-idp `
  --build-arg VITE_OIDC_CLIENT_ID=invopt-ui `
  --build-arg VITE_OIDC_REDIRECT=https://invopt-ui.maspoc.apps.maspoc.zpih.p1.openshiftapps.com/login/callback `
  -t invopt-ui:dev .
```

## 10. Deploy to OpenShift (dev)

```bash
# Tag and push to internal registry
oc tag invopt-ui:dev masdev-inventory-opt/invopt-ui:dev

# Helm deploy
helm upgrade --install invopt-ui ./helm/invopt-ui \
  -f helm/invopt-ui/values.yaml \
  -f helm/invopt-ui/values-dev.yaml \
  -n masdev-inventory-opt
```

## File structure written by this session

```
web/dashboard/src/
├── types/index.ts                         # Cross-cutting TypeScript interfaces
├── lib/
│   ├── formatters.ts                      # Intl helpers (currency, %, date)
│   └── formatters.test.ts
├── theme/
│   └── tokens.scss                        # Carbon token overrides + domain colours
├── i18n/
│   ├── IntlProvider.tsx
│   └── messages/en-US.json
├── auth/
│   ├── oidc.ts                            # OIDC UserManager
│   ├── token.ts                           # getAccessToken helper
│   ├── AuthProvider.tsx                   # Context + MSW bypass
│   ├── RequireAuth.tsx                    # Route guard
│   └── OidcCallback.tsx                  # /login/callback handler
├── api/
│   ├── client.ts                          # Fetch wrapper
│   └── queries.ts                         # 5 TanStack Query hooks
├── test/
│   ├── handlers.ts                        # MSW handler fixtures
│   ├── browser.ts                         # MSW browser worker
│   ├── server.ts                          # MSW node server (Vitest)
│   └── setup.ts                           # Vitest global setup
├── components/
│   ├── PageHeader/
│   ├── KpiCard/                           # + KpiCard.test.tsx
│   ├── EmptyState/
│   └── ErrorState/
├── features/dashboard/
│   ├── KpiStrip/                          # + KpiStrip.test.tsx
│   ├── WorkingCapitalTrendChart/
│   ├── RecommendationsByStatusDonut/
│   ├── ForecastAccuracyTable/
│   └── TopItemsByReleaseTable/
├── routes/
│   ├── ExecutiveDashboard/
│   └── NotFound/
├── App.tsx                                # Root component with all providers
└── main.tsx                               # Entry point with MSW bootstrap

web/dashboard/
├── nginx.conf                             # nginx:unprivileged config (port 8080)
├── playwright.config.ts
└── e2e/exec_dashboard.spec.ts

Dockerfile                                 # Multi-stage build (node → nginx)
.dockerignore
helm/invopt-ui/
├── Chart.yaml
├── values.yaml
├── values-dev.yaml
└── templates/
    ├── _helpers.tpl
    ├── deployment.yaml
    ├── service.yaml
    └── route.yaml                         # OpenShift Route
```
