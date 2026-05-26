/**
 * App — root component.
 *
 * Wires together:
 *   - IntlProvider (i18n)
 *   - QueryClientProvider (TanStack Query)
 *   - AuthProvider (Maximo JWT login)
 *   - React Router routes
 *
 * Routes:
 *   /                            -> ExecutiveDashboard   (protected, in AppShell)
 *   /recommendations             -> Recommendations      (protected, in AppShell)
 *   /recommendations/:recId      -> RecommendationDetail (protected, in AppShell)
 *   /login                       -> Login                (public)
 *   *                            -> NotFound             (public)
 */
import { lazy, Suspense, Component, type ReactNode, type ErrorInfo } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { InlineLoading, InlineNotification } from '@carbon/react';

import { IntlProvider } from '@/i18n/IntlProvider';
import { AuthProvider } from '@/auth/AuthProvider';
import { RequireAuth } from '@/auth/RequireAuth';
import { AppShell } from '@/components/AppShell';

import './styles.scss';

// ─── Lazy route pages ─────────────────────────────────────────────────────────

const ExecutiveDashboard = lazy(async () => {
  const m = await import('./routes/ExecutiveDashboard/ExecutiveDashboard');
  return { default: m.ExecutiveDashboard };
});

const Recommendations = lazy(() => import('./routes/Recommendations'));

const RecommendationDetail = lazy(() => import('./routes/RecommendationDetail'));

const Login = lazy(async () => {
  const m = await import('./routes/Login/Login');
  return { default: m.Login };
});

const NotFound = lazy(async () => {
  const m = await import('./routes/NotFound/NotFound');
  return { default: m.NotFound };
});

// ─── Error boundary ───────────────────────────────────────────────────────────

interface EBState {
  error: Error | null;
}

class AppErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  override state: EBState = { error: null };

  static getDerivedStateFromError(error: Error): EBState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[AppErrorBoundary]', error, info);
  }

  override render() {
    if (this.state.error) {
      return (
        <div style={{ padding: '2rem' }}>
          <InlineNotification
            kind="error"
            title="Application failed to load"
            subtitle={this.state.error.message}
          />
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── Query client ─────────────────────────────────────────────────────────────

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

// ─── Suspense fallback ────────────────────────────────────────────────────────

function AppSuspenseFallback() {
  return (
    <div
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}
    >
      <InlineLoading description="Loading..." status="active" />
    </div>
  );
}

// ─── Protected shell ──────────────────────────────────────────────────────────

function ProtectedShell({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <AppErrorBoundary>
      <IntlProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BrowserRouter>
              <Suspense fallback={<AppSuspenseFallback />}>
                <Routes>
                  {/* Public */}
                  <Route path="/login" element={<Login />} />

                  {/* Protected — all share AppShell */}
                  <Route
                    path="/"
                    element={
                      <ProtectedShell>
                        <ExecutiveDashboard />
                      </ProtectedShell>
                    }
                  />
                  <Route
                    path="/recommendations"
                    element={
                      <ProtectedShell>
                        <Recommendations />
                      </ProtectedShell>
                    }
                  />
                  <Route
                    path="/recommendations/:recId"
                    element={
                      <ProtectedShell>
                        <RecommendationDetail />
                      </ProtectedShell>
                    }
                  />

                  {/* Catch-all */}
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </BrowserRouter>
          </AuthProvider>
        </QueryClientProvider>
      </IntlProvider>
    </AppErrorBoundary>
  );
}
