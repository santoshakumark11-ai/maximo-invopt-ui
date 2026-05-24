/**
 * OidcCallback — redirects to home.
 *
 * OIDC is no longer used.  This component exists so any bookmarked or cached
 * /login/callback URLs don't 404 — they just bounce to the dashboard.
 *
 * @deprecated Safe to delete once the /login/callback route is removed.
 */
import { Navigate } from 'react-router-dom';

export function OidcCallback() {
  return <Navigate to="/" replace />;
}
