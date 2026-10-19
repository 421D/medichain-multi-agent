/**
 * Tests for the api fetch wrapper.
 *
 * Covers:
 *   - happy path: fetch resolves, JSON returned to caller
 *   - sad path: non-2xx response surfaces "API error (status): endpoint"
 *   - sad path: network error surfaces "Backend unavailable"
 *   - createSession / queryTool POST bodies are stringified correctly
 *   - VITE_USE_MOCK off: getSessions rethrows on backend failure
 *
 * Mock fallback (VITE_USE_MOCK=true) is intentionally not toggled here —
 * `import.meta.env` is frozen at module load, so behavioural tests for that
 * branch live as a manual QA item in INSTALL.md § 4.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

import {
  createSession,
  deleteSession,
  getSessions,
  queryTool,
} from './api';

const okJson = (data: unknown) =>
  Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(data) }) as unknown as Promise<Response>;

const httpError = (status: number) =>
  Promise.resolve({ ok: false, status, json: () => Promise.resolve({}) }) as unknown as Promise<Response>;

describe('api fetch wrapper', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('happy: getSessions returns parsed JSON when backend responds 200', async () => {
    const sessions = [{ id: 'a', title: 'Test', status: 'active', llm_model: 'kimi', created_at: '2026-04-28' }];
    const fetchMock = vi.fn().mockReturnValue(okJson(sessions));
    vi.stubGlobal('fetch', fetchMock);

    const result = await getSessions();

    expect(result).toEqual(sessions);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/sessions/',
      expect.objectContaining({ headers: { 'Content-Type': 'application/json' } }),
    );
  });

  it('sad: 4xx surfaces a typed API error including the status code', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(httpError(404)));

    await expect(getSessions()).rejects.toThrow(/API error \(404\)/);
  });

  it('sad: network failure surfaces "Backend unavailable"', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    await expect(getSessions()).rejects.toThrow(/Backend unavailable/);
  });

  it('createSession POSTs a JSON body with title and llm_model', async () => {
    const created = { id: 'new', title: 'Hello', status: 'active', llm_model: 'kimi', created_at: '2026-04-28' };
    const fetchMock = vi.fn().mockReturnValue(okJson(created));
    vi.stubGlobal('fetch', fetchMock);

    await createSession('Hello', 'kimi');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ title: 'Hello', llm_model: 'kimi' });
  });

  it('deleteSession issues DELETE without a body', async () => {
    const fetchMock = vi.fn().mockReturnValue(okJson({}));
    vi.stubGlobal('fetch', fetchMock);

    await deleteSession('abc');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/sessions/abc',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('queryTool POSTs tool_name and query as JSON', async () => {
    const fetchMock = vi.fn().mockReturnValue(okJson({ results: [] }));
    vi.stubGlobal('fetch', fetchMock);

    await queryTool('pubmed_search', 'meningitis');

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ tool_name: 'pubmed_search', query: 'meningitis' });
  });
});
