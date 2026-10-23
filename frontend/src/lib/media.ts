import exifr from 'exifr';
import imageCompression from 'browser-image-compression';

export const MAX_PHOTOS = 5;
export const MAX_ORIGINAL_BYTES = 15 * 1024 * 1024;
export const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];

const DAY_MS = 24 * 60 * 60 * 1000;
const RECENT_DAYS = 30;

export interface PhotoMeta {
  capturedAt: Date | null;
  gps: { lat: number; lng: number } | null;
}

/** Plain-English reason a photo can't be added, or null when it is fine. */
export function validatePhotoFile(file: { type: string; size: number }, currentCount: number): string | null {
  if (currentCount >= MAX_PHOTOS) return `You can add up to ${MAX_PHOTOS} photos`;
  if (!ACCEPTED_TYPES.includes(file.type.toLowerCase())) return 'Please choose a photo (JPEG, PNG, WebP or HEIC)';
  if (file.size > MAX_ORIGINAL_BYTES) return 'Photos can be up to 15 MB';
  return null;
}

function asDate(value: unknown): Date | null {
  return value instanceof Date && !Number.isNaN(value.getTime()) ? value : null;
}

/** When and where the photo was taken, read from its EXIF data. Never throws. */
export async function readPhotoMeta(file: Blob): Promise<PhotoMeta> {
  try {
    const tags = await exifr.parse(file, { gps: true });
    if (!tags) return { capturedAt: null, gps: null };
    const lat = tags.latitude;
    const lng = tags.longitude;
    const gps = typeof lat === 'number' && typeof lng === 'number' && Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null;
    return { capturedAt: asDate(tags.DateTimeOriginal) ?? asDate(tags.CreateDate), gps };
  } catch {
    return { capturedAt: null, gps: null };
  }
}

/** Resize to at most 1600 px and re-encode as JPEG. Re-encoding drops the EXIF data (including GPS). */
export async function shrinkPhoto(file: File): Promise<File> {
  try {
    const out = await imageCompression(file, {
      maxWidthOrHeight: 1600,
      maxSizeMB: 1,
      fileType: 'image/jpeg',
      initialQuality: 0.8,
      useWebWorker: true,
    });
    const base = file.name.replace(/\.[^./\\]+$/, '') || 'photo';
    return new File([out], `${base}.jpg`, { type: 'image/jpeg' });
  } catch {
    throw new Error("This photo format isn't supported in this browser — please choose a JPEG or PNG.");
  }
}

/** The earliest capture time that is plausible (not in the future, within 30 days); otherwise now. */
export function pickObservedAt(captures: (Date | null)[], now: Date): Date {
  const oldest = now.getTime() - RECENT_DAYS * DAY_MS;
  const usable = captures
    .filter((d): d is Date => d !== null && !Number.isNaN(d.getTime()))
    .filter((d) => d.getTime() <= now.getTime() && d.getTime() >= oldest)
    .sort((a, b) => a.getTime() - b.getTime());
  return usable[0] ?? now;
}

const pad = (n: number) => String(n).padStart(2, '0');

/** Local time as `YYYY-MM-DDTHH:mm`, the format `<input type="datetime-local">` uses. */
export function toDateTimeLocal(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromDateTimeLocal(s: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(s.trim());
  if (!match) return null;
  const [year, month, day, hour, minute] = match.slice(1).map(Number);
  const d = new Date(year, month - 1, day, hour, minute);
  // Reject overflow such as 2026-02-31.
  if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) return null;
  return d;
}
