/**
 * App shell — matches the MediChain Design System layout:
 *   - 236px fixed sidebar with brand, 2-section nav, system-status footer
 *   - Main area: sticky 56px topbar + scrollable page content
 *
 * The design splits nav into "Workspace" (daily-use) and "Analysis"
 * (reports/tools) so high-traffic pages stay near the top and the
 * secondary tools don't compete for attention.
 */
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  Activity, MessageSquare, GitBranch, BarChart3, Clock,
  LayoutDashboard, Wrench, Search, Bell, Settings, Zap,
} from 'lucide-react';
import { StatusDot } from '@/components/medichain/primitives';

type NavItem = { to: string; icon: typeof Activity; label: string };

const WORKSPACE: NavItem[] = [
  { to: '/',              icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/consultations', icon: MessageSquare,   label: 'Consultations' },
  { to: '/flow',          icon: GitBranch,       label: 'Workflow' },
];

const ANALYSIS: NavItem[] = [
  { to: '/tools',      icon: Wrench,     label: 'MCP Tools' },
  { to: '/evaluation', icon: BarChart3,  label: 'Evaluation' },
  { to: '/history',    icon: Clock,      label: 'History' },
];

function Brand() {
  return (
    <div className="sidebar-brand">
      <div className="sidebar-logo"><Activity size={17} /></div>
      <div>
        <div className="sidebar-brand-name">MediChain</div>
        <div className="sidebar-brand-tag">Multi-Agent Diagnostics</div>
      </div>
    </div>
  );
}

function NavList({ items }: { items: NavItem[] }) {
  return (
    <>
      {items.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <Icon size={16} className="nav-icon" />
          <span>{label}</span>
        </NavLink>
      ))}
    </>
  );
}

function Sidebar() {
  return (
    <aside className="sidebar">
      <Brand />
      <div className="sidebar-nav">
        <div className="nav-section">Workspace</div>
        <NavList items={WORKSPACE} />
        <div className="nav-section">Analysis</div>
        <NavList items={ANALYSIS} />
      </div>
      <div className="sidebar-footer">
        <StatusDot kind="online" />
        <span>System online</span>
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 10 }}>v3.0</span>
      </div>
    </aside>
  );
}

// Human-readable title per route, shown in the topbar eyebrow.
const ROUTE_TITLES: Record<string, string> = {
  '/':              'Dashboard',
  '/consultations': 'Consultations',
  '/flow':          'Workflow',
  '/tools':         'MCP Tools',
  '/evaluation':    'Evaluation',
  '/history':       'History',
};

function Topbar() {
  const { pathname } = useLocation();
  const title = pathname.startsWith('/session/') ? 'Session' : (ROUTE_TITLES[pathname] ?? 'MediChain');
  return (
    <div className="topbar">
      <div className="hstack gap-md">
        <div className="eyebrow">{title}</div>
      </div>
      <div className="topbar-right">
        <div className="input topbar-search">
          <Search size={14} style={{ color: 'var(--fg-2)' }} />
          <input placeholder="Search sessions, cases..." />
        </div>
        <button className="btn btn-ghost btn-icon" title="Notifications"><Bell size={16} /></button>
        <button className="btn btn-ghost btn-icon" title="Settings"><Settings size={16} /></button>
        <div className="avatar">W</div>
      </div>
    </div>
  );
}

export default function AppLayout() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Topbar />
        <Outlet />
      </main>
    </div>
  );
}
