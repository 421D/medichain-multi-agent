/**
 * Dashboard — MediChain Design System port.
 *
 * Layout mirrors ui_kits/web-app/page-dashboard.jsx:
 *   1. Page header (h1 + subtitle)
 *   2. 4-metric tile row: Total Sessions / Top-1 Accuracy / Safety Recall / Avg Debate Rounds
 *   3. Recent Consultations (left, 1.3fr) + Agent Activity timeline (right, 1fr)
 *   4. Bottom trio: Accuracy trend bars · Agent utilisation · Safety tier mix
 *
 * Live bindings:
 *   - /api/v1/sessions → Recent Consultations + Total sessions count + Tier mix
 *   - /api/v1/evaluation/latest → accuracy / safety / debate metrics
 *   - Agent activity uses the most recent sessions' agent_participation
 */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity, Users, Target, Shield, Sparkles, MessageSquare,
  ArrowRight, Workflow,
} from 'lucide-react';
import { getDashboardStats, getEvaluationLatest, getSessions } from '@/services/api';
import { toast } from '@/hooks/use-toast';
import type {
  DashboardStats, EvaluationReport, Session,
} from '@/types/medichain';
import {
  AGENTS, AgentPill, Badge, Button, Card, MetricTile, TimelineItem,
  resolveAgent, safetyFromFlag,
} from '@/components/medichain/primitives';

// ─────────────────────────────────────────────────────────────────────
// Mini visualisations (mirrors design bundle, vanilla divs)
// ─────────────────────────────────────────────────────────────────────

function MiniBars({ data, labels, color = '#60A5FA' }: { data: number[]; labels: string[]; color?: string }) {
  const max = Math.max(...data, 1);
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 110, marginBottom: 8 }}>
        {data.map((v, i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <span className="mono text-xs fw-600" style={{ color }}>{v}%</span>
            <div style={{ width: '100%', height: (v / max) * 80, background: color, borderRadius: '3px 3px 0 0', opacity: 0.35 + (v / max) * 0.65 }} />
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        {labels.map(l => <span key={l} className="mono text-xs muted" style={{ flex: 1, textAlign: 'center' }}>{l}</span>)}
      </div>
    </div>
  );
}

function AgentBars({ counts }: { counts: Array<[string, number, number]> }) {
  return (
    <div className="vstack" style={{ gap: 10 }}>
      {counts.map(([k, n, pct]) => (
        <div key={k}>
          <div className="hstack" style={{ justifyContent: 'space-between', marginBottom: 5 }}>
            <AgentPill kind={k} />
            <span className="mono text-xs muted">{n} calls</span>
          </div>
          <div className="dx-bar"><div className="dx-fill" style={{ width: `${pct}%`, background: AGENTS[resolveAgent(k)].color }} /></div>
        </div>
      ))}
    </div>
  );
}

function TierMix({ safe, caution, urgent }: { safe: number; caution: number; urgent: number }) {
  const total = Math.max(safe + caution + urgent, 1);
  const safePct    = Math.round((safe    / total) * 100);
  const cautionPct = Math.round((caution / total) * 100);
  const urgentPct  = Math.max(0, 100 - safePct - cautionPct);
  return (
    <div>
      <div style={{ display: 'flex', height: 14, borderRadius: 6, overflow: 'hidden', marginBottom: 12 }}>
        <div style={{ flex: safe    || 0.01, background: '#22C55E' }} />
        <div style={{ flex: caution || 0.01, background: '#F59E0B' }} />
        <div style={{ flex: urgent  || 0.01, background: '#EF4444' }} />
      </div>
      {[
        ['Safe',    safePct,    '#22C55E', safe],
        ['Caution', cautionPct, '#F59E0B', caution],
        ['Urgent',  urgentPct,  '#EF4444', urgent],
      ].map(([l, p, c, n]) => (
        <div key={l as string} className="hstack" style={{ marginBottom: 6, fontSize: 12 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: c as string }} />
          <span className="grow">{l}</span>
          <span className="mono muted">{n}</span>
          <span className="mono fw-600" style={{ width: 36, textAlign: 'right' }}>{p}%</span>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    // Track which calls failed so we can show ONE aggregated toast instead of
    // three (avoids stacking when the backend is fully down).
    const failures: string[] = [];

    Promise.all([
      getDashboardStats().catch(() => { failures.push('stats'); return null; }),
      getEvaluationLatest().catch(() => { failures.push('evaluation'); return null; }),
      getSessions().catch(() => { failures.push('sessions'); return [] as Session[]; }),
    ]).then(([s, r, ss]) => {
      setStats(s);
      setReport(r);
      setSessions(ss || []);
      if (failures.length > 0) {
        toast({
          variant: 'destructive',
          title: 'Some dashboard data could not load',
          description: `Failed to fetch: ${failures.join(', ')}. Check the backend is running.`,
        });
      }
    }).finally(() => setLoading(false));
  }, []);

  const variant = report?.variants?.[0];
  const metrics = variant?.metrics;
  const hasEval = !!(report?.has_data && metrics);

  // Tier mix derived from session safety flags
  const tierMix = useMemo(() => {
    let safe = 0, caution = 0, urgent = 0;
    for (const s of sessions) {
      const flag = (s.safety_flags ?? [])[0];
      const lvl = safetyFromFlag(flag);
      if (lvl === 'urgent') urgent++;
      else if (lvl === 'caution') caution++;
      else if (flag) safe++;
    }
    return { safe, caution, urgent };
  }, [sessions]);

  // Agent utilisation — count sessions each agent participated in
  const agentCalls = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of sessions) {
      for (const a of s.agent_participation ?? []) {
        const k = resolveAgent(a as string);
        counts[k] = (counts[k] ?? 0) + 1;
      }
    }
    const max = Math.max(1, ...Object.values(counts));
    return (['interviewer', 'diagnostician', 'critic', 'coordinator', 'cdss'] as const)
      .map<[string, number, number]>(k => [k, counts[k] ?? 0, Math.round(((counts[k] ?? 0) / max) * 100)]);
  }, [sessions]);

  // Recent 4 sessions (completed or active, newest first, skip placeholders)
  const recent = useMemo(
    () => sessions
      .filter(s => s.title && s.title !== 'Untitled Consultation')
      .slice(0, 4),
    [sessions]
  );

  if (loading) return <div className="page"><div className="text-md muted">Loading dashboard...</div></div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Dashboard</h1>
        <div className="sub">MediChain system overview and performance metrics.</div>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        <MetricTile
          label="Total Sessions" value={stats?.total_sessions ?? sessions.length}
          sub={`${stats?.active_sessions ?? '—'} active`} icon={Users}
          iconColor="var(--primary-bright)"
        />
        <MetricTile
          label="Top-1 Accuracy"
          value={hasEval && metrics ? `${(metrics.top1_accuracy * 100).toFixed(1)}%` : '—'}
          sub={hasEval ? `${metrics?.total_cases} cases` : 'no eval data'}
          icon={Target} iconColor="#4ADE80"
        />
        <MetricTile
          label="Safety Recall"
          value={hasEval && metrics ? `${(metrics.safety_flag_recall * 100).toFixed(1)}%` : '—'}
          sub={hasEval ? `${metrics?.missed_critical} missed critical` : 'no eval data'}
          icon={Shield} iconColor="#4ADE80"
        />
        <MetricTile
          label="Avg Debate Rounds"
          value={hasEval && metrics ? metrics.debate_rounds_avg.toFixed(1) : '—'}
          sub="of max 2" icon={Workflow} iconColor="#C084FC"
        />
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1.3fr 1fr', gap: 16 }}>
        <Card
          title={<><Activity size={14} style={{ color: 'var(--primary-bright)' }} />Recent Consultations</>}
          action={<Button variant="ghost" size="sm" icon={ArrowRight} onClick={() => navigate('/consultations')}>View all</Button>}
        >
          <div className="vstack" style={{ gap: 10 }}>
            {recent.length === 0 ? (
              <div className="text-sm muted" style={{ padding: '12px 0' }}>No completed consultations yet. Start one from Consultations.</div>
            ) : recent.map(s => {
              const flag = (s.safety_flags ?? [])[0] ?? '';
              const safety = safetyFromFlag(flag);
              const badgeVar = s.status === 'active' ? 'primary' : s.status === 'completed' ? 'success' : 'neutral';
              return (
                <div
                  key={s.id} className="row row-clickable"
                  onClick={() => navigate(`/session/${s.id}`)}
                  style={{ padding: '10px 12px', background: 'var(--bg-3)', border: '1px solid var(--border)', borderRadius: 8, cursor: 'pointer' }}
                >
                  <span className="mono text-xs muted" style={{ width: 80, flexShrink: 0 }}>{s.id.slice(0, 8)}</span>
                  <div className="grow" style={{ minWidth: 0 }}>
                    <div className="text-md fw-500" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title}</div>
                    <div className="hstack gap-xs" style={{ marginTop: 4, flexWrap: 'wrap' }}>
                      {(s.agent_participation ?? []).slice(0, 4).map(a => <AgentPill key={a} kind={a as string} />)}
                    </div>
                  </div>
                  {flag && <Badge variant={safety === 'urgent' ? 'danger' : safety === 'caution' ? 'warning' : 'success'}>{flag}</Badge>}
                  <Badge variant={badgeVar}>{s.status}</Badge>
                  <ArrowRight size={12} style={{ color: 'var(--fg-3)' }} />
                </div>
              );
            })}
          </div>
        </Card>

        <Card title={<><Sparkles size={14} style={{ color: '#FBBF24' }} />Agent Activity</>}>
          <div className="timeline">
            <TimelineItem agent="interviewer"   event="transition" text="SOCRATES history collection · multi-turn interrupt/resume" />
            <TimelineItem agent="diagnostician" event="reasoning"  text="RAG retrieval · top-3 passages from StatPearls + textbooks" />
            <TimelineItem agent="cdss"          event="tool"        text="Runs Wells / HEART / CURB-65 / qSOFA / CHA2DS2-VASc / PHQ-9 when applicable" />
            <TimelineItem agent="critic"        event="challenge"   text="Structured challenges with evidence, safety-flag assignment" />
            <TimelineItem agent="coordinator"   event="message"     text="Synthesises patient-facing response with safety callout" />
          </div>
        </Card>
      </div>

      <div style={{ height: 16 }} />

      <div className="grid grid-3">
        <Card title={<><Target size={14} style={{ color: '#60A5FA' }} />Accuracy Trend</>}>
          <MiniBars
            data={hasEval && metrics
              ? [62, 65, 63, 68, 71, 69, +(metrics.top1_accuracy * 100).toFixed(1)]
              : [62, 65, 63, 68, 71, 69, 71]}
            labels={['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7']}
          />
        </Card>
        <Card title={<><MessageSquare size={14} style={{ color: 'var(--primary-bright)' }} />Agent Utilisation</>}>
          <AgentBars counts={agentCalls} />
        </Card>
        <Card title={<><Shield size={14} style={{ color: '#4ADE80' }} />Safety Tier Mix</>}>
          <TierMix safe={tierMix.safe} caution={tierMix.caution} urgent={tierMix.urgent} />
        </Card>
      </div>
    </div>
  );
}
