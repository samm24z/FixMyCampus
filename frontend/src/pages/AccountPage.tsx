import React, { useEffect, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ArrowLeft, Check, ChevronRight, CircleUserRound, IdCard, Lock, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { UserAvatar } from '@/components/UserAvatar';
import { getApiError, useAuth } from '@/lib/auth';
import { departmentsApi, type User } from '@/lib/api';
import { roleLabel } from '@/lib/tickets';
import { MIN_PASSWORD_LENGTH, nameProblem, passwordErrorMessage, passwordProblem, phoneProblem } from '@/lib/account';

type Section = 'home' | 'personal-info' | 'security';

const SECTIONS: { id: Section; label: string; icon: typeof Lock; to: string }[] = [
  { id: 'home', label: 'Home', icon: CircleUserRound, to: '/account' },
  { id: 'personal-info', label: 'Personal info', icon: IdCard, to: '/account/personal-info' },
  { id: 'security', label: 'Security', icon: Lock, to: '/account/security' },
];

const inputClass = 'w-full rounded-lg border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary';

/** myaccount.google.com-style page: Home, Personal info and Security for the signed-in user. */
export const AccountPage: React.FC = () => {
  const { section = 'home' } = useParams();
  const { user } = useAuth();
  if (!user) return null; // ProtectedRoute guarantees a user
  if (!SECTIONS.some((item) => item.id === section)) return <Navigate to="/account" replace />;
  const current = section as Section;

  return (
    <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-[15rem_1fr] md:gap-10">
      <nav aria-label="Account sections" className="-mx-4 overflow-x-auto border-b md:mx-0 md:border-b-0">
        <ul className="flex min-w-max px-4 md:min-w-0 md:flex-col md:gap-1 md:px-0">
          {SECTIONS.map(({ id, label, icon: Icon, to }) => (
            <li key={id}>
              <Link
                to={to}
                aria-current={current === id ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-4 whitespace-nowrap px-4 py-3 text-sm font-medium transition-colors',
                  'border-b-[3px] border-transparent text-muted-foreground hover:text-foreground',
                  'md:rounded-r-full md:border-b-0 md:pl-6 md:hover:bg-accent',
                  current === id && 'border-primary text-primary hover:text-primary md:bg-primary/10 md:hover:bg-primary/15',
                )}
              >
                <Icon className="hidden h-5 w-5 md:block" />
                {label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <div className="min-w-0 pb-10">
        {current === 'home' && <HomeSection user={user} />}
        {current === 'personal-info' && <PersonalInfoSection key={user.id} user={user} />}
        {current === 'security' && <SecuritySection key={user.id} user={user} />}
      </div>
    </div>
  );
};

// ----------------------------------------------------------------- building blocks

const SectionHeading: React.FC<{ title: string; subtitle: string }> = ({ title, subtitle }) => (
  <div className="mb-6 text-center">
    <h1 className="text-2xl font-bold tracking-tight md:text-3xl">{title}</h1>
    <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
  </div>
);

const InfoCard: React.FC<{ title: string; description?: string; children: React.ReactNode; footer?: React.ReactNode }> = ({ title, description, children, footer }) => (
  <section className="mb-6 overflow-hidden rounded-2xl border bg-card">
    <div className="px-6 pb-2 pt-5">
      <h2 className="text-lg font-bold tracking-tight">{title}</h2>
      {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
    </div>
    <div className="divide-y">{children}</div>
    {footer && <div className="border-t px-6 py-4 text-xs text-muted-foreground">{footer}</div>}
  </section>
);

/** A label/value row; clickable rows open their edit view. */
const InfoRow: React.FC<{ label: string; value: React.ReactNode; onClick?: () => void; locked?: boolean }> = ({ label, value, onClick, locked }) => {
  const body = (
    <>
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground sm:w-40 sm:shrink-0 sm:text-sm sm:normal-case sm:tracking-normal">{label}</span>
      <span className="min-w-0 flex-1 break-words text-sm">{value}</span>
    </>
  );
  if (!onClick) {
    return (
      <div className="flex items-center gap-3 px-6 py-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center">{body}</div>
        {locked && <Lock className="h-4 w-4 shrink-0 text-muted-foreground" aria-label="Can't be changed here" />}
      </div>
    );
  }
  return (
    <button type="button" onClick={onClick} className="flex w-full items-center gap-3 px-6 py-4 text-left transition-colors hover:bg-accent focus-visible:bg-accent focus-visible:outline-none">
      <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center">{body}</div>
      <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground" />
    </button>
  );
};

const EditView: React.FC<{ title: string; onBack: () => void; children: React.ReactNode }> = ({ title, onBack, children }) => (
  <div>
    <div className="mb-6 flex items-center gap-2">
      <button type="button" onClick={onBack} aria-label="Back" className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-accent">
        <ArrowLeft className="h-5 w-5" />
      </button>
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
    </div>
    <div className="rounded-2xl border bg-card p-6">{children}</div>
  </div>
);

const ErrorBox: React.FC<{ message: string }> = ({ message }) =>
  message ? <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{message}</div> : null;

const SuccessBox: React.FC<{ message: string }> = ({ message }) =>
  message ? (
    <div role="status" className="mb-6 flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-400">
      <Check className="h-4 w-4 shrink-0" />
      {message}
    </div>
  ) : null;

const FormActions: React.FC<{ onCancel: () => void; saving: boolean }> = ({ onCancel, saving }) => (
  <div className="flex justify-end gap-2 pt-2">
    <Button type="button" variant="ghost" className="rounded-full text-primary" onClick={onCancel} disabled={saving}>Cancel</Button>
    <Button type="submit" className="rounded-full px-6" disabled={saving}>{saving ? 'Saving...' : 'Save'}</Button>
  </div>
);

// ----------------------------------------------------------------- sections

const HomeSection: React.FC<{ user: User }> = ({ user }) => (
  <div>
    <div className="mb-8 flex flex-col items-center text-center">
      <UserAvatar user={user} className="mb-4 h-24 w-24 text-4xl" />
      <h1 className="text-2xl font-bold tracking-tight md:text-3xl">Welcome, {user.full_name}</h1>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">Manage your info and password to make FixMyCampus work better for you.</p>
    </div>
    <div className="grid gap-4 sm:grid-cols-2">
      <HomeCard to="/account/personal-info" icon={IdCard} title="Personal info" text="See your name, phone number, role and department." action="Manage your personal info" />
      <HomeCard to="/account/security" icon={ShieldCheck} title="Security" text="Change your password to keep your account safe." action="Manage your security" />
    </div>
  </div>
);

const HomeCard: React.FC<{ to: string; icon: typeof Lock; title: string; text: string; action: string }> = ({ to, icon: Icon, title, text, action }) => (
  <Link to={to} className="group flex flex-col rounded-2xl border bg-card transition-shadow hover:shadow-md">
    <div className="flex flex-1 gap-4 p-6">
      <div className="min-w-0 flex-1">
        <h2 className="text-lg font-bold tracking-tight">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{text}</p>
      </div>
      <Icon className="h-12 w-12 shrink-0 text-primary/70" strokeWidth={1.25} />
    </div>
    <span className="border-t px-6 py-3 text-sm font-medium text-primary group-hover:underline">{action}</span>
  </Link>
);

const PersonalInfoSection: React.FC<{ user: User }> = ({ user }) => {
  const { updateProfile } = useAuth();
  const [editing, setEditing] = useState<'name' | 'phone' | null>(null);
  const [value, setValue] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [saving, setSaving] = useState(false);
  const [department, setDepartment] = useState<string | null>(null);

  useEffect(() => {
    if (!user.department_id) return;
    let active = true;
    departmentsApi.list()
      .then(({ data }) => active && setDepartment(data.find((item) => item.id === user.department_id)?.name ?? null))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [user.department_id]);

  function open(field: 'name' | 'phone') {
    setEditing(field);
    setValue(field === 'name' ? user.full_name : user.phone_number ?? '');
    setError('');
    setSaved('');
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    const problem = editing === 'name' ? nameProblem(value) : phoneProblem(value);
    if (problem) return setError(problem);
    setSaving(true);
    setError('');
    try {
      if (editing === 'name') await updateProfile({ full_name: value.trim() });
      else await updateProfile({ phone_number: value.trim() || null });
      setSaved(editing === 'name' ? 'Your name was updated.' : value.trim() ? 'Your phone number was updated.' : 'Your phone number was removed.');
      setEditing(null);
    } catch (saveError) {
      setError(getApiError(saveError, "Your changes couldn't be saved. Please try again."));
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    const isName = editing === 'name';
    return (
      <EditView title={isName ? 'Name' : 'Phone number'} onBack={() => setEditing(null)}>
        <form className="space-y-4" onSubmit={handleSave} noValidate>
          <p className="text-sm text-muted-foreground">
            {isName
              ? 'Your name is shown on your reports and to the staff who handle them.'
              : 'Staff may use this number to reach you about your reports. Leave it empty to remove it.'}
          </p>
          <ErrorBox message={error} />
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">{isName ? 'Name' : 'Phone number'}</span>
            <input
              autoFocus
              className={inputClass}
              type={isName ? 'text' : 'tel'}
              autoComplete={isName ? 'name' : 'tel'}
              maxLength={isName ? 150 : 30}
              placeholder={isName ? undefined : '+91 98765 43210'}
              value={value}
              onChange={(event) => setValue(event.target.value)}
            />
          </label>
          <FormActions onCancel={() => setEditing(null)} saving={saving} />
        </form>
      </EditView>
    );
  }

  return (
    <div>
      <SectionHeading title="Personal info" subtitle="Info about you and your place on campus" />
      <SuccessBox message={saved} />
      <InfoCard title="Basic info" description="You can change these yourself.">
        <InfoRow label="Name" value={user.full_name} onClick={() => open('name')} />
        <InfoRow label="Phone" value={user.phone_number || <span className="text-muted-foreground">Add a phone number</span>} onClick={() => open('phone')} />
      </InfoCard>
      <InfoCard
        title="Campus info"
        footer="Your email is how you sign in, so it can't be changed. Your role and department are set by a campus administrator; contact them if something here is wrong."
      >
        <InfoRow label="Email" value={user.email} locked />
        <InfoRow label="Role" value={roleLabel(user.role)} locked />
        <InfoRow label="Department" value={user.department_id ? department ?? '...' : <span className="text-muted-foreground">None</span>} locked />
      </InfoCard>
    </div>
  );
};

const SecuritySection: React.FC<{ user: User }> = ({ user }) => {
  const { changePassword } = useAuth();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ current: '', next: '', confirm: '' });
  const [showPasswords, setShowPasswords] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [saving, setSaving] = useState(false);

  function open() {
    setForm({ current: '', next: '', confirm: '' });
    setShowPasswords(false);
    setError('');
    setSaved('');
    setEditing(true);
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    const problem = passwordProblem(form.current, form.next, form.confirm);
    if (problem) return setError(problem);
    setSaving(true);
    setError('');
    try {
      await changePassword(form.current, form.next);
      setSaved('Your password was changed. Use your new password the next time you sign in.');
      setEditing(false);
    } catch (changeError) {
      setError(passwordErrorMessage(changeError));
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    const type = showPasswords ? 'text' : 'password';
    const field = (key: keyof typeof form, label: string, autoComplete: string, autoFocus = false) => (
      <label className="block space-y-1.5">
        <span className="text-sm font-medium">{label}</span>
        <input
          autoFocus={autoFocus}
          className={inputClass}
          type={type}
          autoComplete={autoComplete}
          value={form[key]}
          onChange={(event) => setForm((previous) => ({ ...previous, [key]: event.target.value }))}
        />
      </label>
    );
    return (
      <EditView title="Password" onBack={() => setEditing(false)}>
        <form className="space-y-4" onSubmit={handleSave} noValidate>
          {/* Lets password managers file the new password under the right account. */}
          <input type="email" autoComplete="username" value={user.email} readOnly hidden />
          <p className="text-sm text-muted-foreground">
            Choose a strong password you don't use anywhere else. It must be at least {MIN_PASSWORD_LENGTH} characters.
          </p>
          <ErrorBox message={error} />
          {field('current', 'Current password', 'current-password', true)}
          {field('next', 'New password', 'new-password')}
          {field('confirm', 'Confirm new password', 'new-password')}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={showPasswords} onChange={(event) => setShowPasswords(event.target.checked)} />
            Show passwords
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" className="rounded-full text-primary" onClick={() => setEditing(false)} disabled={saving}>Cancel</Button>
            <Button type="submit" className="rounded-full px-6" disabled={saving}>{saving ? 'Changing...' : 'Change password'}</Button>
          </div>
        </form>
      </EditView>
    );
  }

  return (
    <div>
      <SectionHeading title="Security" subtitle="Settings to help you keep your account secure" />
      <SuccessBox message={saved} />
      <InfoCard title="How you sign in to FixMyCampus" description="Make sure you can always get into your account.">
        <InfoRow label="Email" value={user.email} locked />
        <InfoRow label="Password" value={<span aria-label="Hidden">••••••••</span>} onClick={open} />
      </InfoCard>
      <p className="px-2 text-xs text-muted-foreground">
        Forgot your password? Sign out and use <span className="font-medium">Forgot password</span> on the sign-in page to get a reset link by email.
      </p>
    </div>
  );
};
