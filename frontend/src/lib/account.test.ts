import { describe, expect, it } from 'vitest';
import { AuthApiError } from '@supabase/supabase-js';
import { avatarColour, initials, nameProblem, passwordErrorMessage, passwordProblem, phoneProblem } from './account';

describe('avatar', () => {
  it('uses the first and last initials', () => {
    expect(initials('Riya Sharma')).toBe('RS');
    expect(initials('  ravi  kumar   reddy ')).toBe('RR');
    expect(initials('Admin')).toBe('A');
    expect(initials('a.b@mvsrec.edu.in')).toBe('AB');
    expect(initials('')).toBe('?');
  });

  it('gives the same person the same colour', () => {
    expect(avatarColour('user-1')).toBe(avatarColour('user-1'));
    expect(avatarColour('user-1')).toMatch(/^#[0-9a-f]{6}$/);
  });
});

describe('profile checks', () => {
  it('needs a real name', () => {
    expect(nameProblem('Riya Sharma')).toBe('');
    expect(nameProblem(' R ')).not.toBe('');
    expect(nameProblem('x'.repeat(151))).not.toBe('');
  });

  it('accepts common phone formats and an empty number', () => {
    expect(phoneProblem('')).toBe('');
    expect(phoneProblem('+91 98765 43210')).toBe('');
    expect(phoneProblem('040-2345 6789')).toBe('');
    expect(phoneProblem('call me')).not.toBe('');
    expect(phoneProblem('12345')).not.toBe('');
  });
});

describe('password change', () => {
  it('checks the form before sending', () => {
    expect(passwordProblem('', 'newpassword', 'newpassword')).toBe('Enter your current password.');
    expect(passwordProblem('old', 'short', 'short')).toMatch(/at least 8/);
    expect(passwordProblem('old', 'newpassword', 'newpasswore')).toBe("The new passwords don't match.");
    expect(passwordProblem('samepassword', 'samepassword', 'samepassword')).toMatch(/different/);
    expect(passwordProblem('old', 'newpassword', 'newpassword')).toBe('');
  });

  it('explains Supabase errors in plain English', () => {
    expect(passwordErrorMessage(new AuthApiError('Invalid login credentials', 400, 'invalid_credentials'))).toBe('Your current password is incorrect.');
    expect(passwordErrorMessage(new AuthApiError('x', 422, 'same_password'))).toMatch(/different/);
    expect(passwordErrorMessage(new Error('boom'))).toMatch(/couldn't be changed/);
  });
});
