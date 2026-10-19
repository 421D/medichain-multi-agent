import { useState, useMemo } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FlaskConical,
  Activity,
  TrendingUp,
  CheckCircle2,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { DiagnosisResult, DiagnosisEntry, CDSSScore, CriticReview } from '@/types/medichain';

// --- Sub-components ---

// Map the backend's `critic_review.safety_flag` (green/yellow/red) into the
// SafetyBadge level. Falls back to `result.safety_level` for forward-compat
// if the backend ever starts emitting it directly.
function _flagToLevel(flag?: string, fallback?: DiagnosisResult['safety_level']): NonNullable<DiagnosisResult['safety_level']> {
  if (fallback) return fallback;
  switch ((flag || '').toLowerCase()) {
    case 'red':    return 'urgent';
    case 'yellow': return 'caution';
    case 'green':  return 'safe';
    default:       return 'safe';
  }
}

function SafetyBadge({ level }: { level: NonNullable<DiagnosisResult['safety_level']> }) {
  const config = {
    safe:    { icon: ShieldCheck,  label: 'Low Risk',  className: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400' },
    caution: { icon: ShieldAlert,  label: 'Caution',   className: 'border-amber-500/40 bg-amber-500/10 text-amber-400' },
    urgent:  { icon: AlertTriangle, label: 'Urgent',   className: 'border-red-500/40 bg-red-500/10 text-red-400' },
  };
  const c = config[level];
  const Icon = c.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${c.className}`}>
      <Icon className="w-3.5 h-3.5" />
      {c.label}
    </span>
  );
}

function DiagnosisRow({ entry, rank }: { entry: DiagnosisEntry; rank: number }) {
  const [open, setOpen] = useState(false);
  const hue = entry.confidence >= 70 ? 150 : entry.confidence >= 40 ? 38 : 0;

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/40 transition-colors"
      >
        <span className="text-xs font-mono text-muted-foreground w-5 flex-shrink-0">#{rank}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-sm font-medium text-foreground truncate">{entry.diagnosis}</span>
            <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 rounded bg-muted flex-shrink-0">{entry.source}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1">
              <div
                className="h-1.5 rounded-full transition-all duration-500"
                style={{
                  width: `${entry.confidence}%`,
                  backgroundColor: `hsl(${hue} 70% 50%)`,
                }}
              />
            </div>
            <span className="text-xs font-semibold tabular-nums" style={{ color: `hsl(${hue} 70% 60%)` }}>
              {entry.confidence}%
            </span>
          </div>
        </div>
        {open ? <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" /> : <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />}
      </button>

      {open && (
        <div className="px-4 pb-3 pt-0 border-t border-border bg-muted/20 space-y-3 animate-slide-in">
          {entry.supporting_evidence.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-emerald-400 font-semibold mb-1.5">Supporting Evidence</p>
              <ul className="space-y-1">
                {entry.supporting_evidence.map((e, i) => (
                  <li key={i} className="text-xs text-secondary-foreground flex items-start gap-1.5">
                    <span className="text-emerald-500 mt-0.5 flex-shrink-0">+</span>
                    {e}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {entry.against_evidence.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-red-400 font-semibold mb-1.5">Against Evidence</p>
              <ul className="space-y-1">
                {entry.against_evidence.map((e, i) => (
                  <li key={i} className="text-xs text-secondary-foreground flex items-start gap-1.5">
                    <span className="text-red-500 mt-0.5 flex-shrink-0">-</span>
                    {e}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CDSSScoreCard({ score }: { score: CDSSScore }) {
  const riskColors: Record<CDSSScore['risk_level'], { bg: string; text: string; border: string }> = {
    low:      { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30' },
    moderate: { bg: 'bg-amber-500/10',   text: 'text-amber-400',   border: 'border-amber-500/30' },
    high:     { bg: 'bg-orange-500/10',   text: 'text-orange-400',  border: 'border-orange-500/30' },
    critical: { bg: 'bg-red-500/10',      text: 'text-red-400',     border: 'border-red-500/30' },
  };
  const c = riskColors[score.risk_level];

  return (
    <div className={`rounded-lg border ${c.border} ${c.bg} p-3 space-y-1.5`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground">{score.tool_name}</span>
        <Badge className={`${c.text} ${c.bg} border ${c.border} text-[10px] px-1.5 py-0`}>
          {score.risk_level.toUpperCase()}
        </Badge>
      </div>
      <p className={`text-lg font-bold tabular-nums ${c.text}`}>
        {score.score}{score.max_score != null ? `/${score.max_score}` : ''}
      </p>
      <p className="text-[11px] text-muted-foreground leading-snug">{score.recommendation}</p>
    </div>
  );
}

// --- Main component ---

interface DiagnosisPanelProps {
  result: DiagnosisResult;
}

export default function DiagnosisPanel({ result }: DiagnosisPanelProps) {
  // L5 fix: memoize sorted array
  const sorted = useMemo(
    () => [...result.differential_diagnosis].sort((a, b) => b.confidence - a.confidence),
    [result.differential_diagnosis]
  );
  const [showAllTests, setShowAllTests] = useState(false);
  const tests = result.recommended_tests ?? [];
  const visibleTests = showAllTests ? tests : tests.slice(0, 5);

  return (
    <div className="space-y-4 animate-slide-in">
      {/* Header */}
      <Card className="border-primary/20 bg-card">
        <CardHeader className="p-4 pb-2 flex-row items-center justify-between space-y-0">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" />
            Diagnosis Result
          </CardTitle>
          <SafetyBadge level={_flagToLevel(result.critic_review?.safety_flag, result.safety_level)} />
        </CardHeader>
        {result.coordinator_response && (
          <CardContent className="px-4 pb-4 pt-1">
            <p className="text-xs text-muted-foreground leading-relaxed">{result.coordinator_response}</p>
          </CardContent>
        )}
      </Card>

      {/* Differential Diagnoses */}
      <div className="space-y-2">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 px-1">
          <TrendingUp className="w-3.5 h-3.5" />
          Differential Diagnoses ({sorted.length})
        </h4>
        <div className="space-y-1.5">
          {sorted.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">No diagnoses generated.</p>
          ) : (
            sorted.map((entry, i) => (
              <DiagnosisRow key={`${entry.diagnosis}-${i}`} entry={entry} rank={i + 1} />
            ))
          )}
        </div>
      </div>

      {/* CDSS Scores */}
      {result.cdss_scores && result.cdss_scores.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 px-1">
            <FlaskConical className="w-3.5 h-3.5" />
            Clinical Scoring (CDSS)
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {result.cdss_scores.map((s, i) => (
              <CDSSScoreCard key={`${s.tool_name}-${i}`} score={s} />
            ))}
          </div>
        </div>
      )}

      {/* Recommended Tests */}
      {tests.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 px-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Recommended Tests
          </h4>
          <div className="rounded-lg border border-border bg-card p-3 space-y-1.5">
            {visibleTests.map((t, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-secondary-foreground py-0.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-primary mt-0.5 flex-shrink-0" />
                {t}
              </div>
            ))}
            {tests.length > 5 && (
              <button
                onClick={() => setShowAllTests(v => !v)}
                className="text-[11px] text-primary hover:underline mt-1"
              >
                {showAllTests ? 'Show less' : `Show ${tests.length - 5} more`}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Critic Review */}
      {result.critic_review && (
        <div className="rounded-lg border border-agent-critic/30 bg-red-500/5 p-3 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[10px] uppercase tracking-wider text-red-400 font-semibold">Critic Review</p>
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
              result.critic_review.approval
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                : 'border-red-500/40 bg-red-500/10 text-red-400'
            }`}>
              {result.critic_review.approval ? 'APPROVED' : 'DENIED'} | Safety: {result.critic_review.safety_flag}
            </span>
          </div>
          <p className="text-xs text-secondary-foreground leading-relaxed">{result.critic_review.final_assessment}</p>
          {result.critic_review.issues.length > 0 && (
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Issues</p>
              {result.critic_review.issues.map((issue, i) => (
                <div key={i} className="text-xs text-secondary-foreground pl-2 border-l-2 border-red-500/30">
                  <span className="font-medium text-red-400">[{issue.type}]</span> {issue.description}
                  {issue.suggestion && <p className="text-[11px] text-muted-foreground italic mt-0.5">Suggestion: {issue.suggestion}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
