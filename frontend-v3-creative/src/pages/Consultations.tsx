/**
 * Consultations — list view, MediChain Design System port.
 *
 * Uses the design bundle's table pattern:
 *   ID · Chief Complaint · Safety · Status · Working DDx · Agents · Started · Open
 *
 * Live wiring:
 *   - GET /sessions for the list (already the existing behaviour).
 *   - POST /sessions on "New Consultation" to mint a session, then
 *     navigate into it (the WebSocket handshake in SessionDetail kicks
 *     the Interviewer off).
 *   - DELETE /sessions/:id with an inline confirm modal for trash rows.
 */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { AlertTriangle, Filter, Plus, Search, Trash2 } from 'lucide-react';
import { createSession, deleteSession, getSessions } from '@/services/api';
import { toast } from '@/hooks/use-toast';
import type { Session } from '@/types/medichain';
import {
  AgentPill, Badge, Button, ArrowRight, safetyFromFlag,
} from '@/components/medichain/primitives';

export default function Consultations() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [search, setSearch] = useState('');
  const [flagFilter, setFlagFilter] = useState(false);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    getSessions()
      .then(setSessions)
      .catch(err => {
        // Surface backend failures instead of silently rendering an empty list.
        // The empty-state UI looks the same as "no sessions yet", which would
        // mislead a tester who has the backend down.
        toast({
          variant: 'destructive',
          title: 'Failed to load sessions',
          description: err instanceof Error ? err.message : 'Backend unreachable',
        });
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => sessions.filter(s => {
    const q = search.toLowerCase();
    const matchSearch = !q
      || s.title.toLowerCase().includes(q)
      || (s.preliminary_diagnosis?.toLowerCase().includes(q) ?? false);
    const matchFlag = !flagFilter || (s.safety_flags?.length ?? 0) > 0;
    return matchSearch && matchFlag;
  }), [sessions, search, flagFilter]);

  const onCreate = async () => {
    setCreating(true);
    setCreateError(null);
    try {
      // createSession is (title, llm_model) — positional, not an object.
      const s = await createSession('New Consultation', 'kimi');
      navigate(`/session/${s.id}`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create session');
    } finally {
      setCreating(false);
    }
  };

  const onDelete = async (id: string) => {
    try {
      await deleteSession(id);
      setSessions(prev => prev.filter(s => s.id !== id));
    } catch (err) {
      console.error('delete failed', err);
    }
    setDeleteId(null);
  };

  return (
    <div className="page">
      <div className="page-header hstack">
        <div className="grow">
          <h1>Consultations</h1>
          <div className="sub">{filtered.length} session{filtered.length === 1 ? '' : 's'} · across all users and timeframes</div>
        </div>
        <div className="input" style={{ width: 280 }}>
          <Search size={14} style={{ color: 'var(--fg-2)' }} />
          <input placeholder="Search sessions..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <Button variant={flagFilter ? 'primary' : 'secondary'} icon={Filter} onClick={() => setFlagFilter(v => !v)}>
          {flagFilter ? 'Flagged only' : 'Filter'}
        </Button>
        <Button variant="primary" icon={Plus} onClick={onCreate} disabled={creating}>
          {creating ? 'Creating…' : 'New Consultation'}
        </Button>
      </div>

      {createError && (
        <div className="safety-callout urgent" style={{ marginBottom: 12 }}>
          <AlertTriangle />
          <div><p>Could not create session: {createError}</p></div>
        </div>
      )}

      <div className="card" style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 24 }} className="text-sm muted">Loading sessions…</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 110 }}>ID</th>
                <th>Chief Complaint</th>
                <th style={{ width: 90 }}>Safety</th>
                <th style={{ width: 100 }}>Status</th>
                <th>Working DDx</th>
                <th style={{ width: 160 }}>Agents</th>
                <th style={{ width: 160 }}>Started</th>
                <th style={{ width: 60 }} />
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: 24, textAlign: 'center' }} className="muted">
                    No sessions match your filters.
                  </td>
                </tr>
              ) : filtered.map(s => {
                const flag = (s.safety_flags ?? [])[0];
                const safety = safetyFromFlag(flag);
                const badgeVar = s.status === 'active' ? 'primary' : s.status === 'completed' ? 'success' : 'neutral';
                const started = (() => {
                  try { return format(new Date(s.created_at), 'MMM d, h:mm a'); }
                  catch { return s.created_at; }
                })();
                return (
                  <tr key={s.id} className="row-clickable" onClick={() => navigate(`/session/${s.id}`)}>
                    <td className="mono muted">{s.id.slice(0, 8)}</td>
                    <td><div className="fw-500" style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title || '(untitled)'}</div></td>
                    <td>{flag ? <Badge variant={safety === 'urgent' ? 'danger' : safety === 'caution' ? 'warning' : 'success'}>{flag}</Badge> : <span className="muted">—</span>}</td>
                    <td><Badge variant={badgeVar}>{s.status}</Badge></td>
                    <td className="muted">{s.preliminary_diagnosis ?? '—'}</td>
                    <td>
                      <div className="hstack" style={{ gap: 4, flexWrap: 'wrap' }}>
                        {(s.agent_participation ?? []).slice(0, 3).map(a => <AgentPill key={a as string} kind={a as string} />)}
                        {(s.agent_participation?.length ?? 0) > 3 && <span className="text-xs muted mono">+{(s.agent_participation?.length ?? 0) - 3}</span>}
                      </div>
                    </td>
                    <td className="mono text-xs muted">{started}</td>
                    <td onClick={e => e.stopPropagation()} style={{ textAlign: 'right' }}>
                      <button
                        className="btn btn-ghost btn-icon"
                        onClick={() => setDeleteId(s.id)}
                        title="Delete session"
                        style={{ color: 'var(--danger-bright)' }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {deleteId && (
        <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) setDeleteId(null); }}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <div className="text-lg fw-600">Delete this consultation?</div>
                <div className="sub">Messages and agent logs will be permanently removed.</div>
              </div>
              <button className="btn btn-ghost btn-icon" onClick={() => setDeleteId(null)}><ArrowRight size={14} style={{ transform: 'rotate(45deg)' }} /></button>
            </div>
            <div className="modal-foot">
              <div />
              <div className="hstack gap-sm">
                <Button variant="ghost" onClick={() => setDeleteId(null)}>Cancel</Button>
                <Button variant="destructive" icon={Trash2} onClick={() => onDelete(deleteId)}>Delete</Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
