import type { Ticket, TicketStatus } from '@/lib/api';

export const STATUSES: TicketStatus[] = ['NEW', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'REOPENED', 'CLOSED'];

export function isDone(status: TicketStatus) {
  return status === 'RESOLVED' || status === 'CLOSED';
}

export function priorityVariant(priority: Ticket['priority']) {
  if (priority === 'CRITICAL') return 'destructive' as const;
  if (priority === 'HIGH') return 'warning' as const;
  return 'secondary' as const;
}

export function statusVariant(status: TicketStatus) {
  return isDone(status) ? ('success' as const) : ('warning' as const);
}
