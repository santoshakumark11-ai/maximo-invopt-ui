/**
 * Vitest global test setup.
 *
 * - Starts the MSW Node server before all tests.
 * - Resets handlers after each test to avoid state leaking between suites.
 * - Closes the server after all tests.
 */
import '@testing-library/jest-dom';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { server } from './server';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
