// vitest.workspace.ts
// Storybook's test addon originally added a browser test entry here that
// required @vitest/browser@3, which conflicts with vitest@1 in this project.
// Unit tests are configured in vite.config.ts (test: { environment: 'jsdom' }).
// Playwright covers real-browser E2E testing (see playwright.config.ts).
import { defineWorkspace } from 'vitest/config';

export default defineWorkspace(['vite.config.ts']);
