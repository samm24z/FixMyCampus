/** App settings from `mobile/.env.local` (EXPO_PUBLIC_* values are inlined into the bundle at build time). */
import Constants from 'expo-constants';

/**
 * In development, the machine running `expo start` as the phone/emulator sees it ("192.168.1.58:8081"
 * on a real phone, "10.0.2.2:8081" on the Android emulator, "localhost:8081" on the iOS Simulator).
 * The backend runs on that same machine, so this finds it without per-device settings.
 */
function devServerHost(): string | null {
  const hostUri = Constants.expoConfig?.hostUri;
  return hostUri ? hostUri.split(':')[0] : null;
}

/** The FastAPI backend. EXPO_PUBLIC_API_BASE_URL wins; otherwise port 8000 on the dev machine. */
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL || `http://${devServerHost() ?? 'localhost'}:8000/api/v1`;

/** The web app. Supabase email links (confirm sign-up, reset password) open there. */
export const WEB_URL = (process.env.EXPO_PUBLIC_WEB_URL || 'http://localhost:5173').replace(/\/+$/, '');

export const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL || '';
export const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || '';

/** College-specific settings in one place; mirrors frontend/src/lib/campus.ts. */
export const CAMPUS = {
  name: 'MVSR Engineering College',
  shortName: 'MVSR',
  emailDomain: (process.env.EXPO_PUBLIC_ALLOWED_EMAIL_DOMAIN || 'mvsrec.edu.in').toLowerCase(),
} as const;

export const EMAIL_HINT = `name@${CAMPUS.emailDomain}`;

/** Client-side convenience check; the backend and Supabase enforce the same rule authoritatively. */
export function isCampusEmail(email: string): boolean {
  const [local, domain, ...rest] = email.trim().toLowerCase().split('@');
  return rest.length === 0 && Boolean(local) && domain === CAMPUS.emailDomain;
}
