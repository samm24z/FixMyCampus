import React, { useEffect, useState } from 'react';
import { ArrowLeft, Clock, MapPin, User, Building2, FileText, Send, RotateCcw } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CATEGORY_OPTIONS, getApiError, ticketsApi, authApi, type TicketDetail, type TicketStatus, type User as AppUser } from '@/lib/api';
import { useAuth } from '@/lib/auth';

const statuses: TicketStatus[] = ['NEW', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'REOPENED', 'CLOSED'];

export const TicketDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [staff, setStaff] = useState<AppUser[]>([]);
  const [departments, setDepartments] = useState<import('@/lib/api').Department[]>([]);
  const [comment, setComment] = useState('');
  const [status, setStatus] = useState<TicketStatus>('NEW');
  const [category, setCategory] = useState('Other');
  const [priority, setPriority] = useState<TicketDetail['priority']>('MEDIUM');
  const [assignee, setAssignee] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  async function loadTicket() {
    if (!id) return;
    setIsLoading(true);
    try {
      const response = await ticketsApi.detail(id);
      setTicket(response.data);
      setStatus(response.data.status);
      setCategory(response.data.category);
      setPriority(response.data.priority);
      setAssignee(response.data.assigned_to || '');
      setDepartmentId(response.data.confirmed_department_id || '');
    } catch (requestError) {
      setError(getApiError(requestError, 'Ticket could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => { void loadTicket(); }, [id]);
  useEffect(() => {
    if (user?.role === 'COORDINATOR' || user?.role === 'ADMIN') {
      authApi.staffDirectory().then((response) => setStaff(response.data)).catch(() => undefined);
      authApi.departmentDirectory().then((response) => setDepartments(response.data)).catch(() => undefined);
    }
  }, [user?.role]);

  async function perform(action: () => Promise<unknown>) {
    setError('');
    setIsSaving(true);
    try {
      await action();
      await loadTicket();
    } catch (requestError) {
      setError(getApiError(requestError));
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) return <p className="py-16 text-center text-sm text-muted-foreground">Loading ticket...</p>;
  if (!ticket) return <div className="space-y-4"><p className="text-sm text-destructive">{error || 'Ticket not found.'}</p><Button variant="outline" onClick={() => navigate('/tickets')}>Back to Tickets</Button></div>;

  const canTriage = user?.role === 'COORDINATOR' || user?.role === 'ADMIN';
  const canStaffUpdate = user?.role === 'STAFF' && ticket.assigned_to === user.id;
  const canReopen = (user?.role === 'STUDENT' || user?.role === 'FACULTY') && ticket.created_by === user.id && ['RESOLVED', 'CLOSED'].includes(ticket.status);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/tickets')}><ArrowLeft className="h-4 w-4" /> Back to Tickets</Button>
      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <div><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2.5 py-1 rounded-md">{ticket.ticket_number}</span><Badge variant={ticket.status === 'RESOLVED' || ticket.status === 'CLOSED' ? 'success' : 'warning'}>{ticket.status}</Badge><Badge variant={ticket.priority === 'CRITICAL' ? 'destructive' : 'outline'}>{ticket.priority}</Badge></div><h1 className="text-2xl sm:text-3xl font-bold mt-2">{ticket.title}</h1></div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <Card><CardHeader><CardTitle className="text-base font-bold flex items-center gap-2"><FileText className="h-4 w-4 text-primary" /> Complaint Details</CardTitle></CardHeader><CardContent className="space-y-4 text-sm"><p className="text-muted-foreground leading-relaxed">{ticket.description}</p><div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground pt-2 border-t"><span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-primary" /> {ticket.location}</span><span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5 text-primary" /> {new Date(ticket.created_at).toLocaleString()}</span></div></CardContent></Card>
          <Card className="border-indigo-500/30 bg-indigo-50/20 dark:bg-indigo-950/10"><CardHeader><CardTitle className="text-base font-bold text-indigo-600 dark:text-indigo-400">AI analysis pending</CardTitle><CardDescription>No AI output has been generated for this ticket.</CardDescription></CardHeader></Card>

          {canTriage && <Card><CardHeader><CardTitle className="text-base font-bold">Coordinator Controls</CardTitle></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2"><label className="text-xs font-medium">Category<select value={category} onChange={(event) => setCategory(event.target.value)} className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm">{CATEGORY_OPTIONS.map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-xs font-medium">Priority<select value={priority} onChange={(event) => setPriority(event.target.value as TicketDetail['priority'])} className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm">{['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-xs font-medium">Status<select value={status} onChange={(event) => setStatus(event.target.value as TicketStatus)} className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm">{statuses.map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-xs font-medium">Department<select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)} className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"><option value="">Unassigned</option>{departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}</select></label><label className="text-xs font-medium">Assign staff<select value={assignee} onChange={(event) => setAssignee(event.target.value)} className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"><option value="">Unassigned</option>{staff.map((member) => <option key={member.id} value={member.id}>{member.full_name}</option>)}</select></label><Button className="sm:col-span-2" disabled={isSaving} onClick={() => perform(async () => { await ticketsApi.update(ticket.ticket_number, { category, priority, status }); if (assignee) await ticketsApi.assign(ticket.ticket_number, assignee, departmentId || null); })}>{isSaving ? 'Saving...' : 'Save Ticket Changes'}</Button></CardContent></Card>}
          {canStaffUpdate && <Card><CardHeader><CardTitle className="text-base font-bold">Staff Update</CardTitle></CardHeader><CardContent className="flex flex-wrap items-end gap-3"><label className="text-xs font-medium">Status<select value={status} onChange={(event) => setStatus(event.target.value as TicketStatus)} className="mt-1 rounded-lg border bg-background px-3 py-2 text-sm">{statuses.map((item) => <option key={item}>{item}</option>)}</select></label><Button disabled={isSaving} onClick={() => perform(() => ticketsApi.update(ticket.ticket_number, { status }))}>{isSaving ? 'Saving...' : 'Update Status'}</Button></CardContent></Card>}

          <Card><CardHeader><CardTitle className="text-base font-bold">Comments</CardTitle></CardHeader><CardContent className="space-y-4"><div className="space-y-3">{ticket.comments.length === 0 && <p className="text-sm text-muted-foreground">No comments yet.</p>}{ticket.comments.map((item) => <div key={item.id} className="rounded-lg border p-3"><p className="text-sm">{item.content}</p><p className="mt-2 text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p></div>)}</div><div className="flex gap-2"><input value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add a comment" className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm" /><Button size="icon" disabled={!comment.trim() || isSaving} onClick={() => perform(async () => { await ticketsApi.comment(ticket.ticket_number, comment); setComment(''); })}><Send className="h-4 w-4" /></Button></div></CardContent></Card>
        </div>

        <div className="space-y-6"><Card><CardHeader><CardTitle className="text-base font-bold">Metadata</CardTitle></CardHeader><CardContent className="space-y-4 text-xs"><div><span className="text-muted-foreground block">Reporter</span><span className="font-medium flex items-center gap-1 mt-0.5"><User className="h-3.5 w-3.5 text-primary" /> {ticket.created_by_name}</span></div><div><span className="text-muted-foreground block">Department</span><span className="font-medium flex items-center gap-1 mt-0.5"><Building2 className="h-3.5 w-3.5 text-primary" /> {ticket.department_name || 'Not assigned'}</span></div><div><span className="text-muted-foreground block">Assignment</span><span className="font-medium mt-0.5 block">{ticket.assigned_to_name || 'Unassigned'}</span></div></CardContent></Card>
          <Card><CardHeader><CardTitle className="text-base font-bold">Timeline</CardTitle></CardHeader><CardContent className="space-y-3">{ticket.history.length === 0 && <p className="text-xs text-muted-foreground">No status history.</p>}{ticket.history.map((item) => <div key={item.id} className="border-l-2 border-primary/30 pl-3"><p className="text-xs font-semibold">{item.to_status}</p><p className="text-[11px] text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p></div>)}</CardContent></Card>
          {canReopen && <Button variant="outline" className="w-full gap-2" disabled={isSaving} onClick={() => perform(() => ticketsApi.reopen(ticket.ticket_number))}><RotateCcw className="h-4 w-4" /> Request Reopen</Button>}
        </div>
      </div>
    </div>
  );
};
