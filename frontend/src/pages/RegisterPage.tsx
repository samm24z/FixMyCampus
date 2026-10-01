import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { UserPlus, Mail, KeyRound, User, School } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ConfigBanner } from '@/components/auth/ConfigBanner';
import { getApiError, roleHome, useAuth } from '@/lib/auth';

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [form, setForm] = useState({ full_name: '', email: '', password: '', role: 'STUDENT' as 'STUDENT' | 'FACULTY' });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [confirmationSentTo, setConfirmationSentTo] = useState('');

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const result = await register(form);
      if (result.needsConfirmation) setConfirmationSentTo(form.email);
      else if (result.user) navigate(roleHome(result.user.role), { replace: true });
    } catch (registrationError) {
      setError(getApiError(registrationError, 'Registration failed. Please check your details.'));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (confirmationSentTo) {
    return (
      <div className="max-w-md mx-auto my-8">
        <Card className="shadow-lg border-indigo-500/10">
          <CardHeader className="space-y-1 text-center">
            <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary mb-2">
              <Mail className="w-6 h-6" />
            </div>
            <CardTitle className="text-2xl font-bold">Check your email</CardTitle>
            <CardDescription>
              We sent a confirmation link to <strong>{confirmationSentTo}</strong>. Click it, then sign in. It can take a minute to arrive; check spam too.
            </CardDescription>
          </CardHeader>
          <CardFooter className="justify-center border-t pt-4">
            <Link to="/login" className="text-primary font-semibold hover:underline text-sm">Go to Sign In</Link>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto my-8 space-y-6">
      <Card className="shadow-lg border-indigo-500/10">
        <CardHeader className="space-y-1 text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary mb-2">
            <UserPlus className="w-6 h-6" />
          </div>
          <CardTitle className="text-2xl font-bold">Create Campus Account</CardTitle>
          <CardDescription>
            Register as a Student or Faculty member. Staff accounts are created by an administrator.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
          <ConfigBanner />
          {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
          <div className="space-y-2">
            <label className="text-sm font-medium">Full Name</label>
            <div className="relative">
              <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Alex Morgan"
                className="w-full pl-9 pr-4 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                value={form.full_name}
                onChange={(event) => setForm({ ...form, full_name: event.target.value })}
                required
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Campus Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <input
                type="email"
                placeholder="alex.morgan@campus.edu"
                className="w-full pl-9 pr-4 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
                required
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Role</label>
            <div className="relative">
              <School className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <select
                className="w-full pl-9 pr-4 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                value={form.role}
                onChange={(event) => setForm({ ...form, role: event.target.value as 'STUDENT' | 'FACULTY' })}
              >
                <option value="STUDENT">Student</option>
                <option value="FACULTY">Faculty</option>
              </select>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Password</label>
            <div className="relative">
              <KeyRound className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <input
                type="password"
                placeholder="••••••••"
                className="w-full pl-9 pr-4 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                value={form.password}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
                minLength={8}
                required
              />
            </div>
          </div>
          <div className="pt-2">
            <Button className="w-full" type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Creating account...' : 'Create Account'}
            </Button>
          </div>
          </form>
        </CardContent>
        <CardFooter className="flex flex-col space-y-3 text-center text-sm border-t pt-4">
          <div className="text-muted-foreground">
            Already have an account?{' '}
            <Link to="/login" className="text-primary font-semibold hover:underline">
              Sign In
            </Link>
          </div>
          <Badge variant="outline" className="text-[11px] text-muted-foreground">
            Student and faculty registration
          </Badge>
        </CardFooter>
      </Card>
    </div>
  );
};
