import type {
  Session,
  Message,
  DashboardStats,
  AgentLog,
  DiagnosisResult,
  EvaluationReport,
  EvaluationCasesResponse,
  EvaluationStatus,
  EvaluationRunRequest,
  AgentStatus,
  ToolsListResponse,
} from '@/types/medichain';
import { mockSessions, mockMessages, mockDashboardStats, mockAgentLogs } from './mockData';

const BASE = '/api/v1';

// Mock-data fallback on API failure is gated behind VITE_USE_MOCK. Defaults to
// false so real backend errors surface in the UI instead of being silently
// replaced with fake sessions/messages. Set VITE_USE_MOCK=true in a local .env
// to restore the old behaviour while prototyping without a running backend.
const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? 'false') === 'true';

async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${BASE}${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    // M25 fix: include status code in error
    if (!res.ok) throw new Error(`API error (${res.status}): ${endpoint}`);
    return res.json();
  } catch (err) {
    // Re-throw API errors as-is, wrap network errors
    if (err instanceof Error && err.message.startsWith('API error')) throw err;
    throw new Error('Backend unavailable');
  }
}

// -- Sessions --
export async function getSessions(): Promise<Session[]> {
  try { return await apiFetch<Session[]>('/sessions/'); }
  catch (err) {
    if (USE_MOCK) { console.warn('API fallback to mock data: /sessions/'); return mockSessions; }
    throw err;
  }
}

export async function getSession(id: string): Promise<Session> {
  try { return await apiFetch<Session>(`/sessions/${id}`); }
  catch (err) {
    if (USE_MOCK) { console.warn(`API fallback to mock data: /sessions/${id}`); return mockSessions.find(s => s.id === id) ?? mockSessions[0]; }
    throw err;
  }
}

export async function createSession(title: string, llm_model = 'gpt-4'): Promise<Session> {
  return apiFetch<Session>('/sessions/', {
    method: 'POST',
    body: JSON.stringify({ title, llm_model }),
  });
}

export async function deleteSession(id: string): Promise<void> {
  await apiFetch(`/sessions/${id}`, { method: 'DELETE' });
}

// -- Diagnosis (restores DiagnosisPanel + DebateView on reload) --
export async function getDiagnosisResult(sessionId: string): Promise<DiagnosisResult | null> {
  try { return await apiFetch<DiagnosisResult | null>(`/sessions/${sessionId}/diagnosis`); }
  catch { return null; }
}

// -- Chat --
export async function getChatHistory(sessionId: string): Promise<Message[]> {
  try { return await apiFetch<Message[]>(`/chat/${sessionId}`); }
  catch (err) {
    if (USE_MOCK) { console.warn(`API fallback to mock data: /chat/${sessionId}`); return mockMessages.filter(m => m.session_id === sessionId); }
    throw err;
  }
}

// -- Dashboard --
export async function getDashboardStats(): Promise<DashboardStats> {
  try { return await apiFetch<DashboardStats>('/sessions/stats'); }
  catch (err) {
    if (USE_MOCK) { console.warn('API fallback to mock data: /sessions/stats'); return mockDashboardStats; }
    throw err;
  }
}

// -- Agent logs --
export async function getAgentLogs(sessionId: string): Promise<AgentLog[]> {
  try { return await apiFetch<AgentLog[]>(`/agents/logs/${sessionId}`); }
  catch (err) {
    if (USE_MOCK) { console.warn(`API fallback to mock data: /agents/logs/${sessionId}`); return mockAgentLogs.filter(l => l.session_id === sessionId); }
    throw err;
  }
}

// -- Agent system status --
export async function getAgentStatus(): Promise<AgentStatus> {
  return apiFetch<AgentStatus>('/agents/status');
}

// -- MCP Tools --
export async function getTools(): Promise<ToolsListResponse> {
  return apiFetch<ToolsListResponse>('/tools/');
}

export async function queryTool(tool_name: string, query: string): Promise<unknown> {
  return apiFetch('/tools/query', {
    method: 'POST',
    body: JSON.stringify({ tool_name, query }),
  });
}

// -- Evaluation Harness --
export async function getEvaluationLatest(): Promise<EvaluationReport> {
  return apiFetch<EvaluationReport>('/evaluation/latest');
}

export async function getEvaluationCases(): Promise<EvaluationCasesResponse> {
  return apiFetch<EvaluationCasesResponse>('/evaluation/cases');
}

export async function getEvaluationStatus(): Promise<EvaluationStatus> {
  return apiFetch<EvaluationStatus>('/evaluation/status');
}

export async function triggerEvaluation(req: EvaluationRunRequest = {}): Promise<{ status: string; started_at: string }> {
  return apiFetch('/evaluation/run', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}
