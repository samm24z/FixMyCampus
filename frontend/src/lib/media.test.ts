import { describe, expect, it } from 'vitest';
import { MAX_ORIGINAL_BYTES, fromDateTimeLocal, pickObservedAt, toDateTimeLocal, validatePhotoFile } from './media';

describe('validatePhotoFile', () => {
  it('accepts normal photos, including HEIC', () => {
    expect(validatePhotoFile({ type: 'image/jpeg', size: 2_000_000 }, 0)).toBeNull();
    expect(validatePhotoFile({ type: 'image/heic', size: 2_000_000 }, 4)).toBeNull();
    expect(validatePhotoFile({ type: 'image/png', size: MAX_ORIGINAL_BYTES }, 0)).toBeNull();
  });

  it('refuses a sixth photo', () => {
    expect(validatePhotoFile({ type: 'image/jpeg', size: 1000 }, 5)).toBe('You can add up to 5 photos');
  });

  it('refuses big files and other types', () => {
    expect(validatePhotoFile({ type: 'image/jpeg', size: MAX_ORIGINAL_BYTES + 1 }, 0)).toBe('Photos can be up to 15 MB');
    expect(validatePhotoFile({ type: 'application/pdf', size: 1000 }, 0)).toBe('Please choose a photo (JPEG, PNG, WebP or HEIC)');
    expect(validatePhotoFile({ type: '', size: 1000 }, 0)).toBe('Please choose a photo (JPEG, PNG, WebP or HEIC)');
  });
});

describe('pickObservedAt', () => {
  const now = new Date('2026-10-23T12:00:00Z');
  const daysAgo = (n: number) => new Date(now.getTime() - n * 24 * 3600 * 1000);

  it('uses the earliest usable capture time', () => {
    expect(pickObservedAt([daysAgo(1), daysAgo(3), null], now)).toEqual(daysAgo(3));
  });

  it('ignores future, old and missing times', () => {
    expect(pickObservedAt([new Date(now.getTime() + 60_000), daysAgo(45), null], now)).toBe(now);
    expect(pickObservedAt([daysAgo(45), daysAgo(2)], now)).toEqual(daysAgo(2));
  });

  it('falls back to now without any captures', () => {
    expect(pickObservedAt([], now)).toBe(now);
  });
});

describe('datetime-local helpers', () => {
  it('formats local time', () => {
    expect(toDateTimeLocal(new Date(2026, 0, 5, 9, 7))).toBe('2026-01-05T09:07');
  });

  it('round-trips', () => {
    const d = new Date(2026, 9, 23, 14, 30);
    expect(fromDateTimeLocal(toDateTimeLocal(d))).toEqual(d);
  });

  it('rejects bad input', () => {
    expect(fromDateTimeLocal('')).toBeNull();
    expect(fromDateTimeLocal('not a date')).toBeNull();
    expect(fromDateTimeLocal('2026-02-31T10:00')).toBeNull();
  });
});
