import { describe, expect, it } from 'vitest';
import { formatAccuracy, mapsLink, photoAgeNote } from './gallery';

const REPORTED = '2026-10-20T10:00:00Z';

describe('photoAgeNote', () => {
  it('says nothing when there are no photo times', () => {
    expect(photoAgeNote([], REPORTED)).toBeNull();
    expect(photoAgeNote([null, null], REPORTED)).toBeNull();
  });

  it('says nothing for photos taken shortly before the report', () => {
    expect(photoAgeNote(['2026-10-20T09:00:00Z'], REPORTED)).toBeNull();
  });

  it('says nothing at exactly 48 hours', () => {
    expect(photoAgeNote(['2026-10-18T10:00:00Z'], REPORTED)).toBeNull();
  });

  it('starts counting just over 48 hours, in whole days', () => {
    expect(photoAgeNote(['2026-10-18T09:59:00Z'], REPORTED)).toBe('Photo taken 2 days before the report');
  });

  it('describes older photos in days', () => {
    expect(photoAgeNote(['2026-10-17T10:00:00Z'], REPORTED)).toBe('Photo taken 3 days before the report');
  });

  it('uses the earliest photo that has a time', () => {
    expect(photoAgeNote([null, '2026-10-19T10:00:00Z', '2026-10-16T10:00:00Z'], REPORTED)).toBe(
      'Photo taken 4 days before the report',
    );
  });

  it('ignores photos with an unreadable time', () => {
    expect(photoAgeNote(['not a date', '2026-10-17T10:00:00Z'], REPORTED)).toBe('Photo taken 3 days before the report');
  });
});

describe('mapsLink', () => {
  it('builds a Google Maps search link with 6 decimals', () => {
    expect(mapsLink(12.9, 77.5)).toBe('https://www.google.com/maps?q=12.900000,77.500000');
    expect(mapsLink(-33.5, 151.25)).toBe('https://www.google.com/maps?q=-33.500000,151.250000');
  });
});

describe('formatAccuracy', () => {
  it('rounds to whole metres', () => {
    expect(formatAccuracy(25.4)).toBe('±25 m');
    expect(formatAccuracy(25.6)).toBe('±26 m');
    expect(formatAccuracy(0)).toBe('±0 m');
  });

  it('returns null when the accuracy is missing', () => {
    expect(formatAccuracy(null)).toBeNull();
    expect(formatAccuracy(undefined)).toBeNull();
    expect(formatAccuracy(Number.NaN)).toBeNull();
  });
});
