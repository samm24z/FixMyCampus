import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { UserCheck, Clock, Wrench, ArrowUpRight } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { getApiError, ticketsApi, type Ticket } from '@/lib/api';

export const StaffPage: React.FC = () => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    ticketsApi.list().then((response) => setTickets(response.data)).catch((requestError) => setError(getApiError(requestError)));
  }, []);

  const active = tickets.filter((ticket) => !['RESOLVED', 'CLOSED'].includes(ticket.status));
  return (
    <div className="space-y-6">
      <div><div className="flex items-center gap-2"><h1 className="text-3xl font-bold tracking-tight">Staff Resolution Workbench</h1><Badge variant="outline">Live</Badge></div><p className="text-muted-foreground text-sm mt-1">Assigned and department tickets requiring action.</p></div>
      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4"><Card><CardContent className="p-5 flex items-center justify-between"><div><span className="text-xs text-muted-foreground">Visible Tickets</span><p className="text-2xl font-bold">{tickets.length}</p></div><Wrench className="h-6 w-6 text-amber-500" /></CardContent></Card><Card><CardContent className="p-5 flex items-center justify-between"><div><span className="text-xs text-muted-foreground">Active Queue</span><p className="text-2xl font-bold">{active.length}</p></div><Clock className="h-6 w-6 text-indigo-500" /></CardContent></Card><Card><CardContent className="p-5 flex items-center justify-between"><div><span className="text-xs text-muted-foreground">Resolved</span><p className="text-2xl font-bold">{tickets.length - active.length}</p></div><UserCheck className="h-6 w-6 text-emerald-500" /></CardContent></Card></div>
      <Card><CardHeader><CardTitle className="text-lg font-bold">Active Resolution Queue</CardTitle><CardDescription>Open tickets available to your role.</CardDescription></CardHeader><CardContent className="space-y-3">{active.length === 0 && <p className="py-10 text-center text-sm text-muted-foreground">No active tickets.</p>}{active.map((ticket) => <Link key={ticket.id} to={`/tickets/${ticket.ticket_number}`} className="flex items-center justify-between gap-3 rounded-lg border p-4 hover:border-primary/50"><div><p className="font-mono text-xs text-primary">{ticket.ticket_number}</p><p className="font-semibold mt-1">{ticket.title}</p><p className="text-xs text-muted-foreground mt-1">{ticket.category} | {ticket.priority} | {ticket.status}</p></div><ArrowUpRight className="h-4 w-4 shrink-0" /></Link>)}</CardContent></Card>
    </div>
  );
};
