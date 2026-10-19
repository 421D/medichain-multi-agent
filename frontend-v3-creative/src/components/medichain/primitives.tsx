/**
 * MediChain design-system primitives.
 *
 * React/TS ports of the handoff bundle's shared components
 * (ui_kits/web-app/primitives.jsx). These components use the plain-CSS
 * classes defined in styles/medichain.css — they deliberately bypass
 * Tailwind utilities so a visual tweak in the CSS propagates everywhere.
 *
 * When to use these vs shadcn/Tailwind: use these whenever rendering
 * MediChain-specific UI (agent pills, safety callouts, diagnosis rows,
 * chat bubbles, etc.). Fall back to shadcn components only for generic
 * modals, toasts, tooltips that the design system doesn't define.
 */
import {
  Activity, AlertTriangle, ArrowRight, BookOpen, Check, Clock,
  Database, Filter, MessageSquare, RefreshCw, Search, Send,
  Settings, Shield, ShieldAlert, Sparkles, Stethoscope, Target,
  Trash2, User, Users, Wrench, X, Zap, GitBranch,
  LayoutDashboard, BarChart3, Workflow, ChevronDown, ChevronRight,
  Bell, Plus,
  type LucideIcon,
} from 'lucide-react';
import type { ReactNode } from 'react';

// ─────────────────────────────────────────────────────────────────────
// Agent identity — mirrors the 6-agent palette in the design spec
// ─────────────────────────────────────────────────────────────────────

export type AgentKind =
  | 'interviewer' | 'diagnostician' | 'critic'
  | 'cdss' | 'coordinator' | 'debate' | 'debate_round';

interface AgentMeta {
  name: string;
  dot: string;             // emoji identifier (always-on)
  color: string;           // CSS var reference
  className: string;       // agent-pill variant
  icon: LucideIcon;
}

const AGENT_ALIAS: Record<string, AgentKind> = { debate_round: 'debate' };

export const AGENTS: Record<AgentKind, AgentMeta> = {
  interviewer:   { name: 'Interviewer',   dot: '🔵', color: 'var(--ag-i)',  className: 'ag-interviewer',   icon: User },
  diagnostician: { name: 'Diagnostician', dot: '🟢', color: 'var(--ag-d)',  className: 'ag-diagnostician', icon: Stethoscope },
  critic:        { name: 'Critic',        dot: '🔴', color: 'var(--ag-c)',  className: 'ag-critic',        icon: ShieldAlert },
  cdss:          { name: 'CDSS',          dot: '🔷', color: 'var(--ag-cd)', className: 'ag-cdss',          icon: Target },
  coordinator:   { name: 'Coordinator',   dot: '🟡', color: 'var(--ag-co)', className: 'ag-coordinator',   icon: Activity },
  debate:        { name: 'Debate',        dot: '🟣', color: 'var(--ag-db)', className: 'ag-debate',        icon: GitBranch },
  debate_round:  { name: 'Debate',        dot: '🟣', color: 'var(--ag-db)', className: 'ag-debate',        icon: GitBranch },
};

export function resolveAgent(raw?: string | null): AgentKind {
  if (!raw) return 'coordinator';
  const key = raw.toLowerCase();
  if (AGENT_ALIAS[key]) return AGENT_ALIAS[key];
  if (key in AGENTS) return key as AgentKind;
  return 'coordinator';
}

export function AgentPill({ kind, dim = false }: { kind: string; dim?: boolean }) {
  const a = AGENTS[resolveAgent(kind)];
  return (
    <span className={`agent-pill ${a.className}`} style={dim ? { opacity: 0.6 } : undefined}>
      {a.dot} {a.name}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Badges & buttons
// ─────────────────────────────────────────────────────────────────────

type BadgeVariant = 'neutral' | 'outline' | 'primary' | 'success' | 'warning' | 'danger';

export function Badge({ children, variant = 'neutral' }: { children: ReactNode; variant?: BadgeVariant }) {
  return <span className={`badge badge-${variant}`}>{children}</span>;
}

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive';
interface BtnProps {
  children?: ReactNode;
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
  icon?: LucideIcon;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  title?: string;
  type?: 'button' | 'submit';
}

export function Button({ children, variant = 'secondary', size, icon: Icon, onClick, disabled, className = '', title, type = 'button' }: BtnProps) {
  const cls = `btn btn-${variant} ${size === 'sm' ? 'btn-sm' : ''} ${className}`.trim();
  return (
    <button type={type} className={cls} onClick={onClick} disabled={disabled} title={title}>
      {Icon && <Icon size={14} />}
      {children}
    </button>
  );
}

export function IconButton({ icon: Icon, onClick, title, className = '' }: { icon: LucideIcon; onClick?: () => void; title?: string; className?: string }) {
  return (
    <button type="button" className={`btn btn-ghost btn-icon ${className}`} onClick={onClick} title={title}>
      <Icon size={16} />
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Card + status
// ─────────────────────────────────────────────────────────────────────

export function Card({ title, action, children, className = '', style }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; style?: React.CSSProperties }) {
  return (
    <div className={`card ${className}`} style={style}>
      {(title || action) && (
        <div className="card-header">
          <div className="card-title">{title}</div>
          {action}
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  );
}

export function StatusDot({ kind = 'online' }: { kind?: 'online' | 'offline' }) {
  return <span className={`status-dot ${kind}`} />;
}

// ─────────────────────────────────────────────────────────────────────
// Safety callout + banner
// ─────────────────────────────────────────────────────────────────────

export type SafetyLevel = 'safe' | 'caution' | 'urgent';

export function safetyFromFlag(flag?: string | null): SafetyLevel {
  const s = (flag || '').toLowerCase();
  if (s === 'red') return 'urgent';
  if (s === 'yellow') return 'caution';
  return 'safe';
}

export function SafetyCallout({ level, title, children }: { level: SafetyLevel; title?: string; children: ReactNode }) {
  const Ico = level === 'safe' ? Shield : AlertTriangle;
  const titleColor = level === 'urgent' ? '#FCA5A5' : level === 'caution' ? '#FBBF24' : '#4ADE80';
  return (
    <div className={`safety-callout ${level}`}>
      <Ico />
      <div>
        {title && <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 2, color: titleColor }}>{title}</div>}
        <p>{children}</p>
      </div>
    </div>
  );
}

export function SafetyBanner({ level, title, reason, escalation }: { level: SafetyLevel; title: string; reason?: string; escalation?: string }) {
  if (level !== 'urgent') return null;
  return (
    <div className="safety-banner">
      <div className="safety-banner-pulse" />
      <AlertTriangle size={18} style={{ color: '#FCA5A5', flexShrink: 0 }} />
      <div className="grow">
        <div className="fw-600 text-sm" style={{ color: '#FECACA' }}>{title}</div>
        {reason && <div className="text-xs" style={{ color: '#FCA5A5', marginTop: 1 }}>{reason}</div>}
      </div>
      {escalation && <div className="text-xs" style={{ color: '#FCA5A5', textAlign: 'right', maxWidth: 320 }}>{escalation}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Metric tile + diagnosis row + timeline item
// ─────────────────────────────────────────────────────────────────────

export function MetricTile({ label, value, sub, icon: Icon, iconColor }: { label: string; value: ReactNode; sub?: ReactNode; icon?: LucideIcon; iconColor?: string }) {
  return (
    <div className="metric-tile">
      <div className="metric-tile-header">
        <span className="metric-tile-label">{label}</span>
        {Icon && <Icon size={14} style={{ color: iconColor || 'var(--fg-2)' }} />}
      </div>
      <div className="metric-value">{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

export function DxRow({ rank, name, source, confidence, barColor = '#22D3EE' }: { rank: number; name: string; source?: string; confidence: number; barColor?: string }) {
  return (
    <div className="dx-row">
      <span className="dx-rank">#{rank}</span>
      <div className="dx-body">
        <div className="dx-top">
          <span className="dx-name">{name}</span>
          {source && <span className="dx-src">{source}</span>}
        </div>
        <div className="dx-bar-row">
          <div className="dx-bar">
            <div className="dx-fill" style={{ width: `${confidence}%`, background: barColor }} />
          </div>
          <span className="dx-pct" style={{ color: barColor }}>{confidence}%</span>
        </div>
      </div>
    </div>
  );
}

export function TimelineItem({ agent, time, event, text }: { agent: string; time?: string; event?: string; text: ReactNode }) {
  const a = AGENTS[resolveAgent(agent)];
  return (
    <div className="timeline-item">
      <div className="timeline-dot" style={{ borderColor: a.color, background: a.color }} />
      <div className="timeline-header">
        <span className="timeline-name" style={{ color: a.color }}>{a.name}</span>
        {time && <span className="timeline-time">{time}</span>}
        {event && <span className="timeline-evt">{event}</span>}
      </div>
      <div className="timeline-text">{text}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Chat bubbles
// ─────────────────────────────────────────────────────────────────────

export function UserBubble({ children, time }: { children: ReactNode; time?: string }) {
  return (
    <div className="bubble-row right anim-in">
      <div>
        <div className="bubble user">{children}</div>
        {time && <div className="bubble-meta right">{time}</div>}
      </div>
    </div>
  );
}

export function AgentBubble({ kind, children, time, streaming = false }: { kind: string; children: ReactNode; time?: string; streaming?: boolean }) {
  return (
    <div className="bubble-row anim-in">
      <div>
        <div className="bubble-agent"><AgentPill kind={kind} /></div>
        <div className="bubble">
          {children}
          {streaming && <span className="stream-cursor">▋</span>}
        </div>
        {time && <div className="bubble-meta">{time}</div>}
      </div>
    </div>
  );
}

// Re-export icons commonly used from pages so callers don't re-import
export {
  Activity, AlertTriangle, ArrowRight, BookOpen, Check, Clock,
  Database, Filter, MessageSquare, RefreshCw, Search, Send, Settings,
  Shield, ShieldAlert, Sparkles, Stethoscope, Target, Trash2, User,
  Users, Wrench, X, Zap, GitBranch, LayoutDashboard, BarChart3,
  Workflow, ChevronDown, ChevronRight, Bell, Plus,
};
