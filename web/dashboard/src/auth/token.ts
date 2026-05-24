/**
 * Token persistence helpers.
 *
 * The JWT issued by POST /auth/login is stored in sessionStorage so it is
 * cleared automatically when the browser tab is closed.  We also store a
 * minimal user profile alongside the token so components can read username /
 * display-name without decoding the JWT themselves.
 *
 * When VITE_USE_MSW=true we return a fixed dev token and never touch storage.
 */

const TOKEN_KEY = 'invopt.access_token';
const USER_KEY = 'invopt.user';

const MSW_TOKEN = 'msw-dev-token';

export interface StoredUser {
  username: string;
  displayName: string;
  groups: string[];
}

// ── Write ─────────────────────────────────────────────────────────────────────

export function saveSession(token: string, user: StoredUser): void {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

// ── Read ──────────────────────────────────────────────────────────────────────

export function getStoredToken(): string | null {
  if (import.meta.env.VITE_USE_MSW === 'true') return MSW_TOKEN;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): StoredUser | null {
  if (import.meta.env.VITE_USE_MSW === 'true') {
    return { username: 'DEVUSER', displayName: 'Dev User', groups: ['MAXEVERYONE'] };
  }
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

/**
 * Returns a valid Bearer token for the current session.
 * Throws if the user is not authenticated (and MSW is disabled).
 */
export function getAccessToken(): string {
  const token = getStoredToken();
  if (!token) throw new Error('Not authenticated — no token in session storage.');
  return token;
}
