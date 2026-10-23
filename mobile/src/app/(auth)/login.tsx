import React, { useState } from 'react';
import { View } from 'react-native';
import { Link, useRouter } from 'expo-router';
import { AuthBrand } from '@/components/account/AuthBrand';
import { AppText, Badge, Button, ErrorBanner, Screen, TextField } from '@/components/ui';
import { Spacing, useColors } from '@/constants/theme';
import { getApiError, useAuth } from '@/lib/auth';
import { CAMPUS, EMAIL_HINT } from '@/lib/config';

export default function LoginScreen() {
  const router = useRouter();
  const colors = useColors();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (submitting) return;
    setError('');
    if (!email.trim() || !password) {
      setError('Enter your email and password.');
      return;
    }
    setSubmitting(true);
    try {
      await login(email, password); // the root layout switches stacks once the user is set
    } catch (loginError) {
      setError(getApiError(loginError, 'Invalid email or password.'));
      setSubmitting(false);
    }
  }

  return (
    <Screen>
      <AuthBrand />
      <AppText variant="muted" style={{ textAlign: 'center' }}>
        Sign in with your {CAMPUS.shortName} college email to report and track campus issues.
      </AppText>
      <ErrorBanner message={error} />
      <TextField
        label="College email"
        placeholder={EMAIL_HINT}
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="email"
        textContentType="username"
        returnKeyType="done"
      />
      <TextField
        label="Password"
        placeholder="Your password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="current-password"
        textContentType="password"
        returnKeyType="go"
        onSubmitEditing={submit}
      />
      <Button title={submitting ? 'Signing in...' : 'Sign in'} loading={submitting} onPress={submit} />
      <Button title="Forgot password?" variant="ghost" onPress={() => router.push('/forgot-password')} />
      <View style={{ alignItems: 'center', gap: Spacing.md }}>
        <AppText variant="muted">
          Don't have an account?{' '}
          <Link href="/register" style={{ color: colors.primary, fontWeight: '600' }}>
            Register here
          </Link>
        </AppText>
        <Badge label={CAMPUS.name} />
      </View>
    </Screen>
  );
}
