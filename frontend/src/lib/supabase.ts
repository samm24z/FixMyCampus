import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

/** False until frontend/.env has the project URL and the public (anon / publishable) key. */
export const supabaseConfigured = Boolean(url && anonKey);

// Supabase Auth owns sign-up, sign-in, password reset and token refresh. Only the public
// anon key is used here; the browser never talks to the database directly (all data goes
// through our API, which enforces roles).
export const supabase = createClient(url || 'http://localhost:54321', anonKey || 'not-configured', {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
});
