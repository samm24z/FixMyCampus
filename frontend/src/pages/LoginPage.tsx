import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LogIn, KeyRound, Mail, ShieldAlert } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ConfigBanner } from '@/components/auth/ConfigBanner';
import { getApiError, roleHome, useAuth } from '@/lib/auth';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, login, requestPasswordReset } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Also covers arriving from the email-confirmation link, which signs the user in on this page.
  useEffect(() => {
    if (user) {
      const destination = (location.state as { from?: string } | null)?.from || roleHome(user.role);
      navigate(destination, { replace: true });
    }
  }, [user, location.state, navigate]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setNotice('');
    setIsSubmitting(true);
    try {
      await login(email, password);
    } catch (loginError) {
      setError(getApiError(loginError, 'Invalid email or password.'));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleForgotPassword() {
    setError('');
    setNotice('');
    if (!email) {
      setError('Enter your email above first, then choose "Forgot password?".');
      return;
    }
    try {
      await requestPasswordReset(email);
      setNotice('If that email has an account, a password reset link is on its way.');
    } catch (resetError) {
      setError(getApiError(resetError));
    }
  }

  return (
    <div className="max-w-md mx-auto my-8 space-y-6">
      <Card className="shadow-lg border-indigo-500/10">
        <CardHeader className="space-y-1 text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary mb-2">
            <LogIn className="w-6 h-6" />
          </div>
          <CardTitle className="text-2xl font-bold">Sign In</CardTitle>
          <CardDescription>
            Enter your institutional email to access your campus grievance portal.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
          <ConfigBanner />
          {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
          {notice && <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm">{notice}</div>}
          <div className="space-y-2">
            <label className="text-sm font-medium">Campus Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <input
                type="email"
                placeholder="student@campus.edu"
                className="w-full pl-9 pr-4 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
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
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
          </div>
          <div className="pt-2 space-y-3">
            <Button className="w-full" type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Signing in...' : 'Sign In'}
            </Button>
            <button type="button" onClick={handleForgotPassword} className="w-full text-center text-xs text-primary hover:underline">
              Forgot password?
            </button>
          </div>
          </form>
        </CardContent>
        <CardFooter className="flex flex-col space-y-3 text-center text-sm border-t pt-4">
          <div className="text-muted-foreground">
            Don't have an account?{' '}
            <Link to="/register" className="text-primary font-semibold hover:underline">
              Register here
            </Link>
          </div>
          <Badge variant="outline" className="text-[11px] text-muted-foreground">
            Secure campus account access
          </Badge>
        </CardFooter>
      </Card>
    </div>
  );
};
