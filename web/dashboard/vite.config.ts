import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';
import { resolve } from 'node:path';

const __dirname = import.meta.dirname;

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  // VITE_API_BASE_URL can be a relative path ('/v1') in dev (used by client.ts)
  // or an absolute URL in production.  http-proxy requires an absolute URL, so
  // only use it as the proxy target when it actually starts with 'http'.
  const rawApiUrl = (env.VITE_API_BASE_URL ?? '').trim();
  const apiTarget: string = rawApiUrl.startsWith('http') ? rawApiUrl : 'http://localhost:8000';
  return {
    plugins: [react(), visualizer({ filename: 'dist/stats.html', gzipSize: true })],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        '@api': resolve(__dirname, 'src/api'),
        '@components': resolve(__dirname, 'src/components'),
        '@features': resolve(__dirname, 'src/features'),
        '@theme': resolve(__dirname, 'src/theme'),
        '@test': resolve(__dirname, 'src/test'),
        // Carbon's SCSS emits font URLs prefixed with '~@ibm/plex/...' — a
        // webpack-era convention for node_modules.  Vite would serve that path
        // literally (resulting in a 404/decode error).  This alias maps it to
        // the real node_modules location so fonts resolve correctly.
        '~@ibm': resolve(__dirname, 'node_modules/@ibm'),
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          silenceDeprecations: ['legacy-js-api'],
          // Allow SCSS files to use @use 'theme/tokens' without relative paths.
          // node_modules is also included so Carbon packages resolve correctly
          // when referenced transitively from CSS Modules via @use.
          loadPaths: [resolve(__dirname, 'src'), resolve(__dirname, 'node_modules')],
        },
      },
    },
    server: {
      port: 5173,
      proxy:
        env.VITE_USE_MSW === 'true'
          ? undefined
          : {
              '/v1': { target: apiTarget, changeOrigin: true, secure: false },
              '/auth': { target: apiTarget, changeOrigin: true, secure: false },
            },
    },
    build: {
      sourcemap: true,
      target: 'es2022',
      rollupOptions: {
        output: {
          manualChunks: {
            carbon: ['@carbon/react', '@carbon/icons-react'],
            charts: ['@carbon/charts-react'],
          },
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: true,
      // Only pick up tests inside src/ — exclude Playwright e2e specs
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      exclude: [
        'node_modules/**',
        'e2e/**',
        'dist/**',
        // Stale pre-migration tests superseded by src/components/KpiCard/KpiCard.test.tsx
        'src/features/executive/**',
      ],
      coverage: {
        reporter: ['text', 'html'],
        lines: 80,
        statements: 80,
        branches: 70,
        functions: 80,
      },
    },
  };
});
