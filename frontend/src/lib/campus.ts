/** College-specific settings in one place, so the app can be re-tailored by editing this file. */
export const CAMPUS = {
  name: 'MVSR Engineering College',
  shortName: 'MVSR',
  emailDomain: (import.meta.env.VITE_ALLOWED_EMAIL_DOMAIN || 'mvsrec.edu.in').toLowerCase(),
} as const;

export const EMAIL_HINT = `name@${CAMPUS.emailDomain}`;

/** Client-side convenience check; the backend and Supabase enforce the same rule authoritatively. */
export function isCampusEmail(email: string): boolean {
  const [local, domain, ...rest] = email.trim().toLowerCase().split('@');
  return rest.length === 0 && Boolean(local) && domain === CAMPUS.emailDomain;
}
