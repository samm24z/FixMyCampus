-- Supabase "Before User Created" auth hook: only @mvsrec.edu.in emails may sign up.
--
-- Installed once per Supabase project, then switched on in the dashboard:
--   Authentication -> Hooks -> Before User Created -> Postgres function -> public.hook_restrict_signup_domain
--
-- This is the outermost layer. The register form and the backend (ALLOWED_EMAIL_DOMAINS) enforce
-- the same rule, so keep the domain below in sync with them.

create or replace function public.hook_restrict_signup_domain(event jsonb)
returns jsonb
language plpgsql
as $$
declare
  signup_email text := lower(coalesce(event->'user'->>'email', ''));
begin
  if signup_email = '' or position('@' in signup_email) = 0
     or split_part(signup_email, '@', 2) <> 'mvsrec.edu.in' then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'Sign-up is limited to @mvsrec.edu.in email addresses.'
    ));
  end if;
  return '{}'::jsonb;
end;
$$;

-- Only Supabase's auth service may call it (not the public API keys).
grant execute on function public.hook_restrict_signup_domain(jsonb) to supabase_auth_admin;
revoke execute on function public.hook_restrict_signup_domain(jsonb) from authenticated, anon, public;
