import { File } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import type { ImagePickerAsset } from 'expo-image-picker';

// Mirrors frontend/src/lib/media.ts; the backend enforces the same limits.
export const MAX_PHOTOS = 5;
export const MAX_ORIGINAL_BYTES = 15 * 1024 * 1024;

const DAY_MS = 24 * 60 * 60 * 1000;
const RECENT_DAYS = 30;

export interface PhotoMeta {
  capturedAt: Date | null;
  gps: { lat: number; lng: number } | null;
}

export interface PreparedPhoto {
  /** file:// URI of the shrunk JPEG, with no EXIF (and so no GPS) left in it. */
  uri: string;
  width: number;
  height: number;
  size: number;
  name: string;
  mimeType: 'image/jpeg';
}

/** Plain-English reason a photo can't be added, or null when it is fine. */
export function validatePhotoAsset(asset: Pick<ImagePickerAsset, 'type' | 'fileSize'>, currentCount: number): string | null {
  if (currentCount >= MAX_PHOTOS) return `You can add up to ${MAX_PHOTOS} photos`;
  if (asset.type && asset.type !== 'image') return 'Please choose a photo';
  if (asset.fileSize && asset.fileSize > MAX_ORIGINAL_BYTES) return 'Photos can be up to 15 MB';
  return null;
}

/** EXIF dates look like "2026:10:23 14:05:09" (local time). */
function parseExifDate(value: unknown): Date | null {
  if (typeof value !== 'string') return null;
  const match = /^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/.exec(value.trim());
  if (!match) return null;
  const [year, month, day, hour, minute, second] = match.slice(1).map(Number);
  const d = new Date(year, month - 1, day, hour, minute, second);
  return Number.isNaN(d.getTime()) ? null : d;
}

function signed(value: unknown, ref: unknown, negative: string): number | null {
  const n = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN;
  if (!Number.isFinite(n)) return null;
  return typeof ref === 'string' && ref.toUpperCase().startsWith(negative) ? -Math.abs(n) : n;
}

/**
 * When and where the photo was taken, from the picker's EXIF. iOS nests GPS under "{GPS}" with
 * Latitude/LatitudeRef; Android uses flat GPSLatitude/GPSLatitudeRef. Never throws.
 */
export function readPhotoMeta(exif: Record<string, unknown> | null | undefined): PhotoMeta {
  if (!exif) return { capturedAt: null, gps: null };
  try {
    const nested = (exif['{Exif}'] ?? {}) as Record<string, unknown>;
    const capturedAt =
      parseExifDate(exif.DateTimeOriginal) ?? parseExifDate(nested.DateTimeOriginal) ?? parseExifDate(exif.DateTime);
    const gpsBlock = (exif['{GPS}'] ?? {}) as Record<string, unknown>;
    const lat = signed(gpsBlock.Latitude ?? exif.GPSLatitude, gpsBlock.LatitudeRef ?? exif.GPSLatitudeRef, 'S');
    const lng = signed(gpsBlock.Longitude ?? exif.GPSLongitude, gpsBlock.LongitudeRef ?? exif.GPSLongitudeRef, 'W');
    const gps = lat !== null && lng !== null && Math.abs(lat) <= 90 && Math.abs(lng) <= 180 && !(lat === 0 && lng === 0) ? { lat, lng } : null;
    return { capturedAt, gps };
  } catch {
    return { capturedAt: null, gps: null };
  }
}

/**
 * Resize to at most 1600 px on the long side and re-encode as JPEG. Re-encoding drops the EXIF
 * data, so the photo's GPS never leaves the phone inside the file.
 */
export async function shrinkPhoto(asset: Pick<ImagePickerAsset, 'uri' | 'width' | 'height' | 'fileName'>): Promise<PreparedPhoto> {
  const context = ImageManipulator.manipulate(asset.uri);
  const longSide = Math.max(asset.width, asset.height);
  if (longSide > 1600) {
    context.resize(asset.width >= asset.height ? { width: 1600 } : { height: 1600 });
  }
  const rendered = await context.renderAsync();
  const saved = await rendered.saveAsync({ format: SaveFormat.JPEG, compress: 0.8 });
  const size = Number(new File(saved.uri).size ?? 0);
  const base = (asset.fileName ?? 'photo').replace(/\.[^./\\]+$/, '') || 'photo';
  return { uri: saved.uri, width: saved.width, height: saved.height, size, name: `${base}.jpg`, mimeType: 'image/jpeg' };
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
