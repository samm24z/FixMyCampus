import React, { useCallback, useEffect, useState } from 'react';
import { Users } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { getApiError, departmentsApi, usersApi, type Department, type Paginated, type Role, type User } from '@/lib/api';
import { useAuth } from '@/lib/auth';

const ROLES: Role[] = ['STUDENT', 'FACULTY', 'STAFF', 'COORDINATOR', 'ADMIN'];
const field = 'rounded-lg border bg-background px-2 py-1.5 text-sm';

export const UserManagement: React.FC = () => {
  const { user: me } = useAuth();
  const [result, setResult] = useState<Paginated<User> | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<Role | ''>('');
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState({ full_name: '', email: '', password: '', role: 'STAFF' as Role, department_id: '' });

  const load = useCallback(() => {
    usersApi.list({ q: search, role: roleFilter, page, page_size: 10 })
      .then((response) => setResult(response.data))
      .catch((requestError) => setError(getApiError(requestError)));
  }, [search, roleFilter, page]);

  useEffect(() => { departmentsApi.list().then((response) => setDepartments(response.data)).catch(() => undefined); }, []);
  useEffect(() => { const timer = setTimeout(load, 250); return () => clearTimeout(timer); }, [load]);

  async function save(action: () => Promise<unknown>, after?: () => void) {
    setError('');
    try {
      await action();
      after?.();
      load();
    } catch (requestError) {
      setError(getApiError(requestError));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Users className="h-5 w-5 text-primary" /> User Management</CardTitle>
        <CardDescription>Create staff and coordinator accounts, change roles, and deactivate accounts. Staff must belong to a department.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}

        <form
          className="grid gap-2 rounded-lg border p-3 sm:grid-cols-6"
          onSubmit={(event) => { event.preventDefault(); void save(() => usersApi.create({ ...draft, department_id: draft.department_id || null }), () => setDraft({ ...draft, full_name: '', email: '', password: '' })); }}
        >
          <input required placeholder="Full name" value={draft.full_name} onChange={(event) => setDraft({ ...draft, full_name: event.target.value })} className={`${field} sm:col-span-2`} />
          <input required type="email" placeholder="Email" value={draft.email} onChange={(event) => setDraft({ ...draft, email: event.target.value })} className={`${field} sm:col-span-2`} />
          <input required minLength={8} type="password" placeholder="Initial password" value={draft.password} onChange={(event) => setDraft({ ...draft, password: event.target.value })} className={`${field} sm:col-span-2`} />
          <select value={draft.role} onChange={(event) => setDraft({ ...draft, role: event.target.value as Role })} className={`${field} sm:col-span-2`}>{ROLES.map((role) => <option key={role}>{role}</option>)}</select>
          <select value={draft.department_id} onChange={(event) => setDraft({ ...draft, department_id: event.target.value })} className={`${field} sm:col-span-2`}><option value="">No department</option>{departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}</select>
          <Button type="submit" size="sm" className="sm:col-span-2">Add User</Button>
        </form>

        <div className="flex flex-col gap-2 sm:flex-row">
          <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search name or email" className={`${field} flex-1`} />
          <select value={roleFilter} onChange={(event) => { setRoleFilter(event.target.value as Role | ''); setPage(1); }} className={field} aria-label="Filter by role"><option value="">All roles</option>{ROLES.map((role) => <option key={role}>{role}</option>)}</select>
        </div>

        <div className="space-y-2">
          {result?.items.map((account) => {
            const isSelf = account.id === me?.id;
            return (
              <div key={account.id} className="grid items-center gap-2 rounded-lg border p-3 text-sm sm:grid-cols-12">
                <div className="sm:col-span-4"><p className="font-medium">{account.full_name} {isSelf && <Badge variant="outline">You</Badge>}</p><p className="text-xs text-muted-foreground">{account.email}</p></div>
                <select disabled={isSelf} value={account.role} onChange={(event) => void save(() => usersApi.update(account.id, { role: event.target.value as Role }))} className={`${field} sm:col-span-2`} aria-label={`Role for ${account.full_name}`}>{ROLES.map((role) => <option key={role}>{role}</option>)}</select>
                <select value={account.department_id ?? ''} onChange={(event) => void save(() => usersApi.update(account.id, { department_id: event.target.value || null }))} className={`${field} sm:col-span-3`} aria-label={`Department for ${account.full_name}`}><option value="">No department</option>{departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}</select>
                <div className="sm:col-span-3 flex items-center justify-between gap-2"><Badge variant={account.is_active ? 'success' : 'secondary'}>{account.is_active ? 'Active' : 'Inactive'}</Badge><Button variant="outline" size="sm" disabled={isSelf} onClick={() => void save(() => usersApi.update(account.id, { is_active: !account.is_active }))}>{account.is_active ? 'Deactivate' : 'Reactivate'}</Button></div>
              </div>
            );
          })}
          {result && result.items.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No users match.</p>}
        </div>
        {result && result.total_pages > 1 && <div className="flex items-center justify-between text-sm text-muted-foreground"><span>{result.total} users - page {result.page} of {result.total_pages}</span><div className="flex gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={page >= result.total_pages} onClick={() => setPage(page + 1)}>Next</Button></div></div>}
      </CardContent>
    </Card>
  );
};
