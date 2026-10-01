import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Ticket as TicketIcon, ArrowUpRight } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { UserManagement } from '@/components/admin/UserManagement';
import { getApiError, ticketsApi, type DashboardSummary } from '@/lib/api';

export const AdminPage: React.FC = () => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { ticketsApi.summary().then((response) => setSummary(response.data)).catch((requestError) => setError(getApiError(requestError))); }, []);
  const stats = [
    { label: 'All Tickets', value: summary?.total_tickets ?? 0 },
    { label: 'Open Tickets', value: summary?.open_tickets ?? 0 },
    { label: 'Resolved Tickets', value: summary?.resolved_tickets ?? 0 },
  ];
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2"><h1 className="text-3xl font-bold tracking-tight">System Administration</h1><Badge variant="destructive">Admin Access</Badge></div>
      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{stats.map((stat) => <Card key={stat.label}><CardContent className="p-5"><p className="text-xs text-muted-foreground">{stat.label}</p><p className="text-2xl font-bold">{stat.value}</p></CardContent></Card>)}</div>
      <UserManagement />
      <Card><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" /> Recent Tickets</CardTitle><CardDescription>Latest tickets across the campus. Use the Tickets page for full search.</CardDescription></CardHeader><CardContent className="space-y-3">{summary && summary.recent_tickets.length === 0 && <div className="py-10 text-center text-sm text-muted-foreground"><TicketIcon className="mx-auto mb-3 h-10 w-10" />No tickets available.</div>}{summary?.recent_tickets.map((ticket) => <Link key={ticket.id} to={`/tickets/${ticket.ticket_number}`} className="flex items-center justify-between gap-3 rounded-lg border p-4 hover:border-primary/50"><div><p className="font-mono text-xs text-primary">{ticket.ticket_number}</p><p className="font-semibold mt-1">{ticket.title}</p><p className="text-xs text-muted-foreground mt-1">{ticket.category} | {ticket.priority} | {ticket.status}</p></div><ArrowUpRight className="h-4 w-4" /></Link>)}</CardContent></Card>
    </div>
  );
};
