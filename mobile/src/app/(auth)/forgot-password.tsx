import React, { useState } from 'react';
import { AppText, Button, ErrorBanner, NoticeBanner, Screen, TextField } from '@/components/ui';
import { getApiError, useAuth } from '@/lib/auth';
import { EMAIL_HINT } from '@/lib/config';

export default function ForgotPasswordScreen() {
  const { requestPasswordReset } = useAuth();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (submitting) return;
    setError('');
    setNotice('');
    if (!email.trim()) {
      setError('Enter your college email first.');
      return;
    }
    setSubmitting(true);
    try {
      await requestPasswordReset(email);
      setNotice(
        'If that email has an account, a password reset link is on its way. The link opens in your browser, where you can choose a new password; then come back here and sign in.',
      );
    } catch (resetError) {
      setError(getApiError(resetError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Screen>
      <AppText variant="muted">Enter your college email and we'll send you a link to reset your password.</AppText>
      <ErrorBanner message={error} />
      <NoticeBanner message={notice} />
      <TextField
        label="College email"
        placeholder={EMAIL_HINT}
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="email"
        textContentType="emailAddress"
        returnKeyType="send"
        onSubmitEditing={submit}
      />
      <Button title={submitting ? 'Sending...' : 'Send reset link'} loading={submitting} onPress={submit} />
    </Screen>
  );
}
