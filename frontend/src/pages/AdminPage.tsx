import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, ShieldCheck, Ticket as TicketIcon } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { UserManagement } from '@/components/admin/UserManagement';
import { getApiError, ticketsApi, type DashboardSummary, type Paginated, type Ticket, type TicketStatus } from '@/lib/api';
import { STATUSES, isDone, priorityVariant, statusVariant } from '@/lib/tickets';

const chipClass = (active: boolean) =>
  `rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${active ? 'border-primary bg-primary text-primary-foreground' : 'hover:border-primary/50'}`;

export const AdminPage: React.FC = () => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [result, setResult] = useState<Paginated<Ticket> | null>(null);
  const [status, setStatus] = useState<TicketStatus | ''>('');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { ticketsApi.summary().then((response) => setSummary(response.data)).catch((requestError) => setError(getApiError(requestError))); }, []);

  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setIsLoading(true);
    ticketsApi.list({ status, search: debouncedSearch, page, page_size: 25 })
      .then((response) => setResult(response.data))
      .catch((requestError) => setError(getApiError(requestError)))
      .finally(() => setIsLoading(false));
  }, [status, debouncedSearch, page]);

  const stats = [
    { label: 'All Tickets', value: summary?.total_tickets ?? 0 },
    { label: 'Open Tickets', value: summary?.open_tickets ?? 0 },
    { label: 'Resolved Tickets', value: summary?.resolved_tickets ?? 0 },
  ];
  const tickets = result?.items ?? [];
  const pickStatus = (next: TicketStatus | '') => { setStatus(next); setPage(1); };
  const isOverdue = (ticket: Ticket) => !!ticket.sla_deadline && !isDone(ticket.status) && new Date(ticket.sla_deadline) < new Date();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2"><h1 className="text-3xl font-bold tracking-tight">System Administration</h1><Badge variant="destructive">Admin Access</Badge></div>
      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{stats.map((stat) => <Card key={stat.label}><CardContent className="p-5"><p className="text-xs text-muted-foreground">{stat.label}</p><p className="text-2xl font-bold">{stat.value}</p></CardContent></Card>)}</div>
      <UserManagement />
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" /> All Tickets</CardTitle><CardDescription>Every ticket across the campus and where it stands. Click a status to filter.</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <button type="button" className={chipClass(status === '')} onClick={() => pickStatus('')}>All {summary?.total_tickets ?? 0}</button>
            {STATUSES.map((item) => <button key={item} type="button" className={chipClass(status === item)} onClick={() => pickStatus(item)}>{item} {summary?.by_status[item] ?? 0}</button>)}
          </div>
          <div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><input value={search} onChange={(event) => setSearch(event.target.value)} type="search" placeholder="Search tickets by keyword, location, ID..." className="w-full pl-9 pr-4 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary" /></div>
          {isLoading && <p className="py-6 text-center text-sm text-muted-foreground">Loading tickets...</p>}
          {!isLoading && tickets.length === 0 && <div className="py-10 text-center text-sm text-muted-foreground"><TicketIcon className="mx-auto mb-3 h-10 w-10" />No tickets found.</div>}
          {tickets.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b text-xs text-muted-foreground"><tr><th className="py-2 pr-3 font-medium">Ticket</th><th className="py-2 pr-3 font-medium">Title</th><th className="py-2 pr-3 font-medium">Category</th><th className="py-2 pr-3 font-medium">Priority</th><th className="py-2 pr-3 font-medium">Status</th><th className="py-2 pr-3 font-medium">SLA deadline</th><th className="py-2 font-medium">Updated</th></tr></thead>
                <tbody>
                  {tickets.map((ticket) => (
                    <tr key={ticket.id} className="border-b last:border-0 hover:bg-muted/40">
                      <td className="py-2 pr-3"><Link to={`/tickets/${ticket.ticket_number}`} className="font-mono text-xs font-bold text-primary hover:underline">{ticket.ticket_number}</Link></td>
                      <td className="py-2 pr-3 font-medium">{ticket.title}</td>
                      <td className="py-2 pr-3 text-muted-foreground">{ticket.category}</td>
                      <td className="py-2 pr-3"><Badge variant={priorityVariant(ticket.priority)}>{ticket.priority}</Badge></td>
                      <td className="py-2 pr-3"><Badge variant={statusVariant(ticket.status)}>{ticket.status}</Badge></td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">{ticket.sla_deadline ? new Date(ticket.sla_deadline).toLocaleString() : '-'}{isOverdue(ticket) && <Badge variant="destructive" className="ml-2">Overdue</Badge>}</td>
                      <td className="py-2 text-xs text-muted-foreground">{new Date(ticket.updated_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {result && result.total_pages > 1 && (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>{result.total} tickets - page {result.page} of {result.total_pages}</span>
              <div className="flex gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={page >= result.total_pages} onClick={() => setPage(page + 1)}>Next</Button></div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
