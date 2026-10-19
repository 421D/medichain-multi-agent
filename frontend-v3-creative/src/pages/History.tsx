import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, Inbox } from 'lucide-react';
import { getSessions } from '@/services/api';
import { toast } from '@/hooks/use-toast';
import type { Session } from '@/types/medichain';
import { format } from 'date-fns';

export default function History() {
  const [sessions, setSessions] = useState<Session[]>([]);
  // M23 + M26 fix: loading state to prevent empty state flash
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    getSessions()
      .then(all => setSessions(all.filter(s => s.status === 'completed')))
      .catch(err => {
        // Don't silently render the empty-state — that would mislead a tester
        // with the backend down into thinking there's just no history yet.
        toast({
          variant: 'destructive',
          title: 'Failed to load history',
          description: err instanceof Error ? err.message : 'Backend unreachable',
        });
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">History</h1>
          <p className="text-sm text-muted-foreground">Completed consultation archive</p>
        </div>
        <div className="flex items-center justify-center py-12 text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">History</h1>
          <p className="text-sm text-muted-foreground">Completed consultation archive</p>
        </div>
        <div className="bg-card border border-border rounded-lg p-16 flex flex-col items-center text-center">
          <Inbox className="w-12 h-12 text-muted-foreground mb-4" />
          <h3 className="font-semibold mb-1">No completed sessions</h3>
          <p className="text-sm text-muted-foreground">Completed consultations will appear here</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">History</h1>
        <p className="text-sm text-muted-foreground">Completed consultation archive</p>
      </div>

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="px-4 py-3 text-xs text-muted-foreground uppercase tracking-wide font-medium">Date</th>
              <th className="px-4 py-3 text-xs text-muted-foreground uppercase tracking-wide font-medium">Title</th>
              <th className="px-4 py-3 text-xs text-muted-foreground uppercase tracking-wide font-medium">Diagnosis</th>
              <th className="px-4 py-3 text-xs text-muted-foreground uppercase tracking-wide font-medium">Confidence</th>
              <th className="px-4 py-3 text-xs text-muted-foreground uppercase tracking-wide font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map(s => (
              <tr key={s.id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3 text-xs text-muted-foreground">{format(new Date(s.created_at), 'MMM d, yyyy')}</td>
                <td className="px-4 py-3 font-medium">{s.title}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{s.preliminary_diagnosis || '—'}</td>
                <td className="px-4 py-3">
                  {s.confidence_score != null ? (
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                        <div className="h-full bg-primary rounded-full" style={{ width: `${s.confidence_score * 100}%` }} />
                      </div>
                      <span className="text-xs text-muted-foreground">{Math.round(s.confidence_score * 100)}%</span>
                    </div>
                  ) : '—'}
                </td>
                <td className="px-4 py-3">
                  <button onClick={() => navigate(`/session/${s.id}`)} className="p-1.5 rounded hover:bg-muted transition-colors" title="View details">
                    <Eye className="w-3.5 h-3.5 text-muted-foreground" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
