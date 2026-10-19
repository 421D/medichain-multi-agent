import {
  Swords,
  ShieldCheck,
  ShieldX,
  ShieldQuestion,
  CheckCircle,
  AlertTriangle,
  XCircle,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { useState, useMemo } from 'react';
import { Badge } from '@/components/ui/badge';
import type {
  DebateRound,
  DebateChallenge,
  DebateResponse,
  DebateResolution,
  DebateOutcome,
} from '@/types/medichain';

// --- Helpers ---

const ACTION_CONFIG = {
  accept:           { label: 'Accepted',           icon: ShieldCheck,    className: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' },
  refute:           { label: 'Refuted',            icon: ShieldX,        className: 'text-red-400 bg-red-500/10 border-red-500/30' },
  partially_accept: { label: 'Partially Accepted', icon: ShieldQuestion, className: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
} as const;

const RESOLUTION_CONFIG: Record<DebateResolution, { label: string; icon: typeof CheckCircle; className: string }> = {
  pending:   { label: 'In Progress', icon: AlertTriangle,  className: 'text-blue-400 bg-blue-500/10 border-blue-500/30' },
  resolved:  { label: 'Resolved',    icon: CheckCircle,    className: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' },
  escalated: { label: 'Escalated',   icon: AlertTriangle,  className: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
  deadlock:  { label: 'Deadlock',    icon: XCircle,        className: 'text-red-400 bg-red-500/10 border-red-500/30' },
};

const CHALLENGE_TYPE_LABELS: Record<DebateChallenge['type'], string> = {
  evidence_gap:          'Evidence Gap',
  alternative_diagnosis: 'Alternative Dx',
  risk_underestimation:  'Risk Underest.',
  methodology:           'Methodology',
  general:               'General',
  missed_diagnosis:      'Missed Dx',
  scoring_error:         'Scoring Error',
  safety_concern:        'Safety Concern',
};

// --- Sub-components ---

function ChallengeCard({ challenge }: { challenge: DebateChallenge }) {
  return (
    <div className="rounded-lg border border-agent-critic/30 bg-red-500/5 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-red-400">Critic Challenge</span>
        <Badge className="text-[10px] px-1.5 py-0 bg-muted border-border text-muted-foreground">
          {CHALLENGE_TYPE_LABELS[challenge.type]}
        </Badge>
      </div>
      <p className="text-xs text-foreground leading-relaxed font-medium">{challenge.claim}</p>
      {challenge.evidence.length > 0 && (
        <ul className="space-y-0.5">
          {challenge.evidence.map((e, i) => (
            <li key={i} className="text-[11px] text-muted-foreground flex items-start gap-1.5">
              <span className="text-red-500/70 mt-px flex-shrink-0">&bull;</span>
              {e}
            </li>
          ))}
        </ul>
      )}
      <p className="text-[11px] text-muted-foreground italic">Suggested: {challenge.suggested_action}</p>
    </div>
  );
}

function ResponseCard({ response }: { response: DebateResponse }) {
  const config = ACTION_CONFIG[response.action];
  const Icon = config.icon;

  return (
    <div className="rounded-lg border border-agent-diagnostician/30 bg-emerald-500/5 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">Diagnostician</span>
        <Badge className={`text-[10px] px-1.5 py-0 border ${config.className}`}>
          <Icon className="w-3 h-3 mr-1" />
          {config.label}
        </Badge>
      </div>
      <p className="text-xs text-foreground leading-relaxed">{response.reasoning}</p>
      {response.evidence.length > 0 && (
        <ul className="space-y-0.5">
          {response.evidence.map((e, i) => (
            <li key={i} className="text-[11px] text-muted-foreground flex items-start gap-1.5">
              <span className="text-emerald-500/70 mt-px flex-shrink-0">&bull;</span>
              {e}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RoundCard({ round, defaultExpanded = true }: { round: DebateRound; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const resConfig = RESOLUTION_CONFIG[round.resolution];
  const ResIcon = resConfig.icon;

  // Pair challenges with their responses by challenge_id
  const paired = round.challenges.map(ch => ({
    challenge: ch,
    response: round.responses.find(r => r.challenge_id === ch.challenge_id),
  }));

  // M13 fix: memoize O(n*m) orphan response filter
  const orphanResponses = useMemo(
    () => round.responses.filter(r => !round.challenges.some(c => c.challenge_id === r.challenge_id)),
    [round.challenges, round.responses],
  );

  return (
    <div className="border border-border rounded-lg overflow-hidden animate-slide-in">
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/40 transition-colors"
      >
        <Swords className="w-4 h-4 text-primary flex-shrink-0" />
        <span className="text-sm font-semibold text-foreground flex-1">Round {round.round_number}</span>
        <Badge className={`text-[10px] px-2 py-0.5 border ${resConfig.className}`}>
          <ResIcon className="w-3 h-3 mr-1" />
          {resConfig.label}
        </Badge>
        {expanded
          ? <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
          : <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        }
      </button>

      {expanded && (
        <div className="border-t border-border bg-muted/10 p-3 space-y-3">
          {paired.map(({ challenge, response }, i) => (
            // Always include the index — LLMs sometimes return non-unique challenge_id
            // (e.g. using the challenge type as the id), which causes React key collisions.
            <div key={`r${round.round_number}-${i}-${challenge.challenge_id || ''}`} className="grid grid-cols-2 gap-2">
              <ChallengeCard challenge={challenge} />
              {response
                ? <ResponseCard response={response} />
                : <div className="rounded-lg border border-dashed border-border p-3 flex items-center justify-center text-xs text-muted-foreground">Awaiting response...</div>
              }
            </div>
          ))}

          {/* Show any responses that have no matching challenge (edge case) */}
          {orphanResponses.map((response, i) => (
              <div key={`orphan-${i}`} className="grid grid-cols-2 gap-2">
                <div className="rounded-lg border border-dashed border-border p-3 flex items-center justify-center text-xs text-muted-foreground">Challenge not available</div>
                <ResponseCard response={response} />
              </div>
            ))
          }
        </div>
      )}
    </div>
  );
}

// --- Main component ---

interface DebateViewProps {
  outcome: DebateOutcome | null;
  /** Live rounds accumulated from individual WS events */
  liveRounds: DebateRound[];
}

export default function DebateView({ outcome, liveRounds }: DebateViewProps) {
  const rounds = outcome?.rounds ?? liveRounds;

  if (rounds.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center space-y-2">
        <Swords className="w-8 h-8 text-muted-foreground/50" />
        <p className="text-xs text-muted-foreground">Debate will appear here once the diagnostic review begins.</p>
        <p className="text-[10px] text-muted-foreground/70">
          When the Critic challenges the Diagnostician's conclusions,<br />the debate protocol will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Summary badge if final outcome */}
      {outcome?.summary && (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
          <p className="text-[10px] uppercase tracking-wider text-primary font-semibold mb-1">Debate Summary</p>
          <p className="text-xs text-secondary-foreground leading-relaxed">{outcome.summary}</p>
        </div>
      )}

      {rounds.map((round) => (
        <RoundCard key={round.round_number} round={round} defaultExpanded={round.round_number === rounds.length} />
      ))}
    </div>
  );
}
