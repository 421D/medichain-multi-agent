/**
 * SessionDetail — MediChain Design System port.
 *
 * Two-panel layout:
 *   - LEFT:  chat + safety banner + composer (textarea, Enter submits)
 *   - RIGHT: 5-tab inspector → Agents / MCP / Dx / Patient / Meta
 *
 * Data flow preserved from prior implementation:
 *   - useWebSocket feeds `agent_transition`, `agent_reasoning`, `agent_message`,
 *     `llm_token` (typewriter), `debate_challenge`, `debate_response`,
 *     `diagnosis_result`.
 *   - Initial load pulls message history, agent logs, and any persisted
 *     diagnosis from the REST API so a refreshed tab rehydrates fully.
 *
 * The design's richer mock data (patient vitals, MCP tool cards,
 * replay scrubber) isn't fully backed by the current API yet, so tabs
 * gracefully degrade when that data isn't present — we surface real
 * agent_log entries instead of inventing vitals.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import {
  getSession, getChatHistory, getAgentLogs, getDiagnosisResult,
} from '@/services/api';
import { useWebSocket } from '@/hooks/useWebSocket';
import type {
  Session, Message, AgentLog, DiagnosisResult, DebateRound,
  DebateOutcome, DebateChallenge, DebateResponse, CDSSScore,
} from '@/types/medichain';
import {
  AGENTS, AgentPill, AgentBubble, UserBubble, Badge, Button,
  Card, DxRow, MetricTile, SafetyBanner, SafetyCallout,
  TimelineItem, resolveAgent, safetyFromFlag,
  Activity, AlertTriangle, ArrowRight, Check, Clock, MessageSquare,
  Send, Shield, Sparkles, Stethoscope, Target, Trash2,
  Wrench, X, Workflow,
} from '@/components/medichain/primitives';

// ─────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────

function safeFormatTime(raw?: string | null, fmt = 'h:mm:ss a'): string {
  if (!raw) return '';
  try {
    const d = new Date(raw);
    if (isNaN(d.getTime())) return '';
    return format(d, fmt);
  } catch { return ''; }
}

function escapeHtml(t: string): string {
  return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatBubble(text: string): string {
  return escapeHtml(text).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br/>');
}

// ─────────────────────────────────────────────────────────────────────
// Critic challenge in-line card (dramatic interruption)
// ─────────────────────────────────────────────────────────────────────

function CriticChallengeCard({ challenge, response }: { challenge: DebateChallenge; response?: DebateResponse }) {
  const [open, setOpen] = useState(true);
  const action = response?.action;
  const resolutionColor = action === 'accept' ? '#4ADE80' : action === 'partially_accept' ? '#FBBF24' : action === 'refute' ? '#F87171' : 'var(--fg-2)';
  const resolutionLabel = action === 'accept' ? '✓ Accepted'
    : action === 'partially_accept' ? '◐ Partial'
    : action === 'refute' ? 'Refuted'
    : '⋯ Awaiting response';
  return (
    <div className="critic-callout anim-in">
      <div className="critic-callout-header" onClick={() => setOpen(o => !o)}>
        <div className="hstack gap-sm">
          <span className="critic-pulse" />
          <AgentPill kind="critic" />
          <span className="text-xs mono muted">challenge · {challenge.type}</span>
        </div>
        <span className="mono text-xs" style={{ color: resolutionColor }}>{resolutionLabel}</span>
      </div>
      {open && (
        <div className="critic-callout-body">
          <div className="critic-section">
            <div className="eyebrow">Claim</div>
            <div className="text-sm" style={{ color: 'var(--fg-1)' }}>{challenge.claim}</div>
          </div>
          {challenge.evidence && challenge.evidence.length > 0 && (
            <div className="critic-section">
              <div className="eyebrow">Evidence</div>
              <ul className="critic-list">{challenge.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
            </div>
          )}
          {challenge.suggested_action && (
            <div className="critic-section">
              <div className="eyebrow">Suggested action</div>
              <div className="text-sm" style={{ color: 'var(--fg-1)' }}>{challenge.suggested_action}</div>
            </div>
          )}
          {response && (
            <div className="critic-section" style={{ borderTop: '1px dashed var(--border)', paddingTop: 10, marginTop: 10 }}>
              <div className="eyebrow">Diagnostician response</div>
              <div className="text-sm" style={{ color: 'var(--fg-1)' }}>{response.reasoning}</div>
              {response.evidence && response.evidence.length > 0 && (
                <ul className="critic-list" style={{ marginTop: 6 }}>
                  {response.evidence.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Tab content renderers
// ─────────────────────────────────────────────────────────────────────

type TabKey = 'agents' | 'mcp' | 'dx' | 'patient' | 'meta';

function AgentsTab({ logs, onSelect, selected }: { logs: AgentLog[]; onSelect: (id: string) => void; selected: string | null }) {
  if (logs.length === 0) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <div className="empty-icon"><Activity size={20} style={{ color: 'var(--fg-3)' }} /></div>
        <div className="text-md fw-500" style={{ marginBottom: 4 }}>No agent activity yet</div>
        <div className="sub">Events will stream in as agents work.</div>
      </div>
    );
  }
  return (
    <div className="vstack" style={{ gap: 14 }}>
      <div className="eyebrow">Agent turn · {logs.length} events · click to inspect</div>
      <div className="vstack" style={{ gap: 6 }}>
        {logs.map(log => {
          const a = AGENTS[resolveAgent(log.agent)];
          const active = log.id === selected;
          return (
            <div
              key={log.id}
              onClick={() => onSelect(log.id)}
              className="turn-row"
              style={{
                background: active ? 'var(--bg-3)' : 'var(--bg-2)',
                borderColor: active ? a.color : 'var(--border)',
                boxShadow: active ? `inset 3px 0 0 ${a.color}` : 'none',
              }}
            >
              <span className="turn-dot" style={{ background: a.color }} />
              <span className="turn-name" style={{ color: a.color }}>{a.name}</span>
              <span className="turn-evt">{log.event_type}</span>
              <span className="turn-headline">{log.content || '(no content)'}</span>
              <span className="turn-ms mono">{safeFormatTime(log.timestamp, 'HH:mm:ss')}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function McpTab({ logs }: { logs: AgentLog[] }) {
  // Derive: which agents participated, and summarise
  const byAgent = useMemo(() => {
    const map: Record<string, number> = {};
    for (const l of logs) map[l.agent] = (map[l.agent] ?? 0) + 1;
    return map;
  }, [logs]);

  return (
    <div className="vstack" style={{ gap: 14 }}>
      <div className="mcp-summary">
        <div className="mcp-summary-item">
          <div className="mcp-summary-val">{Object.values(byAgent).reduce((a, b) => a + b, 0)}</div>
          <div className="mcp-summary-lbl">Events</div>
        </div>
        <div className="mcp-summary-item">
          <div className="mcp-summary-val">{Object.keys(byAgent).length}</div>
          <div className="mcp-summary-lbl">Agents</div>
        </div>
        <div className="mcp-summary-item">
          <div className="mcp-summary-val mono">—</div>
          <div className="mcp-summary-lbl">Tool calls</div>
        </div>
        <div className="mcp-summary-item">
          <div className="mcp-summary-val" style={{ color: '#4ADE80' }}>OK</div>
          <div className="mcp-summary-lbl">Status</div>
        </div>
      </div>
      <div className="eyebrow">Available MCP tools</div>
      <div className="vstack" style={{ gap: 10 }}>
        {[
          { tool: 'pubmed_search',   server: 'research', purpose: 'Find medical literature relevant to the differential.' },
          { tool: 'drugbank_lookup', server: 'research', purpose: 'Check drug interactions via OpenFDA.' },
          { tool: 'icd11_lookup',    server: 'research', purpose: 'Look up WHO ICD-11 diagnosis codes.' },
          { tool: 'wells_score',     server: 'cdss',     purpose: 'PE risk scoring (Wells 2000).' },
          { tool: 'curb65',          server: 'cdss',     purpose: 'Pneumonia severity (CURB-65).' },
          { tool: 'heart_score',     server: 'cdss',     purpose: 'Chest pain / ACS risk.' },
          { tool: 'qsofa',           server: 'cdss',     purpose: 'Sepsis screening.' },
          { tool: 'cha2ds2_vasc',    server: 'cdss',     purpose: 'AF stroke risk.' },
          { tool: 'phq9',            server: 'cdss',     purpose: 'Depression severity screening.' },
        ].map(c => {
          const srvColor = c.server === 'cdss' ? '#22D3EE' : '#F472B6';
          return (
            <div key={c.tool} className="mcp-card">
              <div className="mcp-card-head" style={{ borderBottom: 'none', paddingBottom: 0, marginBottom: 0 }}>
                <span className="mcp-card-idx mono">{c.tool}</span>
                <div className="grow" style={{ minWidth: 0 }}>
                  <div className="hstack gap-sm" style={{ flexWrap: 'wrap' }}>
                    <span className="mcp-srv-pill" style={{ background: srvColor + '22', color: srvColor, borderColor: srvColor + '55' }}>
                      <Wrench size={9} /> {c.server}
                    </span>
                    <span className="text-xs muted">{c.purpose}</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DxTab({ diagnosis }: { diagnosis: DiagnosisResult | null }) {
  if (!diagnosis) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <div className="empty-icon"><Stethoscope size={20} style={{ color: 'var(--fg-3)' }} /></div>
        <div className="text-md fw-500" style={{ marginBottom: 4 }}>Waiting on diagnosis</div>
        <div className="sub">The Diagnostician will post a ranked differential once history is complete.</div>
      </div>
    );
  }
  const ddx = diagnosis.differential_diagnosis ?? [];
  const safety = safetyFromFlag(diagnosis.critic_review?.safety_flag ?? undefined);
  return (
    <div className="vstack" style={{ gap: 12 }}>
      <div className="eyebrow">Differential · {ddx.length} conditions</div>
      <div className="vstack" style={{ gap: 8 }}>
        {ddx.map((d, i) => (
          <DxDetailRow key={i} rank={i + 1} entry={d} />
        ))}
      </div>
      {diagnosis.cdss_scores && diagnosis.cdss_scores.length > 0 && (
        <>
          <div className="eyebrow" style={{ marginTop: 4 }}>Clinical scoring (CDSS)</div>
          <div className="grid grid-2" style={{ gap: 8 }}>
            {diagnosis.cdss_scores.map((s, i) => <CdssScoreCard key={i} score={s} />)}
          </div>
        </>
      )}
      <div style={{ height: 4 }} />
      <SafetyCallout
        level={safety}
        title={safety === 'urgent' ? 'Urgent care now' : safety === 'caution' ? 'Same-day / follow-up' : 'Safe — home care'}
      >
        {diagnosis.critic_review?.final_assessment ?? 'No critic review yet.'}
      </SafetyCallout>
    </div>
  );
}

function DxDetailRow({ rank, entry }: { rank: number; entry: NonNullable<DiagnosisResult['differential_diagnosis']>[number] }) {
  const [open, setOpen] = useState(false);
  const hue = entry.confidence >= 70 ? 150 : entry.confidence >= 40 ? 38 : 0;
  const bar = `hsl(${hue} 70% 55%)`;
  return (
    <div className="ddx-detail">
      <div className="ddx-row-summary" onClick={() => setOpen(o => !o)}>
        <span className="ddx-rank mono">#{rank}</span>
        <div className="grow" style={{ minWidth: 0 }}>
          <div className="fw-500 text-sm">{entry.diagnosis}</div>
          {entry.source && <div className="text-xs muted">source: {entry.source}</div>}
        </div>
        <div className="ddx-bar-wrap">
          <div className="ddx-bar-fill" style={{ width: `${entry.confidence}%`, background: bar }} />
        </div>
        <span className="mono text-xs" style={{ minWidth: 36, textAlign: 'right', color: bar }}>{entry.confidence}%</span>
      </div>
      {open && (
        <div className="ddx-detail-body">
          {entry.supporting_evidence?.length > 0 && (
            <div className="critic-section">
              <div className="eyebrow" style={{ color: '#4ADE80' }}>Supporting</div>
              <ul className="critic-list">{entry.supporting_evidence.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </div>
          )}
          {entry.against_evidence?.length > 0 && (
            <div className="critic-section">
              <div className="eyebrow" style={{ color: '#F87171' }}>Against</div>
              <ul className="critic-list">{entry.against_evidence.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CdssScoreCard({ score }: { score: CDSSScore }) {
  const riskMap: Record<string, { bg: string; border: string; text: string }> = {
    low:      { bg: 'rgba(34,197,94,.08)',  border: 'rgba(34,197,94,.35)',  text: '#4ADE80' },
    moderate: { bg: 'rgba(245,158,11,.08)', border: 'rgba(245,158,11,.35)', text: '#FBBF24' },
    high:     { bg: 'rgba(249,115,22,.08)', border: 'rgba(249,115,22,.35)', text: '#FB923C' },
    critical: { bg: 'rgba(220,38,38,.08)',  border: 'rgba(220,38,38,.35)',  text: '#F87171' },
  };
  const c = riskMap[score.risk_level] ?? riskMap.moderate;
  return (
    <div style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: 8, padding: 10 }}>
      <div className="hstack" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
        <span className="text-xs fw-600">{score.tool_name}</span>
        <span className="mono text-xs" style={{ color: c.text }}>{score.risk_level.toUpperCase()}</span>
      </div>
      <div className="fw-700 mono" style={{ fontSize: 18, color: c.text }}>
        {score.score}{score.max_score != null && <span className="text-xs muted"> / {score.max_score}</span>}
      </div>
      {score.recommendation && <div className="text-xs" style={{ color: 'var(--fg-2)', marginTop: 4, lineHeight: 1.4 }}>{score.recommendation}</div>}
    </div>
  );
}

function PatientTab({ messages, session }: { messages: Message[]; session: Session | null }) {
  // Best-effort synthesis from available data — first user message tends to
  // contain the chief complaint; we don't yet expose full patient_history.
  const firstUser = messages.find(m => m.role === 'user');
  const chief = firstUser?.content?.slice(0, 120) || session?.title || 'Not captured yet.';
  return (
    <div className="vstack" style={{ gap: 12 }}>
      <div className="eyebrow">Patient snapshot</div>
      <div className="patient-header">
        <div className="patient-avatar">—</div>
        <div>
          <div className="fw-500 text-sm">Patient context</div>
          <div className="text-xs muted">as captured during intake</div>
        </div>
      </div>
      <div>
        <div className="eyebrow" style={{ marginBottom: 6 }}>Chief complaint</div>
        <div className="text-sm" style={{ color: 'var(--fg-1)', lineHeight: 1.55 }}>{chief}</div>
      </div>
      <div className="text-xs muted" style={{ paddingTop: 8, borderTop: '1px dashed var(--border)' }}>
        Structured vitals, meds, allergies and family history are surfaced once the Interviewer's SOCRATES pass is complete and published to the server state.
      </div>
    </div>
  );
}

function MetaTab({ session, diagnosis, messages, logs }: {
  session: Session | null; diagnosis: DiagnosisResult | null;
  messages: Message[]; logs: AgentLog[];
}) {
  const rows: Array<[string, string]> = [
    ['Session ID',      session?.id ?? '—'],
    ['Title',           session?.title ?? '—'],
    ['Status',          session?.status ?? '—'],
    ['Model',           session?.llm_model ?? '—'],
    ['Started',         safeFormatTime(session?.created_at, 'MMM d, yyyy · h:mm a')],
    ['Messages',        String(messages.length)],
    ['Agent events',    String(logs.length)],
    ['Debate rounds',   String(diagnosis?.debate_outcome?.rounds?.length ?? 0)],
    ['Challenges',      String(diagnosis?.debate_outcome?.total_challenges ?? 0)],
    ['Accepted',        String(diagnosis?.debate_outcome?.accepted ?? 0)],
    ['Refuted',         String(diagnosis?.debate_outcome?.refuted ?? 0)],
    ['Final verdict',   diagnosis?.debate_outcome?.final_verdict ?? '—'],
    ['Safety flag',     diagnosis?.critic_review?.safety_flag ?? '—'],
  ];
  return (
    <div className="vstack" style={{ gap: 10 }}>
      <div className="eyebrow">Session metadata</div>
      {rows.map(([k, v]) => (
        <div key={k} className="hstack" style={{ justifyContent: 'space-between', borderBottom: '1px solid var(--border-soft)', paddingBottom: 6, fontSize: 12 }}>
          <span className="muted">{k}</span>
          <span className="mono" style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v}</span>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────

export default function SessionDetail() {
  const { sessionId: rawSessionId } = useParams<{ sessionId: string }>();
  const sessionId = rawSessionId ?? '';
  const navigate = useNavigate();

  const [session, setSession] = useState<Session | null>(null);
  // Track whether getSession returned 404 / network error, so we can render
  // a real "not found" state instead of an indefinite "Loading..." spinner.
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [diagnosis, setDiagnosis] = useState<DiagnosisResult | null>(null);
  const [_debateOutcome, setDebateOutcome] = useState<DebateOutcome | null>(null);
  const [liveRounds, setLiveRounds] = useState<DebateRound[]>([]);
  const [streaming, setStreaming] = useState<{ agent: string; content: string } | null>(null);
  const [input, setInput] = useState('');
  const [tab, setTab] = useState<TabKey>('agents');
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const processedSeqRef = useRef(0);
  const idCounter = useRef(0);
  const nextId = () => String(++idCounter.current);

  const { events, isConnected, sendMessage } = useWebSocket(sessionId);

  useEffect(() => {
    if (!sessionId) return;
    setSessionError(null);
    getSession(sessionId)
      .then(s => { setSession(s); setSessionError(null); })
      .catch(err => setSessionError(err instanceof Error ? err.message : 'Session not found'));
    getChatHistory(sessionId).then(setMessages).catch(() => {});
    getAgentLogs(sessionId).then(setLogs).catch(() => {});
    getDiagnosisResult(sessionId).then(d => {
      if (!d) return;
      setDiagnosis(d);
      if (d.debate_outcome) {
        setDebateOutcome(d.debate_outcome);
        if (d.debate_outcome.rounds?.length) setLiveRounds(d.debate_outcome.rounds);
      }
    }).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streaming]);

  // Consume WebSocket events by monotonic _seq so internal ring-buffer
  // trims never cause us to skip a batch.
  useEffect(() => {
    if (!sessionId || events.length === 0) return;
    let maxSeen = processedSeqRef.current;
    for (const ev of events) {
      if (ev._seq <= processedSeqRef.current) continue;
      if (ev._seq > maxSeen) maxSeen = ev._seq;

      if (ev.type === 'agent_message' && ev.content) {
        setMessages(prev => [...prev, {
          id: `ws-${nextId()}`,
          session_id: sessionId,
          role: 'assistant',
          agent: ev.agent,
          content: ev.content!,
          timestamp: new Date().toISOString(),
        }]);
        if (streaming && ev.agent === streaming.agent) setStreaming(null);
      }

      if (ev.type === 'llm_token' && ev.content && ev.agent) {
        const agent = ev.agent;
        const token = ev.content;
        setStreaming(prev => prev && prev.agent === agent
          ? { agent, content: prev.content + token }
          : { agent, content: token });
      }

      if ((ev.type === 'agent_transition' || ev.type === 'agent_reasoning') && ev.content) {
        setLogs(prev => [...prev, {
          id: `ws-log-${nextId()}`,
          session_id: sessionId,
          agent: ev.agent!,
          event_type: ev.type === 'agent_transition' ? 'transition' : 'reasoning',
          content: ev.content!,
          timestamp: new Date().toISOString(),
          completed: true,
        }]);
      }

      if (ev.type === 'diagnosis_result' && ev.data) {
        const d = ev.data as unknown as DiagnosisResult;
        setDiagnosis(d);
        if (d.debate_outcome) {
          setDebateOutcome(d.debate_outcome);
        }
      }

      if (ev.type === 'debate_challenge' && ev.data) {
        const ch = ev.data as unknown as DebateChallenge;
        const nowIso = new Date().toISOString();
        setLiveRounds(prev => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (!last || last.resolution !== 'pending') {
            copy.push({
              round_number: copy.length + 1,
              challenges: [ch],
              responses: [],
              resolution: 'pending',
              _createdAt: nowIso,
            } as DebateRound & { _createdAt: string });
          } else {
            copy[copy.length - 1] = { ...last, challenges: [...last.challenges, ch] };
          }
          return copy;
        });
      }

      if (ev.type === 'debate_response' && ev.data) {
        const r = ev.data as unknown as DebateResponse;
        setLiveRounds(prev => {
          if (prev.length === 0) return prev;
          const copy = [...prev];
          const last = { ...copy[copy.length - 1] };
          last.responses = [...last.responses, r];
          if (last.responses.length >= last.challenges.length) last.resolution = 'resolved';
          copy[copy.length - 1] = last;
          return copy;
        });
      }
    }
    processedSeqRef.current = maxSeen;
  }, [events, sessionId, streaming]);

  // Rules of Hooks: this useMemo MUST run every render. The early-return
  // guards for !rawSessionId / sessionError sit BELOW, so the hook order
  // stays consistent whether we bail out or render the full chat.
  // Merge live debate rounds into the flat chat stream so the dramatic
  // critic callout renders inline with the conversation. Items are merge-sorted
  // by timestamp — messages use their own `timestamp`, debate rounds use
  // `_createdAt` (stamped when the round's first challenge arrives). Without
  // this, debate cards were always appended after all messages regardless of
  // when they actually happened.
  const renderedChat = useMemo(() => {
    type Entry =
      | { type: 'msg'; msg: Message; ts: number }
      | { type: 'challenge'; ch: DebateChallenge; resp?: DebateResponse; round: number; ts: number };
    const out: Entry[] = [];
    for (const m of messages) {
      const ts = m.timestamp ? Date.parse(m.timestamp) : 0;
      out.push({ type: 'msg', msg: m, ts: Number.isNaN(ts) ? 0 : ts });
    }
    for (const round of liveRounds) {
      const rr = round as DebateRound & { _createdAt?: string };
      const rawTs = rr._createdAt ? Date.parse(rr._createdAt) : NaN;
      const ts = Number.isNaN(rawTs) ? Date.now() : rawTs;
      for (let i = 0; i < round.challenges.length; i++) {
        // Keep challenges within a round clustered by adding a tiny offset
        // per index so their relative order is preserved under stable sort.
        out.push({
          type: 'challenge',
          ch: round.challenges[i],
          resp: round.responses[i],
          round: round.round_number,
          ts: ts + i,
        });
      }
    }
    out.sort((a, b) => a.ts - b.ts);
    return out;
  }, [messages, liveRounds]);

  // Post-hook early returns (safe now — all hooks above have registered).
  if (!rawSessionId) return null;
  if (sessionError) {
    return (
      <div className="page">
        <div className="card" style={{ padding: 32, textAlign: 'center', maxWidth: 520, margin: '48px auto' }}>
          <div className="empty-icon"><AlertTriangle size={20} style={{ color: 'var(--danger-bright)' }} /></div>
          <div className="text-lg fw-600" style={{ marginBottom: 6 }}>Session not found</div>
          <div className="sub" style={{ marginBottom: 16 }}>
            {sessionError} · The session id <span className="mono">{sessionId.slice(0, 8)}</span> isn't in the database.
          </div>
          <Button variant="primary" onClick={() => navigate('/consultations')}>Back to Consultations</Button>
        </div>
      </div>
    );
  }

  const handleSend = () => {
    const v = input.trim();
    if (!v || !isConnected) return;
    setMessages(prev => [...prev, {
      id: `user-${nextId()}`,
      session_id: sessionId,
      role: 'user',
      content: v,
      timestamp: new Date().toISOString(),
    }]);
    sendMessage(v);
    setInput('');
  };

  const safety = safetyFromFlag(diagnosis?.critic_review?.safety_flag);
  const safetyTitle = safety === 'urgent' ? 'Urgent — seek in-person care now'
    : safety === 'caution' ? 'Caution — timely follow-up recommended'
    : 'Safe — routine care';

  return (
    <div className="page" style={{ padding: 20 }}>
      {/* ===== Top row: back + meta + actions ===== */}
      <div className="hstack" style={{ marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
        <Button variant="ghost" onClick={() => navigate('/consultations')}>← Back</Button>
        <div className="grow" style={{ minWidth: 200 }}>
          <div className="hstack gap-sm" style={{ flexWrap: 'wrap' }}>
            <span className="mono text-xs muted">{sessionId.slice(0, 8)}</span>
            <Badge variant={session?.status === 'active' ? 'primary' : session?.status === 'completed' ? 'success' : 'neutral'}>{session?.status ?? 'loading'}</Badge>
            {diagnosis?.critic_review?.safety_flag && (
              <Badge variant={safety === 'urgent' ? 'danger' : safety === 'caution' ? 'warning' : 'success'}>{diagnosis.critic_review.safety_flag}</Badge>
            )}
            <span className="text-xs muted">· {safeFormatTime(session?.created_at, 'MMM d, h:mm a')}</span>
          </div>
          <div className="text-lg fw-600" style={{ marginTop: 2 }}>{session?.title || 'Loading...'}</div>
        </div>
        <div className="hstack gap-xs">
          <div className={`status-dot ${isConnected ? 'online' : ''}`} style={{ background: isConnected ? undefined : 'var(--danger-bright)' }} />
          <span className="text-xs muted">{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      <SafetyBanner
        level={safety}
        title={safetyTitle}
        reason={diagnosis?.critic_review?.final_assessment?.slice(0, 200)}
      />

      {/* ===== Main split ===== */}
      <div className="split" style={{ marginTop: 14 }}>
        {/* LEFT: Chat */}
        <div className="split-panel">
          <div className="card-header">
            <div className="card-title"><MessageSquare size={14} />Patient Conversation</div>
            <span className="mono text-xs muted">{messages.length} messages</span>
          </div>
          <div className="chat-messages">
            {renderedChat.map((entry, i) => {
              if (entry.type === 'msg') {
                const m = entry.msg;
                if (m.role === 'user') {
                  return <UserBubble key={m.id} time={safeFormatTime(m.timestamp ?? m.created_at)}><span dangerouslySetInnerHTML={{ __html: formatBubble(m.content) }} /></UserBubble>;
                }
                return (
                  <AgentBubble key={m.id} kind={m.agent ?? 'coordinator'} time={safeFormatTime(m.timestamp ?? m.created_at)}>
                    <span dangerouslySetInnerHTML={{ __html: formatBubble(m.content) }} />
                  </AgentBubble>
                );
              }
              return <CriticChallengeCard key={`ch-${i}`} challenge={entry.ch} response={entry.resp} />;
            })}
            {streaming && (
              <AgentBubble kind={streaming.agent} streaming>
                <span dangerouslySetInnerHTML={{ __html: formatBubble(streaming.content) }} />
              </AgentBubble>
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="chat-composer">
            <div className="textarea grow">
              <textarea
                rows={2}
                placeholder={isConnected ? 'Type a follow-up… (Enter to send, Shift+Enter for newline)' : 'Reconnecting…'}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                disabled={!isConnected}
              />
            </div>
            <Button variant="primary" icon={Send} onClick={handleSend} disabled={!isConnected || !input.trim()}>Send</Button>
          </div>
        </div>

        {/* RIGHT: 5-tab inspector */}
        <div className="split-panel">
          <div className="tabs" role="tablist" style={{ margin: '0 16px' }}>
            {(['agents', 'mcp', 'dx', 'patient', 'meta'] as const).map(k => {
              const isActive = tab === k;
              const label = k === 'agents' ? 'Agents'
                : k === 'mcp' ? 'MCP'
                : k === 'dx' ? 'Diagnoses'
                : k === 'patient' ? 'Patient'
                : 'Meta';
              return (
                <div
                  key={k}
                  role="tab"
                  tabIndex={isActive ? 0 : -1}
                  aria-selected={isActive}
                  aria-label={label}
                  className={`tab ${isActive ? 'active' : ''}`}
                  onClick={() => setTab(k)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setTab(k); } }}
                >
                  {label}
                </div>
              );
            })}
          </div>
          <div style={{ padding: '4px 14px 16px', overflow: 'auto', flex: 1 }}>
            {tab === 'agents' && <AgentsTab logs={logs} onSelect={setSelectedLogId} selected={selectedLogId} />}
            {tab === 'mcp'     && <McpTab logs={logs} />}
            {tab === 'dx'      && <DxTab diagnosis={diagnosis} />}
            {tab === 'patient' && <PatientTab messages={messages} session={session} />}
            {tab === 'meta'    && <MetaTab session={session} diagnosis={diagnosis} messages={messages} logs={logs} />}
          </div>
        </div>
      </div>
    </div>
  );
}
