import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Clock, CheckCircle2, Ticket as TicketIcon, PlusCircle } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { getApiError, ticketsApi, type DashboardSummary } from '@/lib/api';

export const DashboardPage: React.FC = () => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    ticketsApi.summary().then((response) => setSummary(response.data)).catch((requestError) => setError(getApiError(requestError)));
  }, []);

  const stats = [
    { label: 'Total Tickets', value: summary?.total_tickets ?? 0, icon: TicketIcon, color: 'text-primary' },
    { label: 'Open Tickets', value: summary?.open_tickets ?? 0, icon: Clock, color: 'text-amber-500' },
    { label: 'Resolved Tickets', value: summary?.resolved_tickets ?? 0, icon: CheckCircle2, color: 'text-emerald-500' },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Campus Operations Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-1">Your current campus grievance activity.</p>
        </div>
        <Link to="/tickets/new"><Button className="gap-2"><PlusCircle className="h-4 w-4" /> Submit New Complaint</Button></Link>
      </div>

      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return <Card key={stat.label}><CardContent className="p-6 flex items-center justify-between"><div className="space-y-1"><p className="text-xs font-medium text-muted-foreground">{stat.label}</p><p className="text-2xl font-bold">{stat.value}</p></div><div className={`p-3 rounded-xl bg-muted ${stat.color}`}><Icon className="h-6 w-6" /></div></CardContent></Card>;
        })}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between"><div><CardTitle className="text-lg font-bold">Recent Tickets</CardTitle><CardDescription>Latest tickets visible to your account.</CardDescription></div><Badge variant="outline">Live</Badge></div>
        </CardHeader>
        <CardContent>
          {!summary && !error && <p className="py-10 text-center text-sm text-muted-foreground">Loading tickets...</p>}
          {summary && summary.recent_tickets.length === 0 && <div className="text-center py-10 border border-dashed rounded-lg text-muted-foreground"><TicketIcon className="h-10 w-10 mx-auto mb-3" /><p className="text-sm">No tickets yet.</p></div>}
          <div className="space-y-3">{summary?.recent_tickets.map((ticket) => <Link key={ticket.id} to={`/tickets/${ticket.ticket_number}`} className="block rounded-lg border p-4 hover:border-primary/50"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-mono text-xs font-bold text-primary">{ticket.ticket_number}</span><Badge variant={ticket.status === 'RESOLVED' || ticket.status === 'CLOSED' ? 'success' : 'warning'}>{ticket.status}</Badge></div><p className="mt-2 font-semibold">{ticket.title}</p><p className="text-xs text-muted-foreground mt-1">{ticket.category} | {ticket.priority} | {ticket.location}</p></Link>)}</div>
        </CardContent>
      </Card>
    </div>
  );
};
