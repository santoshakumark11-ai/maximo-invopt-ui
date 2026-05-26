/**
 * AuthProvider — JWT-based auth context.
 *
 * The authentication flow:
 *   1. User submits the Login form → POST /auth/login with username + password.
 *   2. Backend validates credentials against Maximo OSLC whoami.
 *   3. Backend returns a signed JWT.
 *   4. We store the token in sessionStorage and update context.
 *   5. All API calls attach the token via Authorization: Bearer.
 *
 * When VITE_USE_MSW=true the provider injects a synthetic dev user so the
 * rest of the app can assume authentication during local development.
 */
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { saveSession, clearSession, getStoredToken, getStoredUser, type StoredUser } from './token';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AuthUser extends StoredUser {
  accessToken: string;
}

interface AuthContextValue {
  /** Authenticated user, or null when not signed in. */
  user: AuthUser | null;
  /** True while the login network request is in flight. */
  isLoading: boolean;
  /** Error message from the last failed login attempt, if any. */
  loginError: string | null;
  /** Submit username + personal Maximo API key; resolves true on success, false on failure. */
  login: (username: string, apiKey: string) => Promise<boolean>;
  /** Clear the session. */
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ─── MSW dev stub ─────────────────────────────────────────────────────────────

function makeDevUser(): AuthUser {
  return {
    username: 'DEVUSER',
    displayName: 'Dev User',
    groups: ['MAXEVERYONE'],
    accessToken: 'msw-dev-token',
  };
}

function hydrateFromStorage(): AuthUser | null {
  const token = getStoredToken();
  const stored = getStoredUser();
  if (!token || !stored) return null;
  return { ...stored, accessToken: token };
}

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const useMsw = import.meta.env.VITE_USE_MSW === 'true';

  const [user, setUser] = useState<AuthUser | null>(useMsw ? makeDevUser() : hydrateFromStorage());
  const [isLoading, setIsLoading] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const login = useCallback(
    async (username: string, apiKey: string): Promise<boolean> => {
      if (useMsw) {
        setUser(makeDevUser());
        return true;
      }

      setIsLoading(true);
      setLoginError(null);

      try {
        const resp = await fetch('/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, api_key: apiKey }),
        });

        if (!resp.ok) {
          const body = await resp.json().catch(() => ({}));
          // FastAPI 422s return detail as an array of Pydantic error objects
          const raw = (body as { detail?: unknown }).detail;
          const msg = Array.isArray(raw)
            ? (raw as Array<{ msg?: string }>).map((e) => e.msg ?? 'Unknown error').join('; ')
            : typeof raw === 'string'
              ? raw
              : 'Login failed';
          setLoginError(msg);
          return false;
        }

        const data = (await resp.json()) as {
          access_token: string;
          display_name: string;
          groups: string[];
        };

        const storedUser: StoredUser = {
          username: username.toUpperCase(),
          displayName: data.display_name,
          groups: data.groups,
        };

        saveSession(data.access_token, storedUser);

        setUser({ ...storedUser, accessToken: data.access_token });
        return true;
      } catch (_err) {
        setLoginError('Unable to reach the server. Please try again.');
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [useMsw]
  );

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
    setLoginError(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, loginError, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
