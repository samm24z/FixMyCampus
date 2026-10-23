import React, { useEffect, useState } from 'react';
import { ArrowLeft, Clock, MapPin, User, Building2, FileText, Send, RotateCcw, CalendarClock, CheckCircle2, Star, Undo2, Sparkles, Copy, Users, Scissors } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { TicketGallery } from '@/components/TicketGallery';
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
import { PRIORITIES, confidenceLabel, priorityLabel, reportsLabel, roleLabel, similarityLabel, statusLabel, statusVariant } from '@/lib/tickets';

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

  // Suggestions are prepared in the background right after a report is filed: check back a few times.
  const suggestionsPending = ticket?.suggestions?.status === 'pending';
  const ticketRef = ticket?.ticket_number;
  useEffect(() => {
    if (!suggestionsPending || !ticketRef) return;
    let attempts = 0;
    const timer = setInterval(() => {
      attempts += 1;
      ticketsApi.detail(ticketRef).then((response) => setTicket(response.data)).catch(() => undefined);
      if (attempts >= 8) clearInterval(timer);
    }, 2500);
    return () => clearInterval(timer);
  }, [suggestionsPending, ticketRef]);

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
  const { suggestions } = ticket;
  const suggestionsDiffer = !!suggestions && (
    suggestions.category !== ticket.category ||
    suggestions.priority !== ticket.priority ||
    (!!suggestions.department_id && suggestions.department_id !== ticket.confirmed_department_id)
  );
  const departmentName = (departmentId: string | null) => departments.find((item) => item.id === departmentId)?.name;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/tickets')}><ArrowLeft className="h-4 w-4" /> Back to Tickets</Button>
      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2.5 py-1 rounded-md">{ticket.ticket_number}</span>
          <Badge variant={statusVariant(ticket.status)}>{statusLabel(ticket.status)}</Badge>
          <Badge variant={ticket.priority === 'CRITICAL' ? 'destructive' : 'outline'}>{priorityLabel(ticket.priority)} priority</Badge>
          {ticket.report_count > 1 && permissions.can_review_suggestions && <Badge variant="warning">{reportsLabel(ticket.report_count)}</Badge>}
          {ticket.parent_ticket_id && permissions.can_review_suggestions && <Badge variant="outline">Grouped</Badge>}
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold mt-2">{ticket.title}</h1>
        {!permissions.can_review_suggestions && (ticket.report_count > 1 || ticket.parent_ticket_id) && (
          <p className="mt-2 flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 p-3 text-sm"><Users className="h-4 w-4 text-primary" /> Other people reported the same problem. We're fixing them together.</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base font-bold flex items-center gap-2"><FileText className="h-4 w-4 text-primary" /> What's wrong</CardTitle></CardHeader>
            <CardContent className="space-y-4 text-sm">
              <p className="text-muted-foreground leading-relaxed">{ticket.description}</p>
              <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground pt-2 border-t">
                <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-primary" /> {ticket.location}</span>
                <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5 text-primary" /> {new Date(ticket.created_at).toLocaleString()}</span>
                {ticket.sla_deadline && <span className="flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5 text-primary" /> Fix by {new Date(ticket.sla_deadline).toLocaleString()}</span>}
              </div>
            </CardContent>
          </Card>

          <TicketGallery ticket={ticket} />

          {permissions.can_review_suggestions && (
            <Card>
              <CardHeader><CardTitle className="text-base font-bold flex items-center gap-2"><Sparkles className="h-4 w-4 text-primary" /> Suggestions</CardTitle><CardDescription>A starting point only. You decide the category, priority and department.</CardDescription></CardHeader>
              <CardContent className="space-y-3 text-sm">
                {!suggestions && <p className="text-muted-foreground">No suggestions for this ticket yet.</p>}
                {suggestions?.status === 'pending' && <p className="text-muted-foreground">Preparing suggestions...</p>}
                {suggestions?.status === 'failed' && <p className="text-muted-foreground">Suggestions couldn't be prepared for this ticket. You can try again.</p>}
                {suggestions?.status === 'done' && (
                  <>
                    <dl className="grid gap-3 sm:grid-cols-3">
                      <div><dt className="text-xs text-muted-foreground">Category</dt><dd className="font-medium">{suggestions.category}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Priority</dt><dd className="font-medium">{suggestions.priority ? priorityLabel(suggestions.priority) : '-'}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Department</dt><dd className="font-medium">{suggestions.department_name || '-'}</dd></div>
                    </dl>
                    {suggestions.confidence !== null && <p className="text-xs text-muted-foreground">{confidenceLabel(suggestions.confidence)}{suggestions.source === 'keywords' ? ' - based on keywords' : ''}</p>}
                    {suggestions.reason && <p className="text-muted-foreground">{suggestions.reason}</p>}
                  </>
                )}
                <div className="flex flex-wrap gap-2">
                  {suggestions?.status === 'done' && <Button size="sm" disabled={isSaving || !suggestionsDiffer} onClick={() => perform(() => ticketsApi.acceptSuggestions(ref))}>Use these suggestions</Button>}
                  <Button size="sm" variant="outline" disabled={isSaving || suggestions?.status === 'pending'} onClick={() => perform(() => ticketsApi.refreshSuggestions(ref))}>Refresh suggestions</Button>
                </div>
              </CardContent>
            </Card>
          )}

          {permissions.can_review_suggestions && ticket.duplicates.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base font-bold flex items-center gap-2"><Copy className="h-4 w-4 text-primary" /> Possible duplicates</CardTitle><CardDescription>These open tickets sound like the same problem. Reports you confirm are grouped and fixed together.</CardDescription></CardHeader>
              <CardContent className="space-y-3">
                {ticket.duplicates.map((item) => (
                  <div key={item.ticket_id} className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0 text-sm">
                      <div className="flex flex-wrap items-center gap-2"><Link to={`/tickets/${item.ticket_number}`} className="font-mono text-xs font-bold text-primary hover:underline">{item.ticket_number}</Link><Badge variant={statusVariant(item.status)}>{statusLabel(item.status)}</Badge><span className="text-xs text-muted-foreground">{similarityLabel(item.similarity_score)}</span></div>
                      <p className="mt-1 truncate font-medium">{item.title}</p>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <Button size="sm" disabled={isSaving} onClick={() => perform(() => ticketsApi.sameProblem(ref, item.ticket_number))}>Same problem</Button>
                      <Button size="sm" variant="outline" disabled={isSaving} onClick={() => perform(() => ticketsApi.notSameProblem(ref, item.ticket_number))}>Not the same</Button>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {permissions.can_edit_triage && (
            <Card>
              <CardHeader><CardTitle className="text-base font-bold">Category and Priority</CardTitle><CardDescription>Correct these if needed. Changing them also updates the fix-by date.</CardDescription></CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-medium">Category
                  <select value={category} onChange={(event) => setCategory(event.target.value)} className={selectClass}>{CATEGORY_OPTIONS.map((item) => <option key={item}>{item}</option>)}</select>
                </label>
                <label className="text-xs font-medium">Priority
                  <select value={priority} onChange={(event) => setPriority(event.target.value as TicketPriority)} className={selectClass}>{PRIORITIES.map((item) => <option key={item} value={item}>{priorityLabel(item)}</option>)}</select>
                </label>
                <Button className="sm:col-span-2" disabled={isSaving || (category === ticket.category && priority === ticket.priority)} onClick={() => perform(() => ticketsApi.triage(ref, { category, priority }))}>Save Changes</Button>
              </CardContent>
            </Card>
          )}

          {permissions.can_assign && (
            <Card>
              <CardHeader><CardTitle className="text-base font-bold">Assign to Staff</CardTitle><CardDescription>Currently: {ticket.assigned_to_name || 'not assigned'}{ticket.department_name ? ` (${ticket.department_name})` : ''}</CardDescription></CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-medium">Department
                  <select value={departmentId} onChange={(event) => { setDepartmentId(event.target.value); setAssignee(''); }} className={selectClass}>
                    <option value="">Staff member's own department</option>
                    {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label className="text-xs font-medium">Staff member
                  <select value={assignee} onChange={(event) => setAssignee(event.target.value)} className={selectClass}>
                    <option value="">Choose a staff member...</option>
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
                <label className="text-xs font-medium">New status
                  <select value={nextStatus} onChange={(event) => setNextStatus(event.target.value as TicketStatus)} className={selectClass}>
                    <option value="">Choose a status...</option>
                    {permissions.allowed_statuses.map((item) => <option key={item} value={item}>{statusLabel(item)}</option>)}
                  </select>
                </label>
                <label className="text-xs font-medium">Note{remarksRequired ? ' (required)' : ' (optional)'}
                  <input value={remarks} onChange={(event) => setRemarks(event.target.value)} className={selectClass} placeholder={nextStatus === 'CLOSED' ? 'Why is this ticket being turned down?' : 'What was done?'} />
                </label>
                <Button className="sm:col-span-2" disabled={isSaving || !nextStatus || (remarksRequired && !remarks.trim())} onClick={() => perform(() => ticketsApi.changeStatus(ref, nextStatus as TicketStatus, remarks))}>Update Status</Button>
              </CardContent>
            </Card>
          )}

          {(permissions.can_give_feedback || ticket.feedback) && (
            <Card>
              <CardHeader><CardTitle className="text-base font-bold flex items-center gap-2"><Star className="h-4 w-4 text-primary" /> Rate the Fix</CardTitle>{permissions.can_give_feedback && <CardDescription>How happy are you with how this was fixed?</CardDescription>}</CardHeader>
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
                    <Button disabled={isSaving || rating === 0 || (rating === ticket.feedback?.rating && feedbackComments === (ticket.feedback?.comments ?? ''))} onClick={() => perform(() => ticketsApi.submitFeedback(ref, rating, feedbackComments))}>{ticket.feedback ? 'Update Rating' : 'Send Rating'}</Button>
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
                      {item.author_role && <span className="font-normal text-muted-foreground">{roleLabel(item.author_role)}</span>}
                      {item.is_internal && <Badge variant="warning">Staff only</Badge>}
                    </div>
                    <p className="text-sm">{item.content}</p>
                    <p className="mt-2 text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p>
                  </div>
                ))}
              </div>
              {permissions.can_comment && (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input value={comment} onChange={(event) => setComment(event.target.value)} placeholder={isInternal ? 'Add a note only staff can see' : 'Add a comment'} className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm" />
                    <Button size="icon" disabled={!comment.trim() || isSaving} onClick={() => perform(() => ticketsApi.comment(ref, comment, isInternal), () => setComment(''))}><Send className="h-4 w-4" /></Button>
                  </div>
                  {permissions.can_comment_internal && (
                    <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={isInternal} onChange={(event) => setIsInternal(event.target.checked)} /> Only staff can see this note</label>
                  )}
                </div>
              )}
              {!permissions.can_comment && ticket.status === 'CLOSED' && <p className="text-sm text-muted-foreground">This ticket is closed. Reopen it to add a comment.</p>}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base font-bold">Details</CardTitle></CardHeader>
            <CardContent className="space-y-4 text-xs">
              <div><span className="text-muted-foreground block">Reported by</span><span className="font-medium flex items-center gap-1 mt-0.5"><User className="h-3.5 w-3.5 text-primary" /> {ticket.created_by_name}</span></div>
              <div><span className="text-muted-foreground block">Category</span><span className="font-medium mt-0.5 block">{ticket.category}</span></div>
              <div><span className="text-muted-foreground block">Department</span><span className="font-medium flex items-center gap-1 mt-0.5"><Building2 className="h-3.5 w-3.5 text-primary" /> {ticket.department_name || 'Not assigned'}</span></div>
              <div><span className="text-muted-foreground block">Assigned to</span><span className="font-medium mt-0.5 block">{ticket.assigned_to_name || 'Not assigned yet'}</span></div>
            </CardContent>
          </Card>
          {permissions.can_review_suggestions && (ticket.parent_ticket_id || ticket.group_members.length > 0) && (
            <Card>
              <CardHeader><CardTitle className="text-base font-bold flex items-center gap-2"><Users className="h-4 w-4 text-primary" /> {ticket.parent_ticket_id ? 'Grouped report' : reportsLabel(ticket.report_count)}</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-xs">
                {ticket.parent_ticket_id && (
                  <>
                    <p>Grouped with <Link to={`/tickets/${ticket.parent_ticket_number}`} className="font-mono font-bold text-primary hover:underline">{ticket.parent_ticket_number}</Link>. Its status follows that ticket, so update that ticket instead.</p>
                    {permissions.can_split_group && <Button variant="outline" size="sm" className="w-full gap-2" disabled={isSaving} onClick={() => perform(() => ticketsApi.splitFromGroup(ref))}><Scissors className="h-4 w-4" /> Split from group</Button>}
                  </>
                )}
                {ticket.group_members.map((member) => (
                  <div key={member.ticket_id} className="flex items-center justify-between gap-2 border-t pt-2">
                    <div className="min-w-0"><Link to={`/tickets/${member.ticket_number}`} className="font-mono font-bold text-primary hover:underline">{member.ticket_number}</Link><p className="truncate text-muted-foreground">{member.title}</p></div>
                    <Badge variant={statusVariant(member.status)}>{statusLabel(member.status)}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle className="text-base font-bold">History</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {ticket.history.length === 0 && <p className="text-xs text-muted-foreground">No updates yet.</p>}
              {ticket.history.map((item) => (
                <div key={item.id} className="border-l-2 border-primary/30 pl-3">
                  <p className="text-xs font-semibold">{statusLabel(item.to_status)}{item.changed_by === null && <span className="font-normal text-muted-foreground"> - automatic</span>}</p>
                  {item.remarks && <p className="text-[11px] text-foreground">{item.remarks}</p>}
                  <p className="text-[11px] text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p>
                </div>
              ))}
            </CardContent>
          </Card>
          {permissions.can_confirm && (
            <Card className="border-emerald-500/30">
              <CardHeader><CardTitle className="text-base font-bold">Is the issue fixed?</CardTitle><CardDescription>If it's fixed, confirm to close the ticket. If you don't reply, it will close by itself after a few days.</CardDescription></CardHeader>
              <CardContent><Button className="w-full gap-2" disabled={isSaving} onClick={() => perform(() => ticketsApi.confirm(ref))}><CheckCircle2 className="h-4 w-4" /> Yes, it's fixed</Button></CardContent>
            </Card>
          )}
          {permissions.can_withdraw && (
            <Card>
              <CardContent className="space-y-2 pt-6">
                <input value={withdrawReason} onChange={(event) => setWithdrawReason(event.target.value)} placeholder="Why are you cancelling? (optional)" className="w-full rounded-lg border bg-background px-3 py-2 text-sm" />
                <Button variant="outline" className="w-full gap-2" disabled={isSaving} onClick={() => perform(() => ticketsApi.withdraw(ref, withdrawReason), () => setWithdrawReason(''))}><Undo2 className="h-4 w-4" /> Cancel This Ticket</Button>
              </CardContent>
            </Card>
          )}
          {permissions.can_reopen && (
            <Card>
              <CardContent className="space-y-2 pt-6">
                <input value={reopenReason} onChange={(event) => setReopenReason(event.target.value)} placeholder="Why is it not fixed? (optional)" className="w-full rounded-lg border bg-background px-3 py-2 text-sm" />
                <Button variant="outline" className="w-full gap-2" disabled={isSaving} onClick={() => perform(() => ticketsApi.reopen(ref, reopenReason), () => setReopenReason(''))}><RotateCcw className="h-4 w-4" /> Reopen Ticket</Button>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
