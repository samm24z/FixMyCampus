import React from 'react';
import { supabaseConfigured } from '@/lib/supabase';

/** Shown on auth screens until frontend/.env points at a Supabase project. */
export const ConfigBanner: React.FC = () =>
  supabaseConfigured ? null : (
    <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
      Sign-in is not configured yet. Set <code>VITE_SUPABASE_URL</code> and <code>VITE_SUPABASE_ANON_KEY</code> in{' '}
      <code>frontend/.env</code> and restart the dev server.
    </div>
  );
