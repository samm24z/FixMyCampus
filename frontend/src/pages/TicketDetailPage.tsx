import React, { useEffect, useState } from 'react';
import { ArrowLeft, Clock, MapPin, User, Building2, FileText, Send, RotateCcw, CalendarClock, CheckCircle2, Star, Undo2 } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  CATEGORY_OPTIONS,
  departmentsApi,
  getApiError,
  ticketsApi,
  usersApi,
  type Department,
  type TicketDetail,
  type TicketPriority,
  type TicketStatus,
  type User as AppUser,
} from '@/lib/api';
import { statusVariant } from '@/lib/tickets';

const PRIORITIES: TicketPriority[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const selectClass = 'mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm';

export const TicketDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [staff, setStaff] = useState<AppUser[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [comment, setComment] = useState('');
  const [isInternal, setIsInternal] = useState(false);
  const [category, setCategory] = useState('');
  const [priority, setPriority] = useState<TicketPriority>('MEDIUM');
  const [assignee, setAssignee] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [nextStatus, setNextStatus] = useState<TicketStatus | ''>('');
  const [remarks, setRemarks] = useState('');
  const [reopenReason, setReopenReason] = useState('');
  const [withdrawReason, setWithdrawReason] = useState('');
  const [rating, setRating] = useState(0);
  const [feedbackComments, setFeedbackComments] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  function applyTicket(next: TicketDetail) {
    setTicket(next);
    setCategory(next.category);
    setPriority(next.priority);
    setAssignee(next.assigned_to || '');
    setDepartmentId(next.confirmed_department_id || '');
    setNextStatus('');
    setRemarks('');
    setRating(next.feedback?.rating ?? 0);
    setFeedbackComments(next.feedback?.comments ?? '');
  }

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    ticketsApi
      .detail(id)
      .then((response) => applyTicket(response.data))
      .catch((requestError) => setError(getApiError(requestError, 'Ticket could not be loaded.')))
      .finally(() => setIsLoading(false));
  }, [id]);

  const canAssign = ticket?.permissions.can_assign;
  useEffect(() => {
    if (!canAssign) return;
    usersApi.staff().then((response) => setStaff(response.data)).catch(() => undefined);
    departmentsApi.list().then((response) => setDepartments(response.data)).catch(() => undefined);
  }, [canAssign]);

  /** Run a mutation; every ticket endpoint returns the refreshed ticket, so no reload is needed. */
  async function perform(action: () => Promise<{ data: TicketDetail }>, onDone?: () => void) {
    setError('');
    setIsSaving(true);
    try {
      applyTicket((await action()).data);
      onDone?.();
    } catch (requestError) {
      setError(getApiError(requestError));
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) return <p className="py-16 text-center text-sm text-muted-foreground">Loading ticket...</p>;
  if (!ticket) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-destructive">{error || 'Ticket not found.'}</p>
        <Button variant="outline" onClick={() => navigate('/tickets')}>Back to Tickets</Button>
      </div>
    );
  }

  const { permissions } = ticket;
  const ref = ticket.ticket_number;
  const remarksRequired = !!nextStatus && permissions.statuses_requiring_remarks.includes(nextStatus);
  const visibleStaff = departmentId ? staff.filter((member) => member.department_id === departmentId) : staff;
  const departmentName = (departmentId: string | null) => departments.find((item) => item.id === departmentId)?.name;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/tickets')}><ArrowLeft className="h-4 w-4" /> Back to Tickets</Button>
      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2.5 py-1 rounded-md">{ticket.ticket_number}</span>
          <Badge variant={statusVariant(ticket.status)}>{ticket.status}</Badge>
          <Badge variant={ticket.priority === 'CRITICAL' ? 'destructive' : 'outline'}>{ticket.priority}</Badge>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold mt-2">{ticket.title}</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base font-bold flex items-center gap-2"><FileText className="h-4 w-4 text-primary" /> Complaint Details</CardTitle></CardHeader>
            <CardContent className="space-y-4 text-sm">
              <p className="text-muted-foreground leading-relaxed">{ticket.description}</p>
              <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground pt-2 border-t">
                <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-primary" /> {ticket.location}</span>
                <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5 text-primary" /> {new Date(ticket.created_at).toLocaleString()}</span>
                {ticket.sla_deadline && <span className="flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5 text-primary" /> SLA due {new Date(ticket.sla_deadline).toLocaleString()}</span>}
              </div>
            </CardContent>
          </Card>

          <Card className="border-indigo-500/30 bg-indigo-50/20 dark:bg-indigo-950/10">
            <CardHeader>
              <CardTitle className="text-base font-bold text-indigo-600 dark:text-indigo-400">AI analysis pending</CardTitle>
              <CardDescription>No AI output has been generated for this ticket.</CardDescription>
            </CardHeader>
          </Card>

          {permissions.can_edit_triage && (
            <Card>
              <CardHeader><CardTitle className="text-base font-bold">Triage</CardTitle><CardDescription>Confirm or correct the classification. Changes recalculate the SLA.</CardDescription></CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-medium">Category
                  <select value={category} onChange={(event) => setCategory(event.target.value)} className={selectClass}>{CATEGORY_OPTIONS.map((item) => <option key={item}>{item}</option>)}</select>
                </label>
                <label className="text-xs font-medium">Priority
                  <select value={priority} onChange={(event) => setPriority(event.target.value as TicketPriority)} className={selectClass}>{PRIORITIES.map((item) => <option key={item}>{item}</option>)}</select>
                </label>
                <Button className="sm:col-span-2" disabled={isSaving || (category === ticket.category && priority === ticket.priority)} onClick={() => perform(() => ticketsApi.triage(ref, { category, priority }))}>Save Triage</Button>
              </CardContent>
            </Card>
          )}

          {permissions.can_assign && (
            <Card>
              <CardHeader><CardTitle className="text-base font-bold">Assignment</CardTitle><CardDescription>Currently: {ticket.assigned_to_name || 'unassigned'}{ticket.department_name ? ` (${ticket.department_name})` : ''}</CardDescription></CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-medium">Department
                  <select value={departmentId} onChange={(event) => { setDepartmentId(event.target.value); setAssignee(''); }} className={selectClass}>
                    <option value="">Staff member's own department</option>
                    {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label className="text-xs font-medium">Staff member
                  <select value={assignee} onChange={(event) => setAssignee(event.target.value)} className={selectClass}>
                    <option value="">Select staff...</option>
                    {visibleStaff.map((member) => <option key={member.id} value={member.id}>{member.full_name}{departmentName(member.department_id) ? ` - ${departmentName(member.department_id)}` : ''}</option>)}
                  </select>
                </label>
                <Button className="sm:col-span-2" disabled={isSaving || !assignee || assignee === ticket.assigned_to} onClick={() => perform(() => ticketsApi.assign(ref, assignee, departmentId || null))}>{ticket.assigned_to ? 'Reassign' : 'Assign'}</Button>
              </CardContent>
            </Card>
          )}

          {permissions.allowed_statuses.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base font-bold">Update Status</CardTitle></CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-medium">Move to
                  <select value={nextStatus} onChange={(event) => setNextStatus(event.target.value as TicketStatus)} className={selectClass}>
                    <option value="">Select status...</option>
                    {permissions.allowed_statuses.map((item) => <option key={item}>{item}</option>)}
                  </select>
                </label>
                <label className="text-xs font-medium">Remarks{remarksRequired ? ' (required)' : ' (optional)'}
                  <input value={remarks} onChange={(event) => setRemarks(event.target.value)} className={selectClass} placeholder="What changed?" />
                </label>
                <Button className="sm:col-span-2" disabled={isSaving || !nextStatus || (remarksRequired && !remarks.trim())} onClick={() => perform(() => ticketsApi.changeStatus(ref, nextStatus as TicketStatus, remarks))}>Update Status</Button>
              </CardContent>
            </Card>
          )}

          {(permissions.can_give_feedback || ticket.feedback) && (
            <Card>
              <CardHeader><CardTitle className="text-base font-bold flex items-center gap-2"><Star className="h-4 w-4 text-primary" /> Resolution Feedback</CardTitle>{permissions.can_give_feedback && <CardDescription>How well was this resolved?</CardDescription>}</CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-1" role="radiogroup" aria-label="Rating">
                  {[1, 2, 3, 4, 5].map((value) => (
                    <button key={value} type="button" role="radio" aria-checked={rating === value} aria-label={`${value} star${value > 1 ? 's' : ''}`} disabled={!permissions.can_give_feedback || isSaving} onClick={() => setRating(value)} className="disabled:cursor-default">
                      <Star className={`h-6 w-6 ${value <= rating ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground'}`} />
                    </button>
                  ))}
                </div>
                {permissions.can_give_feedback ? (
                  <>
                    <textarea value={feedbackComments} onChange={(event) => setFeedbackComments(event.target.value)} maxLength={2000} rows={3} placeholder="Comments (optional)" className="w-full rounded-lg border bg-background px-3 py-2 text-sm" />
                    <Button disabled={isSaving || rating === 0 || (rating === ticket.feedback?.rating && feedbackComments === (ticket.feedback?.comments ?? ''))} onClick={() => perform(() => ticketsApi.submitFeedback(ref, rating, feedbackComments))}>{ticket.feedback ? 'Update Feedback' : 'Submit Feedback'}</Button>
                  </>
                ) : (
                  ticket.feedback?.comments && <p className="text-sm text-muted-foreground">{ticket.feedback.comments}</p>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader><CardTitle className="text-base font-bold">Comments</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                {ticket.comments.length === 0 && <p className="text-sm text-muted-foreground">No comments yet.</p>}
                {ticket.comments.map((item) => (
                  <div key={item.id} className={`rounded-lg border p-3 ${item.is_internal ? 'border-amber-500/40 bg-amber-500/5' : ''}`}>
                    <div className="mb-1 flex items-center gap-2 text-xs font-semibold">
                      {item.author_name || 'Unknown'}
                      {item.author_role && <span className="font-normal text-muted-foreground">{item.author_role}</span>}
                      {item.is_internal && <Badge variant="warning">Internal</Badge>}
                    </div>
                    <p className="text-sm">{item.content}</p>
                    <p className="mt-2 text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p>
                  </div>
                ))}
              </div>
              {permissions.can_comment && (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input value={comment} onChange={(event) => setComment(event.target.value)} placeholder={isInternal ? 'Add an internal note (hidden from the reporter)' : 'Add a comment'} className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm" />
                    <Button size="icon" disabled={!comment.trim() || isSaving} onClick={() => perform(() => ticketsApi.comment(ref, comment, isInternal), () => setComment(''))}><Send className="h-4 w-4" /></Button>
                  </div>
                  {permissions.can_comment_internal && (
                    <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={isInternal} onChange={(event) => setIsInternal(event.target.checked)} /> Internal note (staff only)</label>
                  )}
                </div>
              )}
              {!permissions.can_comment && ticket.status === 'CLOSED' && <p className="text-sm text-muted-foreground">Ticket is closed.</p>}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base font-bold">Metadata</CardTitle></CardHeader>
            <CardContent className="space-y-4 text-xs">
              <div><span className="text-muted-foreground block">Reporter</span><span className="font-medium flex items-center gap-1 mt-0.5"><User className="h-3.5 w-3.5 text-primary" /> {ticket.created_by_name}</span></div>
              <div><span className="text-muted-foreground block">Category</span><span className="font-medium mt-0.5 block">{ticket.category}</span></div>
              <div><span className="text-muted-foreground block">Department</span><span className="font-medium flex items-center gap-1 mt-0.5"><Building2 className="h-3.5 w-3.5 text-primary" /> {ticket.department_name || 'Not assigned'}</span></div>
              <div><span className="text-muted-foreground block">Assignment</span><span className="font-medium mt-0.5 block">{ticket.assigned_to_name || 'Unassigned'}</span></div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base font-bold">Timeline</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {ticket.history.length === 0 && <p className="text-xs text-muted-foreground">No status history.</p>}
              {ticket.history.map((item) => (
                <div key={item.id} className="border-l-2 border-primary/30 pl-3">
                  <p className="text-xs font-semibold">{item.to_status}{item.changed_by === null && <span className="font-normal text-muted-foreground"> - System</span>}</p>
                  {item.remarks && <p className="text-[11px] text-foreground">{item.remarks}</p>}
                  <p className="text-[11px] text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p>
                </div>
              ))}
            </CardContent>
          </Card>
          {permissions.can_confirm && (
            <Card className="border-emerald-500/30">
              <CardHeader><CardTitle className="text-base font-bold">Is the issue fixed?</CardTitle><CardDescription>Confirm to close this ticket. Otherwise it closes by itself a few days after being resolved.</CardDescription></CardHeader>
              <CardContent><Button className="w-full gap-2" disabled={isSaving} onClick={() => perform(() => ticketsApi.confirm(ref))}><CheckCircle2 className="h-4 w-4" /> Confirm Fixed</Button></CardContent>
            </Card>
          )}
          {permissions.can_withdraw && (
            <Card>
              <CardContent className="space-y-2 pt-6">
                <input value={withdrawReason} onChange={(event) => setWithdrawReason(event.target.value)} placeholder="Reason for withdrawing (optional)" className="w-full rounded-lg border bg-background px-3 py-2 text-sm" />
                <Button variant="outline" className="w-full gap-2" disabled={isSaving} onClick={() => perform(() => ticketsApi.withdraw(ref, withdrawReason), () => setWithdrawReason(''))}><Undo2 className="h-4 w-4" /> Withdraw Ticket</Button>
              </CardContent>
            </Card>
          )}
          {permissions.can_reopen && (
            <Card>
              <CardContent className="space-y-2 pt-6">
                <input value={reopenReason} onChange={(event) => setReopenReason(event.target.value)} placeholder="Why is it not fixed? (optional)" className="w-full rounded-lg border bg-background px-3 py-2 text-sm" />
                <Button variant="outline" className="w-full gap-2" disabled={isSaving} onClick={() => perform(() => ticketsApi.reopen(ref, reopenReason), () => setReopenReason(''))}><RotateCcw className="h-4 w-4" /> Request Reopen</Button>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
