/**
 * Lightweight fetch wrapper shared by all query hooks.
 *
 * - Attaches the Bearer token from the auth layer.
 * - Throws a typed HttpError on non-2xx responses.
 * - Respects VITE_API_BASE_URL for the base path.
 */
import { getAccessToken } from '@/auth/token';
import type { ApiError } from '@/types';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) ?? '/v1';

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: ApiError
  ) {
    super(`HTTP ${status}: ${body.message}`);
    this.name = 'HttpError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let body: ApiError;
    try {
      body = (await response.json()) as ApiError;
    } catch {
      body = { code: 'UNKNOWN', message: response.statusText };
    }
    throw new HttpError(response.status, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
