import { isAuthError } from '@supabase/supabase-js';

/** Up to two initials for the avatar: "Riya Sharma" -> "RS", "admin@x.dev" -> "A". */
export function initials(name: string): string {
  const words = name.replace(/@.*$/, '').split(/[\s._-]+/).filter(Boolean);
  if (words.length === 0) return '?';
  const letters = words.length === 1 ? words[0][0] : words[0][0] + words[words.length - 1][0];
  return letters.toUpperCase();
}

// Google-like avatar colours; white text stays readable on all of them.
const AVATAR_COLOURS = ['#1a73e8', '#d93025', '#188038', '#e37400', '#9334e6', '#c5221f', '#12857a', '#b06000', '#3949ab', '#ad1457'];

/** The same person always gets the same colour. */
export function avatarColour(seed: string): string {
  let hash = 0;
  for (const ch of seed) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
  return AVATAR_COLOURS[Math.abs(hash) % AVATAR_COLOURS.length];
}

/** Mirrors the backend rules for names; returns a message or '' when fine. */
export function nameProblem(name: string): string {
  const clean = name.trim().replace(/\s+/g, ' ');
  if (clean.length < 2) return 'Enter your name (at least 2 characters).';
  if (clean.length > 150) return 'That name is too long (150 characters at most).';
  return '';
}

/** Mirrors the backend rules for phone numbers; an empty number is allowed (it clears it). */
export function phoneProblem(phone: string): string {
  const clean = phone.trim();
  if (!clean) return '';
  const digits = clean.replace(/\D/g, '').length;
  if (!/^\+?[0-9 ()-]+$/.test(clean) || digits < 7 || digits > 15) return 'Enter a valid phone number, e.g. +91 98765 43210.';
  return '';
}

export const MIN_PASSWORD_LENGTH = 8;

/** Checks the password form before anything is sent to Supabase. */
export function passwordProblem(current: string, next: string, confirm: string): string {
  if (!current) return 'Enter your current password.';
  if (next.length < MIN_PASSWORD_LENGTH) return `Your new password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  if (next !== confirm) return "The new passwords don't match.";
  if (next === current) return 'Your new password must be different from your current one.';
  return '';
}

/** Plain-English text for the Supabase errors a password change can hit. */
export function passwordErrorMessage(error: unknown): string {
  if (isAuthError(error)) {
    switch (error.code) {
      case 'invalid_credentials':
        return 'Your current password is incorrect.';
      case 'same_password':
        return 'Your new password must be different from your current one.';
      case 'weak_password':
        return 'That password is too easy to guess. Try a longer one with a mix of letters, numbers and symbols.';
      case 'over_request_rate_limit':
        return 'Too many attempts. Wait a few minutes and try again.';
      case 'reauthentication_needed':
      case 'session_expired':
      case 'session_not_found':
        return 'For your security, sign out and sign in again, then change your password.';
    }
    if (error.message) return error.message;
  }
  return "Your password couldn't be changed. Please try again.";
}
