import React, { useState } from 'react';
import { Pressable, View } from 'react-native';
import { AppText, Button, Card, ErrorBanner, NoticeBanner, TextField } from '@/components/ui';
import { Spacing, useColors } from '@/constants/theme';
import { MIN_PASSWORD_LENGTH, passwordErrorMessage, passwordProblem } from '@/lib/account';
import { useAuth } from '@/lib/auth';

export function PasswordCard() {
  const { changePassword } = useAuth();
  const colors = useColors();
  const [editing, setEditing] = useState(false);
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [saving, setSaving] = useState(false);

  function open() {
    setCurrent('');
    setNext('');
    setConfirm('');
    setShow(false);
    setError('');
    setSaved('');
    setEditing(true);
  }

  async function save() {
    const problem = passwordProblem(current, next, confirm);
    if (problem) return setError(problem);
    setSaving(true);
    setError('');
    try {
      await changePassword(current, next);
      setSaved('Your password was changed. Use your new password the next time you sign in.');
      setEditing(false);
    } catch (changeError) {
      setError(passwordErrorMessage(changeError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <AppText variant="heading">Password</AppText>
      <NoticeBanner message={saved} />
      {editing ? (
        <View style={{ gap: Spacing.md }}>
          <AppText variant="muted">
            Choose a strong password you don't use anywhere else. It must be at least {MIN_PASSWORD_LENGTH} characters.
          </AppText>
          <ErrorBanner message={error} />
          <TextField
            label="Current password"
            value={current}
            onChangeText={setCurrent}
            secureTextEntry={!show}
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="current-password"
            textContentType="password"
        returnKeyType="done"
          />
          <TextField
            label="New password"
            value={next}
            onChangeText={setNext}
            secureTextEntry={!show}
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="new-password"
            textContentType="newPassword"
        returnKeyType="done"
          />
          <TextField
            label="Confirm new password"
            value={confirm}
            onChangeText={setConfirm}
            secureTextEntry={!show}
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="new-password"
            textContentType="newPassword"
            returnKeyType="done"
            onSubmitEditing={save}
          />
          <Pressable onPress={() => setShow((value) => !value)} accessibilityRole="checkbox" accessibilityState={{ checked: show }}>
            <AppText variant="muted" style={{ color: colors.primary }}>{show ? 'Hide passwords' : 'Show passwords'}</AppText>
          </Pressable>
          <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
            <Button title="Cancel" variant="outline" disabled={saving} onPress={() => setEditing(false)} style={{ flex: 1 }} />
            <Button title={saving ? 'Changing...' : 'Change password'} loading={saving} onPress={save} style={{ flex: 1 }} />
          </View>
        </View>
      ) : (
        <View style={{ gap: Spacing.md }}>
          <AppText variant="muted">Forgot it? Sign out and use "Forgot password?" on the sign-in screen to get a reset link.</AppText>
          <Button title="Change password" variant="outline" onPress={open} />
        </View>
      )}
    </Card>
  );
}
