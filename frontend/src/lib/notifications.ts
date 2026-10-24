/** Short, friendly age of a time: "just now", "5 min ago", "2 hours ago", "3 days ago", then the date. */
export function timeAgo(iso: string, now: number = Date.now()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const minutes = Math.floor(Math.max(0, now - then) / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} ${days === 1 ? 'day' : 'days'} ago`;
  return new Date(then).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

/** What the badge on the bell shows: nothing for zero, "9+" above nine. */
export function badgeLabel(count: number): string {
  if (count <= 0) return '';
  return count > 9 ? '9+' : String(count);
}

/** Where a notification leads, or null when it is not about a ticket. */
export function notificationLink(notification: { ticket_number: string | null }): string | null {
  return notification.ticket_number ? `/tickets/${notification.ticket_number}` : null;
}
