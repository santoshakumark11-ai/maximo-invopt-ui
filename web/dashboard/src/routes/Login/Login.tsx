/**
 * Login page — Maximo username + personal API key form.
 *
 * MAS 9.1 only supports API-key authentication for REST.
 * Users generate their key in Maximo → Security → API Keys.
 *
 * On success the user is redirected to the page they originally tried to visit
 * (stored in router location.state.from) or "/" by default.
 */
import { useState, type FormEvent } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { TextInput, PasswordInput, Button, InlineNotification, Tile } from '@carbon/react';
import { useAuth } from '@/auth/AuthProvider';
import styles from './Login.module.scss';

export function Login() {
  const { login, isLoading, loginError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/';

  const [username, setUsername] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (!username.trim()) {
      setLocalError('Username is required.');
      return;
    }
    if (!apiKey.trim()) {
      setLocalError('API key is required.');
      return;
    }

    const ok = await login(username.trim(), apiKey.trim());
    if (ok) {
      navigate(from, { replace: true });
    }
    // On failure loginError is set by AuthProvider
  };

  const errorMessage = localError ?? loginError;

  return (
    <div className={styles.page}>
      <Tile className={styles.card ?? ''}>
        {/* Logo / header */}
        <div className={styles.header}>
          <h1 className={styles.title}>Inventory Optimisation</h1>
          <p className={styles.subtitle}>Sign in with your Maximo username and API key</p>
        </div>

        {/* Error notification */}
        {errorMessage && (
          <InlineNotification
            kind="error"
            title="Sign-in failed"
            subtitle={errorMessage}
            hideCloseButton
            className={styles.notification ?? ''}
          />
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate>
          <TextInput
            id="login-username"
            labelText="Username"
            placeholder="MAXIMO_USER"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={isLoading}
            className={styles.field ?? ''}
          />

          <PasswordInput
            id="login-api-key"
            labelText="API Key"
            helperText="Generate your key in Maximo → Security → API Keys"
            placeholder="••••••••••••••••"
            autoComplete="current-password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            disabled={isLoading}
            className={styles.field ?? ''}
          />

          <Button type="submit" disabled={isLoading} className={styles.submit}>
            {isLoading ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </Tile>
    </div>
  );
}
