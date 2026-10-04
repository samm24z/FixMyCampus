import { AuthApiError } from '@supabase/supabase-js';
import { AxiosError, type AxiosResponse } from 'axios';
import { describe, expect, it } from 'vitest';
import { getApiError } from './api';
import { roleHome } from './auth';
import { isCampusEmail } from './campus';

function apiError(status: number, data: unknown) {
  const error = new AxiosError('failed');
  error.response = { status, data } as AxiosResponse;
  return error;
}

describe('getApiError', () => {
  it('reads the backend error envelope', () => {
    expect(getApiError(apiError(409, { success: false, error: { code: 'CONFLICT', message: 'Email is already registered' } }))).toBe(
      'Email is already registered',
    );
  });

  it('flattens validation details into field messages', () => {
    const body = { error: { message: 'Invalid', details: [{ loc: ['body', 'title'], msg: 'String too short' }] } };
    expect(getApiError(apiError(422, body))).toBe('title: String too short');
  });

  it('falls back to a plain detail string', () => {
    expect(getApiError(apiError(401, { detail: 'Not authenticated' }))).toBe('Not authenticated');
  });

  it('reports an unreachable server', () => {
    expect(getApiError(new AxiosError('Network Error'))).toMatch(/Cannot reach the server/);
  });

  it('shows Supabase Auth messages as written', () => {
    expect(getApiError(new AuthApiError('Invalid login credentials', 400, 'invalid_credentials'))).toBe('Invalid login credentials');
  });

  it('uses the caller fallback for unknown errors', () => {
    expect(getApiError(new Error('boom'), 'Nope')).toBe('Nope');
  });
});

describe('roleHome', () => {
  it('sends each role to its own landing page', () => {
    expect(roleHome('STUDENT')).toBe('/dashboard');
    expect(roleHome('FACULTY')).toBe('/dashboard');
    expect(roleHome('STAFF')).toBe('/staff');
    expect(roleHome('COORDINATOR')).toBe('/staff');
    expect(roleHome('ADMIN')).toBe('/admin');
  });
});

describe('isCampusEmail', () => {
  it('accepts only exact college-domain addresses, in any case', () => {
    expect(isCampusEmail('roll.no@mvsrec.edu.in')).toBe(true);
    expect(isCampusEmail('  Roll.No@MVSREC.edu.in ')).toBe(true);
  });

  it('rejects other domains, look-alikes, sub-domains and malformed input', () => {
    for (const bad of ['a@gmail.com', 'a@mvsrec.edu.in.evil.com', 'a@evilmvsrec.edu.in', 'a@cse.mvsrec.edu.in', 'mvsrec.edu.in', '@mvsrec.edu.in', 'a@b@mvsrec.edu.in', '']) {
      expect(isCampusEmail(bad), bad).toBe(false);
    }
  });
});
