import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { UserCheck, Clock, Wrench, ArrowUpRight } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';
import { getApiError, ticketsApi, type DashboardSummary, type Paginated, type Ticket } from '@/lib/api';

export const StaffPage: React.FC = () => {
  const { user } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [queue, setQueue] = useState<Paginated<Ticket> | null>(null);
  const [mineOnly, setMineOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');

  useEffect(() => {
    ticketsApi.summary().then((response) => setSummary(response.data)).catch((requestError) => setError(getApiError(requestError)));
  }, []);

  useEffect(() => {
    ticketsApi
      .list({ open_only: true, assigned_to: mineOnly ? user?.id : undefined, page, page_size: 10 })
      .then((response) => setQueue(response.data))
      .catch((requestError) => setError(getApiError(requestError)));
  }, [mineOnly, page, user?.id]);

  const tickets = queue?.items ?? [];
  const unassigned = summary?.by_status.NEW ?? 0;
  return (
    <div className="space-y-6">
      <div><div className="flex items-center gap-2"><h1 className="text-3xl font-bold tracking-tight">{user?.role === 'STAFF' ? 'Staff Resolution Workbench' : 'Triage Desk'}</h1><Badge variant="outline">Live</Badge></div><p className="text-muted-foreground text-sm mt-1">Assigned and department tickets requiring action.</p></div>
      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card><CardContent className="p-5 flex items-center justify-between"><div><span className="text-xs text-muted-foreground">Open Tickets</span><p className="text-2xl font-bold">{summary?.open_tickets ?? 0}</p></div><Wrench className="h-6 w-6 text-amber-500" /></CardContent></Card>
        <Card><CardContent className="p-5 flex items-center justify-between"><div><span className="text-xs text-muted-foreground">New (untriaged)</span><p className="text-2xl font-bold">{unassigned}</p></div><Clock className="h-6 w-6 text-indigo-500" /></CardContent></Card>
        <Card><CardContent className="p-5 flex items-center justify-between"><div><span className="text-xs text-muted-foreground">Resolved</span><p className="text-2xl font-bold">{summary?.resolved_tickets ?? 0}</p></div><UserCheck className="h-6 w-6 text-emerald-500" /></CardContent></Card>
      </div>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3"><div><CardTitle className="text-lg font-bold">Active Resolution Queue</CardTitle><CardDescription>Open tickets available to your role.</CardDescription></div>
            <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={mineOnly} onChange={(event) => { setMineOnly(event.target.checked); setPage(1); }} /> Assigned to me</label></div>
        </CardHeader>
        <CardContent className="space-y-3">
          {tickets.length === 0 && <p className="py-10 text-center text-sm text-muted-foreground">No active tickets.</p>}
          {tickets.map((ticket) => <Link key={ticket.id} to={`/tickets/${ticket.ticket_number}`} className="flex items-center justify-between gap-3 rounded-lg border p-4 hover:border-primary/50"><div><p className="font-mono text-xs text-primary">{ticket.ticket_number}</p><p className="font-semibold mt-1">{ticket.title}</p><p className="text-xs text-muted-foreground mt-1">{ticket.category} | {ticket.priority} | {ticket.status}</p></div><ArrowUpRight className="h-4 w-4 shrink-0" /></Link>)}
          {queue && queue.total_pages > 1 && <div className="flex items-center justify-between pt-2 text-sm text-muted-foreground"><span>Page {queue.page} of {queue.total_pages}</span><div className="flex gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={page >= queue.total_pages} onClick={() => setPage(page + 1)}>Next</Button></div></div>}
        </CardContent>
      </Card>
    </div>
  );
};
