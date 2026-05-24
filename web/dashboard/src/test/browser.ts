/**
 * MSW browser worker — used when VITE_USE_MSW=true (local dev / demo).
 */
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
