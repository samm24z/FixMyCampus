import type { BadgeTone } from '@/components/ui';
import type { TicketPriority, TicketStatus } from '@/lib/api';
import { priorityVariant, statusVariant } from '@/lib/tickets';

const TONES = { destructive: 'danger', warning: 'warning', success: 'success', secondary: 'neutral' } as const;

export const statusTone = (status: TicketStatus): BadgeTone => TONES[statusVariant(status)];
export const priorityTone = (priority: TicketPriority): BadgeTone => TONES[priorityVariant(priority)];

/** "Oct 23, 4:15 PM" (the year is added when it is not the current one). */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: sameYear ? undefined : 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/** "5m ago", "3h ago", "2d ago", then a short date. */
export function relativeDate(value: string): string {
  const date = new Date(value);
  const diff = Date.now() - date.getTime();
  if (Number.isNaN(diff)) return '';
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric',
  });
}
