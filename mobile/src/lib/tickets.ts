import type { Role, Ticket, TicketPriority, TicketStatus } from './api';

export const STATUSES: TicketStatus[] = ['NEW', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'REOPENED', 'CLOSED'];
export const PRIORITIES: TicketPriority[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

/** Words people see; the API values stay as they are. */
const STATUS_LABELS: Record<TicketStatus, string> = {
  NEW: 'New',
  UNDER_REVIEW: 'Under review',
  ASSIGNED: 'Assigned',
  IN_PROGRESS: 'In progress',
  RESOLVED: 'Resolved',
  REOPENED: 'Reopened',
  CLOSED: 'Closed',
};
const PRIORITY_LABELS: Record<TicketPriority, string> = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical' };
const ROLE_LABELS: Record<Role, string> = {
  STUDENT: 'Student',
  FACULTY: 'Faculty',
  STAFF: 'Staff',
  COORDINATOR: 'Coordinator',
  ADMIN: 'Admin',
};

export const statusLabel = (status: TicketStatus) => STATUS_LABELS[status] ?? status;
export const priorityLabel = (priority: TicketPriority) => PRIORITY_LABELS[priority] ?? priority;
export const roleLabel = (role: Role) => ROLE_LABELS[role] ?? role;

/** "Fairly sure (82%)": how sure the suggestion is, in plain words. */
export function confidenceLabel(confidence: number) {
  const words = confidence >= 0.9 ? 'Very sure' : confidence >= 0.7 ? 'Fairly sure' : confidence >= 0.5 ? 'Not fully sure' : 'Just a guess';
  return `${words} (${Math.round(confidence * 100)}%)`;
}

export const similarityLabel = (score: number) => `${Math.round(score * 100)}% similar`;
export const reportsLabel = (count: number) => `Reported by ${count} people`;

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
