/**
 * RequireAuth — route guard component.
 *
 * - While a session exists: renders children.
 * - If no session: redirects to /login (preserving the intended destination
 *   in location state so the login page can redirect back after success).
 */
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider';
import { InlineLoading } from '@carbon/react';

interface RequireAuthProps {
  children: React.ReactNode;
}

export function RequireAuth({ children }: RequireAuthProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
        }}
      >
        <InlineLoading description="Signing you in…" status="active" />
      </div>
    );
  }

  if (!user) {
    // Preserve the attempted URL so we can redirect back after login
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
