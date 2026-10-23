import React, { useState } from 'react';
import { View } from 'react-native';
import { Link } from 'expo-router';
import Ionicons from '@expo/vector-icons/Ionicons';
import { AppText, Badge, Button, Card, ErrorBanner, Screen, SegmentedChoice, TextField } from '@/components/ui';
import { MIN_PASSWORD_LENGTH } from '@/lib/account';
import { Spacing, useColors } from '@/constants/theme';
import { getApiError, useAuth } from '@/lib/auth';
import { CAMPUS, EMAIL_HINT, isCampusEmail } from '@/lib/config';

type SignUpRole = 'STUDENT' | 'FACULTY';
const ROLES: readonly SignUpRole[] = ['STUDENT', 'FACULTY'];

export default function RegisterScreen() {
  const colors = useColors();
  const { register } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<SignUpRole>('STUDENT');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [confirmationSentTo, setConfirmationSentTo] = useState('');

  async function submit() {
    if (submitting) return;
    setError('');
    if (fullName.trim().length < 2) {
      setError('Enter your full name.');
      return;
    }
    if (!isCampusEmail(email)) {
      setError(`Please use your ${CAMPUS.shortName} college email address (${EMAIL_HINT}).`);
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Your password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    setSubmitting(true);
    try {
      const result = await register({ full_name: fullName.trim(), email, password, role });
      // Without confirmation the user is signed in and the root layout switches stacks.
      if (result.needsConfirmation) setConfirmationSentTo(email.trim());
    } catch (registrationError) {
      setError(getApiError(registrationError, 'Registration failed. Please check your details.'));
    } finally {
      setSubmitting(false);
    }
  }

  if (confirmationSentTo) {
    return (
      <Screen>
        <Card style={{ alignItems: 'center' }}>
          <Ionicons name="mail-outline" size={40} color={colors.primary} />
          <AppText variant="heading">Check your email</AppText>
          <AppText variant="muted" style={{ textAlign: 'center' }}>
            We sent a confirmation link to {confirmationSentTo}. Open it, then sign in. It can take a minute to arrive; check spam too.
          </AppText>
          <Link href="/login" style={{ color: colors.primary, fontWeight: '600', paddingVertical: Spacing.sm }}>
            Go to Sign In
          </Link>
        </Card>
      </Screen>
    );
  }

  return (
    <Screen>
      <AppText variant="muted">
        Open to {CAMPUS.name} students and faculty with a @{CAMPUS.emailDomain} email. Staff accounts are created by an administrator.
      </AppText>
      <ErrorBanner message={error} />
      <TextField
        label="Full name"
        placeholder="Alex Morgan"
        value={fullName}
        onChangeText={setFullName}
        autoCapitalize="words"
        autoComplete="name"
        textContentType="name"
        returnKeyType="done"
      />
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
        returnKeyType="done"
      />
      <View style={{ gap: Spacing.xs }}>
        <AppText variant="label">I am a</AppText>
        <SegmentedChoice
          options={ROLES}
          value={role}
          onChange={setRole}
          labelFor={(option) => (option === 'STUDENT' ? 'Student' : 'Faculty')}
        />
      </View>
      <TextField
        label="Password"
        hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        placeholder="Choose a password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="new-password"
        textContentType="newPassword"
        returnKeyType="go"
        onSubmitEditing={submit}
      />
      <Button title={submitting ? 'Creating account...' : 'Create account'} loading={submitting} onPress={submit} />
      <View style={{ alignItems: 'center', gap: Spacing.md }}>
        <AppText variant="muted">
          Already have an account?{' '}
          <Link href="/login" style={{ color: colors.primary, fontWeight: '600' }}>
            Sign in
          </Link>
        </AppText>
        <Badge label={`${CAMPUS.name} email addresses only`} />
      </View>
    </Screen>
  );
}
