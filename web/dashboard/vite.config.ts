import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  return {
    plugins: [react(), visualizer({ filename: 'dist/stats.html', gzipSize: true })],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
        '@api': path.resolve(__dirname, 'src/api'),
        '@components': path.resolve(__dirname, 'src/components'),
        '@features': path.resolve(__dirname, 'src/features'),
        '@theme': path.resolve(__dirname, 'src/theme'),
        '@test': path.resolve(__dirname, 'src/test'),
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: `@use "@theme/tokens" as *;`,
        },
      },
    },
    server: {
      port: 5173,
      proxy:
        env.VITE_USE_MSW === 'true'
          ? undefined
          : {
              '/v1': { target: env.VITE_API_BASE_URL, changeOrigin: true, secure: false },
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
