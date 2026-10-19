import { useEffect, useState, useCallback } from 'react';
import {
  Target,
  Shield,
  AlertTriangle,
  Activity,
  PlayCircle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  MessagesSquare,
  GitCompare,
  Database,
  Loader2,
} from 'lucide-react';
import {
  getEvaluationLatest,
  getEvaluationStatus,
  triggerEvaluation,
} from '@/services/api';
import type {
  EvaluationReport,
  EvaluationStatus,
  EvalCaseDetail,
  EvalVariant,
} from '@/types/medichain';
import { Button } from '@/components/ui/button';

// -- Helpers --

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

function Flag({ ok, label }: { ok: boolean; label: string }) {
  const Icon = ok ? CheckCircle2 : XCircle;
  const color = ok ? 'text-emerald-400' : 'text-red-400';
  return (
    <span className={`inline-flex items-center gap-1 text-xs ${color}`}>
      <Icon className="w-3.5 h-3.5" />
      {label}
    </span>
  );
}

function ProgressBar({ value, color = 'bg-primary' }: { value: number; color?: string }) {
  const pctValue = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
      <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pctValue}%` }} />
    </div>
  );
}

function SafetyBadge({ flag }: { flag: string }) {
  const colors: Record<string, string> = {
    red: 'bg-red-500/15 text-red-400 border-red-500/30',
    yellow: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    green: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  };
  const cls = colors[flag?.toLowerCase()] ?? 'bg-muted text-muted-foreground border-border';
  return (
    <span className={`text-[10px] uppercase px-2 py-0.5 rounded-full border font-semibold ${cls}`}>
      {flag || 'unknown'}
    </span>
  );
}

// -- Per-case expandable card --

function CaseCard({ c }: { c: EvalCaseDetail }) {
  const [open, setOpen] = useState(false);
  const failed = c.error && c.error.length > 0;

  return (
    <div className={`bg-card border rounded-lg overflow-hidden ${failed ? 'border-red-500/40' : 'border-border'}`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 hover:bg-muted/30 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          {open ? <ChevronDown className="w-4 h-4 text-muted-foreground shrink-0" /> : <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />}
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-mono">{c.case_id}</span>
              <span className="font-medium truncate">{c.case_name.replace(/_/g, ' ')}</span>
              {failed && <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400">ERROR</span>}
            </div>
            {!failed && (
              <div className="text-xs text-muted-foreground mt-0.5 truncate">
                AI: {c.ai_primary_diagnosis}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <Flag ok={c.top1_correct} label="Top-1" />
          <Flag ok={c.top3_recall} label="Top-3" />
          <Flag ok={c.safety_flag_correct} label="Safety" />
          <span className="text-xs text-muted-foreground inline-flex items-center gap-1">
            <MessagesSquare className="w-3 h-3" />
            {c.debate_rounds} rounds
          </span>
          <span className="text-xs text-muted-foreground inline-flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {c.total_time_seconds.toFixed(1)}s
          </span>
        </div>
      </button>

      {open && (
        <div className="border-t border-border p-4 bg-muted/20 space-y-4 text-sm">
          {failed ? (
            <div className="text-red-400 font-mono text-xs whitespace-pre-wrap">{c.error}</div>
          ) : (
            <>
              {/* AI vs Ground Truth side by side */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">AI Output</div>
                  <div className="space-y-1.5 text-xs">
                    <div>
                      <span className="text-muted-foreground">Primary: </span>
                      <span className="font-medium">{c.ai_primary_diagnosis}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Top-3: </span>
                      <span>{c.ai_top3.join(' · ') || '—'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Safety: </span>
                      <SafetyBadge flag={c.ai_safety_flag} />
                    </div>
                    {c.ai_final_assessment && (
                      <div className="pt-1 text-muted-foreground italic line-clamp-3">
                        "{c.ai_final_assessment}"
                      </div>
                    )}
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Ground Truth</div>
                  <div className="space-y-1.5 text-xs">
                    <div>
                      <span className="text-muted-foreground">Primary: </span>
                      <span className="font-medium">{c.ground_truth_primary}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Expected DDx: </span>
                      <span>{c.ground_truth_ddx.join(' · ')}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Safety: </span>
                      <SafetyBadge flag={c.ground_truth_safety} />
                    </div>
                    <div>
                      <span className="text-muted-foreground">Expected tests: </span>
                      <span>{c.ground_truth_tests.join(', ')}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Debate timeline */}
              {c.debate_summary.length > 0 && (
                <div className="border-t border-border/60 pt-3">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                    Debate Timeline ({c.debate_rounds} rounds · {c.challenges_accepted} accepted · {c.challenges_refuted} refuted)
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {c.debate_summary.map((r) => (
                      <div
                        key={r.round_number}
                        className="px-3 py-1.5 rounded-md bg-purple-500/10 border border-purple-500/30 text-[11px]"
                      >
                        <span className="font-semibold text-purple-300">R{r.round_number}</span>
                        <span className="text-muted-foreground"> · {r.challenges_count} challenges → {r.responses_count} responses ({r.resolution})</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// -- Main page --

export default function Evaluation() {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [status, setStatus] = useState<EvaluationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([
        getEvaluationLatest().catch(() => null),
        getEvaluationStatus().catch(() => null),
      ]);
      setReport(r);
      setStatus(s);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll while running
  useEffect(() => {
    if (status?.status !== 'running') return;
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [status?.status, refresh]);

  const handleRun = async () => {
    setTriggering(true);
    try {
      await triggerEvaluation({});
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setTriggering(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64 text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading evaluation…
      </div>
    );
  }

  const variant: EvalVariant | undefined = report?.variants?.[0];
  const metrics = variant?.metrics;
  const isRunning = status?.status === 'running';
  const hasData = report?.has_data && variant && metrics;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Evaluation Harness</h1>
          <p className="text-sm text-muted-foreground">
            Offline scoring pipeline · 7 ground-truth clinical cases · V2 debate protocol
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-2" onClick={refresh}>
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
          <Button size="sm" className="gap-2" onClick={handleRun} disabled={triggering || isRunning}>
            {triggering || isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
            {isRunning ? 'Running…' : 'Run Evaluation'}
          </Button>
        </div>
      </div>

      {/* Running banner */}
      {isRunning && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 flex items-center gap-3">
          <Loader2 className="w-5 h-5 text-amber-400 animate-spin" />
          <div className="text-sm">
            <div className="font-medium text-amber-300">Evaluation in progress…</div>
            <div className="text-xs text-muted-foreground">
              Started at {status?.started_at ? new Date(status.started_at).toLocaleTimeString() : '—'}.
              Running 7 cases through the V2 debate pipeline. Each case ≈ 2-4 minutes.
            </div>
          </div>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div className="text-sm">
            <div className="font-medium text-red-300">Error</div>
            <div className="text-xs text-muted-foreground">{error}</div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!hasData && !isRunning && (
        <div className="bg-card border border-border rounded-lg p-16 flex flex-col items-center text-center">
          <Database className="w-12 h-12 text-muted-foreground mb-4" />
          <h3 className="font-semibold mb-1">No evaluation data yet</h3>
          <p className="text-sm text-muted-foreground mb-4">
            {report?.message ?? 'Click "Run Evaluation" to score 7 clinical test cases against the V2 pipeline.'}
          </p>
          <Button size="sm" className="gap-2" onClick={handleRun} disabled={triggering}>
            {triggering ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
            Run Evaluation
          </Button>
        </div>
      )}

      {/* Summary metrics */}
      {hasData && metrics && (
        <>
          <div className="text-xs text-muted-foreground">
            Last run: <span className="text-foreground font-medium">{report?.generated_at}</span>
            {' · '}Variant: <span className="text-foreground font-mono">{variant.name}</span>
            {' · '}Cases: <span className="text-foreground">{metrics.total_cases}</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              icon={Target}
              label="Top-1 Accuracy"
              value={pct(metrics.top1_accuracy)}
              hint="AI's first choice matches ground truth"
              progress={metrics.top1_accuracy}
              color="bg-blue-500"
            />
            <MetricCard
              icon={GitCompare}
              label="Top-3 Recall"
              value={pct(metrics.top3_recall)}
              hint="Ground truth appears in top-3 DDx"
              progress={metrics.top3_recall}
              color="bg-emerald-500"
            />
            <MetricCard
              icon={Shield}
              label="Safety Flag Recall"
              value={pct(metrics.safety_flag_recall)}
              hint="Red/yellow/green triage correct"
              progress={metrics.safety_flag_recall}
              color="bg-purple-500"
            />
            <MetricCard
              icon={AlertTriangle}
              label="Missed Critical"
              value={String(metrics.missed_critical)}
              hint="Cases where safety flag was wrong"
              progress={metrics.total_cases > 0 ? 1 - metrics.missed_critical / metrics.total_cases : 0}
              color={metrics.missed_critical > 0 ? 'bg-red-500' : 'bg-emerald-500'}
            />
          </div>

          {/* Debate Protocol Metrics */}
          <div className="bg-card border border-border rounded-lg p-5">
            <div className="flex items-center gap-2 mb-4">
              <MessagesSquare className="w-4 h-4 text-purple-400" />
              <h3 className="text-sm font-semibold">Debate Protocol Metrics</h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/30">V2</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <DebateStat
                label="Avg Rounds per Case"
                value={metrics.debate_rounds_avg.toFixed(1)}
                max="2.0"
                progress={metrics.debate_rounds_avg / 2}
              />
              <DebateStat
                label="Challenge Acceptance"
                value={pct(metrics.challenge_acceptance_rate)}
                hint="Diagnostician accepted Critic's challenge"
                progress={metrics.challenge_acceptance_rate}
              />
              <DebateStat
                label="Diagnosis Revision Rate"
                value={pct(metrics.diagnosis_revision_rate)}
                hint="% of cases where debate changed the diagnosis"
                progress={metrics.diagnosis_revision_rate}
              />
            </div>
          </div>

          {/* Per-case breakdown */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Case-by-Case Breakdown</h3>
              <span className="text-xs text-muted-foreground">{variant.cases.length} cases · click to expand</span>
            </div>
            <div className="space-y-2">
              {variant.cases.map((c) => (
                <CaseCard key={c.case_id} c={c} />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// -- Sub-components --

function MetricCard({
  icon: Icon,
  label,
  value,
  hint,
  progress,
  color,
}: {
  icon: typeof Target;
  label: string;
  value: string;
  hint: string;
  progress: number;
  color: string;
}) {
  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground uppercase tracking-wide">{label}</span>
        <Icon className="w-4 h-4 text-muted-foreground" />
      </div>
      <p className="text-2xl font-bold">{value}</p>
      <ProgressBar value={progress} color={color} />
      <p className="text-[10px] text-muted-foreground">{hint}</p>
    </div>
  );
}

function DebateStat({
  label,
  value,
  max,
  hint,
  progress,
}: {
  label: string;
  value: string;
  max?: string;
  hint?: string;
  progress: number;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        {max && <span className="text-[10px] text-muted-foreground">max {max}</span>}
      </div>
      <div className="text-xl font-bold">{value}</div>
      <ProgressBar value={progress} color="bg-purple-500" />
      {hint && <p className="text-[10px] text-muted-foreground">{hint}</p>}
    </div>
  );
}
