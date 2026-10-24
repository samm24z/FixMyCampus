import { describe, expect, it } from 'vitest';
import { badgeLabel, notificationLink, timeAgo } from './notifications';

const NOW = new Date('2026-03-10T12:00:00Z').getTime();
const ago = (ms: number) => new Date(NOW - ms).toISOString();
const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

describe('timeAgo', () => {
  it('says "just now" for the last minute', () => {
    expect(timeAgo(ago(20_000), NOW)).toBe('just now');
    expect(timeAgo(ago(-5_000), NOW)).toBe('just now');
  });

  it('counts minutes, hours and days', () => {
    expect(timeAgo(ago(5 * MIN), NOW)).toBe('5 min ago');
    expect(timeAgo(ago(59 * MIN), NOW)).toBe('59 min ago');
    expect(timeAgo(ago(HOUR), NOW)).toBe('1 hour ago');
    expect(timeAgo(ago(3 * HOUR), NOW)).toBe('3 hours ago');
    expect(timeAgo(ago(DAY), NOW)).toBe('1 day ago');
    expect(timeAgo(ago(6 * DAY), NOW)).toBe('6 days ago');
  });

  it('falls back to the date after a week', () => {
    expect(timeAgo(ago(30 * DAY), NOW)).toMatch(/2026/);
  });

  it('returns nothing for a bad date', () => {
    expect(timeAgo('not a date', NOW)).toBe('');
  });
});

describe('badgeLabel', () => {
  it('hides zero and caps at 9+', () => {
    expect(badgeLabel(0)).toBe('');
    expect(badgeLabel(4)).toBe('4');
    expect(badgeLabel(9)).toBe('9');
    expect(badgeLabel(10)).toBe('9+');
  });
});

describe('notificationLink', () => {
  it('links to the ticket when there is one', () => {
    expect(notificationLink({ ticket_number: 'FMC-0042' })).toBe('/tickets/FMC-0042');
    expect(notificationLink({ ticket_number: null })).toBeNull();
  });
});
