import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Ticket as TicketIcon, Search, Plus, ArrowUpRight, Clock } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { getApiError, ticketsApi, type Paginated, type Ticket, type TicketStatus } from '@/lib/api';

const STATUSES: TicketStatus[] = ['NEW', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'REOPENED', 'CLOSED'];

function priorityVariant(priority: Ticket['priority']) {
  if (priority === 'CRITICAL') return 'destructive' as const;
  if (priority === 'HIGH') return 'warning' as const;
  return 'secondary' as const;
}

export const TicketsPage: React.FC = () => {
  const navigate = useNavigate();
  const [result, setResult] = useState<Paginated<Ticket> | null>(null);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [status, setStatus] = useState<TicketStatus | ''>('');
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setIsLoading(true);
    setError('');
    ticketsApi.list({ search: debouncedSearch, status, page, page_size: 10 })
      .then((response) => setResult(response.data))
      .catch((requestError) => setError(getApiError(requestError)))
      .finally(() => setIsLoading(false));
  }, [debouncedSearch, status, page]);

  const tickets = result?.items ?? [];
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4"><div><h1 className="text-3xl font-bold tracking-tight">Campus Tickets</h1><p className="text-muted-foreground text-sm mt-1">Live tickets visible to your account.</p></div><Button className="gap-2" onClick={() => navigate('/tickets/new')}><Plus className="h-4 w-4" /> Create Ticket</Button></div>
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1"><Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><input value={search} onChange={(event) => setSearch(event.target.value)} type="search" placeholder="Search tickets by keyword, location, ID..." className="w-full pl-9 pr-4 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary" /></div>
        <select value={status} onChange={(event) => { setStatus(event.target.value as TicketStatus | ''); setPage(1); }} className="rounded-lg border bg-background px-3 py-2 text-sm" aria-label="Filter by status"><option value="">All statuses</option>{STATUSES.map((item) => <option key={item}>{item}</option>)}</select>
      </div>
      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      {isLoading && <p className="py-10 text-center text-sm text-muted-foreground">Loading tickets...</p>}
      {!isLoading && !error && tickets.length === 0 && <div className="rounded-lg border border-dashed py-16 text-center text-muted-foreground"><TicketIcon className="mx-auto h-10 w-10 mb-3" /><p className="text-sm">No tickets found.</p></div>}
      <div className="grid gap-4">{tickets.map((ticket) => <Card key={ticket.id} className="hover:border-primary/50 transition-all"><CardContent className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4"><div className="space-y-2"><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">{ticket.ticket_number}</span><Badge variant="outline">{ticket.category}</Badge><Badge variant={priorityVariant(ticket.priority)}>{ticket.priority}</Badge><span className="text-xs text-muted-foreground flex items-center gap-1"><Clock className="h-3 w-3" /> {new Date(ticket.created_at).toLocaleString()}</span></div><h3 className="font-semibold text-base">{ticket.title}</h3><p className="text-xs text-muted-foreground">Location: <span className="font-medium text-foreground">{ticket.location}</span></p></div><div className="flex items-center gap-3"><Badge variant={ticket.status === 'RESOLVED' || ticket.status === 'CLOSED' ? 'success' : 'warning'}>{ticket.status}</Badge><Link to={`/tickets/${ticket.ticket_number}`}><Button variant="outline" size="sm" className="gap-1">View <ArrowUpRight className="h-3.5 w-3.5" /></Button></Link></div></CardContent></Card>)}</div>
      {result && result.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{result.total} tickets - page {result.page} of {result.total_pages}</span>
          <div className="flex gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={page >= result.total_pages} onClick={() => setPage(page + 1)}>Next</Button></div>
        </div>
      )}
    </div>
  );
};
