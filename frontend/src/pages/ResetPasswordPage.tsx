import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { KeyRound } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getApiError, roleHome, useAuth } from '@/lib/auth';

/** Landing page of the emailed reset link: Supabase signs the user in with a recovery session, then they pick a new password. */
export const ResetPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, isLoading, updatePassword } = useAuth();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      await updatePassword(password);
      navigate(user ? roleHome(user.role) : '/login', { replace: true });
    } catch (updateError) {
      setError(getApiError(updateError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="max-w-md mx-auto my-8">
      <Card className="shadow-lg border-indigo-500/10">
        <CardHeader className="space-y-1 text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary mb-2"><KeyRound className="w-6 h-6" /></div>
          <CardTitle className="text-2xl font-bold">Choose a new password</CardTitle>
          <CardDescription>Open this page from the link in your password reset email.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-center text-sm text-muted-foreground">Checking your reset link...</p>
          ) : !user ? (
            <p className="text-center text-sm text-destructive">This reset link is invalid or has expired. Request a new one from the sign-in page.</p>
          ) : (
            <form className="space-y-4" onSubmit={handleSubmit}>
              {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
              <input type="password" required minLength={8} placeholder="New password (8+ characters)" value={password} onChange={(event) => setPassword(event.target.value)} className="w-full px-4 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              <Button className="w-full" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Saving...' : 'Update Password'}</Button>
            </form>
          )}
        </CardContent>
        <CardFooter className="justify-center border-t pt-4 text-sm"><Link to="/login" className="text-primary font-semibold hover:underline">Back to Sign In</Link></CardFooter>
      </Card>
    </div>
  );
};
