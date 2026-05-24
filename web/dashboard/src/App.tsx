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
 *   /        -> ExecutiveDashboard  (protected)
 *   /login   -> Login               (public)
 *   *        -> NotFound            (public)
 */
import { lazy, Suspense, Component, type ReactNode, type ErrorInfo } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { IntlProvider } from '@/i18n/IntlProvider';
import { AuthProvider } from '@/auth/AuthProvider';
import { RequireAuth } from '@/auth/RequireAuth';

import { InlineLoading, InlineNotification } from '@carbon/react';

import './styles.scss';

// ---------------------------------------------------------------------------
// Lazy route pages
// ---------------------------------------------------------------------------
const ExecutiveDashboard = lazy(async () => {
  const m = await import('./routes/ExecutiveDashboard/ExecutiveDashboard');
  return { default: m.ExecutiveDashboard };
});

const Login = lazy(async () => {
  const m = await import('./routes/Login/Login');
  return { default: m.Login };
});

const NotFound = lazy(async () => {
  const m = await import('./routes/NotFound/NotFound');
  return { default: m.NotFound };
});

// ---------------------------------------------------------------------------
// Error boundary
// ---------------------------------------------------------------------------
interface EBState {
  error: Error | null;
}

class AppErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  state: EBState = { error: null };

  static getDerivedStateFromError(error: Error): EBState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[AppErrorBoundary]', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: '2rem' }}>
          <InlineNotification
            kind="error"
            title="Application failed to load"
            subtitle={this.state.error.message}
          />
          <p style={{ marginTop: '1rem', fontSize: '0.875rem', color: '#555' }}>
            Check the browser console for details. If packages are missing run:{' '}
            <code>
              pnpm add react-router-dom @tanstack/react-query react-intl clsx msw
              @carbon/charts-react @carbon/charts
            </code>
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// Query client
// ---------------------------------------------------------------------------
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppSuspenseFallback() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
      }}
    >
      <InlineLoading description="Loading..." status="active" />
    </div>
  );
}

export default function App() {
  return (
    <AppErrorBoundary>
      <IntlProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BrowserRouter
              future={{
                v7_startTransition: true,
                v7_relativeSplatPath: true,
              }}
            >
              <Suspense fallback={<AppSuspenseFallback />}>
                <Routes>
                  {/* Public */}
                  <Route path="/login" element={<Login />} />

                  {/* Protected */}
                  <Route
                    path="/"
                    element={
                      <RequireAuth>
                        <ExecutiveDashboard />
                      </RequireAuth>
                    }
                  />

                  {/* Fallback */}
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
