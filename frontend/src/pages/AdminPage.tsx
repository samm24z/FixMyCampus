import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Ticket as TicketIcon, ArrowUpRight } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { getApiError, ticketsApi, type Ticket } from '@/lib/api';

export const AdminPage: React.FC = () => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { ticketsApi.list().then((response) => setTickets(response.data)).catch((requestError) => setError(getApiError(requestError))); }, []);
  const resolved = tickets.filter((ticket) => ['RESOLVED', 'CLOSED'].includes(ticket.status)).length;
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2"><h1 className="text-3xl font-bold tracking-tight">System Administration</h1><Badge variant="destructive">Admin Access</Badge></div>
      <p className="text-muted-foreground text-sm">Basic live ticket overview for administrators.</p>
      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4"><Card><CardContent className="p-5"><p className="text-xs text-muted-foreground">All Tickets</p><p className="text-2xl font-bold">{tickets.length}</p></CardContent></Card><Card><CardContent className="p-5"><p className="text-xs text-muted-foreground">Open Tickets</p><p className="text-2xl font-bold">{tickets.length - resolved}</p></CardContent></Card><Card><CardContent className="p-5"><p className="text-xs text-muted-foreground">Resolved Tickets</p><p className="text-2xl font-bold">{resolved}</p></CardContent></Card></div>
      <Card><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" /> Ticket Overview</CardTitle><CardDescription>All tickets currently stored in the backend.</CardDescription></CardHeader><CardContent className="space-y-3">{tickets.length === 0 && <div className="py-10 text-center text-sm text-muted-foreground"><TicketIcon className="mx-auto mb-3 h-10 w-10" />No tickets available.</div>}{tickets.map((ticket) => <Link key={ticket.id} to={`/tickets/${ticket.ticket_number}`} className="flex items-center justify-between gap-3 rounded-lg border p-4 hover:border-primary/50"><div><p className="font-mono text-xs text-primary">{ticket.ticket_number}</p><p className="font-semibold mt-1">{ticket.title}</p><p className="text-xs text-muted-foreground mt-1">{ticket.category} | {ticket.priority} | {ticket.status}</p></div><ArrowUpRight className="h-4 w-4" /></Link>)}</CardContent></Card>
    </div>
  );
};
