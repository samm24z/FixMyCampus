import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { authApi, getApiError, type User } from './api';
import { WEB_URL } from './config';
import { supabase } from './supabase';

export { getApiError };

export interface RegisterForm {
  full_name: string;
  email: string;
  password: string;
  role: 'STUDENT' | 'FACULTY';
}

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<User>;
  /** `needsConfirmation` is true when Supabase emailed a link the user must click before signing in. */
  register: (form: RegisterForm) => Promise<{ user: User | null; needsConfirmation: boolean }>;
  /** Emails a reset link; the link opens the web app's reset-password page. */
  requestPasswordReset: (email: string) => Promise<void>;
  /** Saves the signed-in user's own name / phone number and refreshes `user` everywhere. */
  updateProfile: (changes: { full_name?: string; phone_number?: string | null }) => Promise<User>;
  /** Checks the current password, then sets the new one. */
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const userId = useRef<string | null>(null);

  const loadProfile = useCallback(async (): Promise<User> => {
    try {
      const profile = (await authApi.me()).data;
      userId.current = profile.id;
      setUser(profile);
      return profile;
    } catch (error) {
      userId.current = null;
      setUser(null);
      throw error;
    }
  }, []);

  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(async ({ data }) => {
      if (data.session) await loadProfile().catch(() => undefined);
      if (active) setIsLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((event, session) => {
      if (!session) {
        userId.current = null;
        setUser(null);
        return;
      }
      // Only reload for a different user. Deferred with setTimeout because calling Supabase from
      // inside this callback can deadlock.
      if (event === 'SIGNED_IN' && userId.current !== session.user.id) setTimeout(() => void loadProfile().catch(() => undefined), 0);
    });
    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, [loadProfile]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
      if (error) throw error;
      try {
        return await loadProfile();
      } catch (profileError) {
        await supabase.auth.signOut();
        // e.g. "Sign-up is limited to @mvsrec.edu.in email addresses." or a deactivated account.
        throw new Error(getApiError(profileError, 'Your account could not be loaded. Contact a campus administrator.'));
      }
    },
    [loadProfile],
  );

  const register = useCallback(
    async (form: RegisterForm) => {
      const { data, error } = await supabase.auth.signUp({
        email: form.email.trim(),
        password: form.password,
        options: {
          data: { full_name: form.full_name, role: form.role },
          emailRedirectTo: `${WEB_URL}/login`,
        },
      });
      if (error) throw error;
      // With "Confirm email" on, Supabase returns no session until the emailed link is clicked.
      if (!data.session) return { user: null, needsConfirmation: true };
      return { user: await loadProfile().catch(() => null), needsConfirmation: false };
    },
    [loadProfile],
  );

  const requestPasswordReset = useCallback(async (email: string) => {
    const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo: `${WEB_URL}/reset-password` });
    if (error) throw error;
  }, []);

  const updateProfile = useCallback(async (changes: { full_name?: string; phone_number?: string | null }) => {
    const profile = (await authApi.updateMe(changes)).data;
    setUser(profile);
    return profile;
  }, []);

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    const { data } = await supabase.auth.getUser();
    const email = data.user?.email;
    if (!email) throw new Error('Your session has expired. Sign in again to change your password.');
    // Signing in again proves the current password; a wrong password leaves the session untouched.
    const check = await supabase.auth.signInWithPassword({ email, password: currentPassword });
    if (check.error) throw check.error;
    const { error } = await supabase.auth.updateUser({ password: newPassword, current_password: currentPassword });
    if (error) throw error;
  }, []);

  const logout = useCallback(async () => {
    await supabase.auth.signOut();
    userId.current = null;
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, isLoading, login, register, requestPasswordReset, updateProfile, changePassword, logout }),
    [user, isLoading, login, register, requestPasswordReset, updateProfile, changePassword, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}
