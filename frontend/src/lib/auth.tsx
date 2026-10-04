import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { authApi, getApiError, type Role, type User } from './api';
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
  requestPasswordReset: (email: string) => Promise<void>;
  updatePassword: (password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Landing page for each role after sign-in. */
export function roleHome(role: Role): string {
  if (role === 'ADMIN') return '/admin';
  if (role === 'STAFF' || role === 'COORDINATOR') return '/staff';
  return '/dashboard';
}

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
      // Supabase re-emits SIGNED_IN when the tab regains focus; only reload for a different user.
      // Deferred with setTimeout because calling Supabase from inside this callback can deadlock.
      if (event === 'SIGNED_IN' && userId.current !== session.user.id) setTimeout(() => void loadProfile().catch(() => undefined), 0);
    });
    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, [loadProfile]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
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
        email: form.email,
        password: form.password,
        options: {
          data: { full_name: form.full_name, role: form.role },
          emailRedirectTo: `${window.location.origin}/login`,
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
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    if (error) throw error;
  }, []);

  const updatePassword = useCallback(async (password: string) => {
    const { error } = await supabase.auth.updateUser({ password });
    if (error) throw error;
  }, []);

  const logout = useCallback(async () => {
    await supabase.auth.signOut();
    userId.current = null;
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, isLoading, login, register, requestPasswordReset, updatePassword, logout }),
    [user, isLoading, login, register, requestPasswordReset, updatePassword, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}

/** Redirects anonymous users to /login and users without a matching role to their own home. */
export const ProtectedRoute: React.FC<{ roles?: Role[]; children: React.ReactNode }> = ({ roles, children }) => {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) return <p className="py-16 text-center text-sm text-muted-foreground">Loading...</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to={roleHome(user.role)} replace />;
  return <>{children}</>;
};
