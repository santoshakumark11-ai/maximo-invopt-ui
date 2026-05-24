/**
 * Application entry point.
 *
 * When VITE_USE_MSW=true the MSW service worker is started before React
 * mounts, so all API requests are intercepted from the very first render.
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

async function enableMocking() {
  if (import.meta.env.VITE_USE_MSW !== 'true') return;
  const { worker } = await import('./test/browser');
  return worker.start({
    onUnhandledRequest: 'warn',
  });
}

enableMocking().then(() => {
  const root = document.getElementById('root');
  if (!root) throw new Error('Root element #root not found in index.html');

  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
});
