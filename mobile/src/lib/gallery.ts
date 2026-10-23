const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

/**
 * "Photo taken 3 days before the report" when the earliest photo was taken more than 48 hours
 * before the report was filed. Null when there is nothing to say.
 */
export function photoAgeNote(capturedAts: (string | null)[], reportCreatedAt: string): string | null {
  const reportTime = Date.parse(reportCreatedAt);
  const captureTimes = capturedAts
    .flatMap((value) => (value ? [Date.parse(value)] : []))
    .filter((time) => Number.isFinite(time));
  if (captureTimes.length === 0 || !Number.isFinite(reportTime)) return null;

  const gapMs = reportTime - Math.min(...captureTimes);
  if (gapMs <= 48 * HOUR_MS) return null;

  const days = Math.floor(gapMs / DAY_MS);
  return `Photo taken ${days} ${days === 1 ? 'day' : 'days'} before the report`;
}

/** Opens the spot in Google Maps. Coordinates are fixed to 6 decimals (about 11 cm). */
export function mapsLink(lat: number, lng: number): string {
  return `https://www.google.com/maps?q=${lat.toFixed(6)},${lng.toFixed(6)}`;
}

/** "±25 m", or null when the accuracy is unknown. */
export function formatAccuracy(m: number | null | undefined): string | null {
  if (m === null || m === undefined || !Number.isFinite(m)) return null;
  return `±${Math.round(m)} m`;
}
