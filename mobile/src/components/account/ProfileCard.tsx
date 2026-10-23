import React, { useEffect, useState } from 'react';
import { View } from 'react-native';
import { AppText, Badge, Button, Card, ErrorBanner, NoticeBanner, TextField } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { departmentsApi, type User } from '@/lib/api';
import { nameProblem, phoneProblem } from '@/lib/account';
import { getApiError, useAuth } from '@/lib/auth';
import { roleLabel } from '@/lib/tickets';
import { Avatar } from './Avatar';

/** Header with avatar, name, email and role, plus editable name / phone. */
export function ProfileCard({ user }: { user: User }) {
  const { updateProfile } = useAuth();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone_number ?? '');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [saving, setSaving] = useState(false);
  const [department, setDepartment] = useState<string | null>(null);

  useEffect(() => {
    if (!user.department_id) return;
    let active = true;
    departmentsApi
      .list()
      .then(({ data }) => active && setDepartment(data.find((item) => item.id === user.department_id)?.name ?? null))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [user.department_id]);

  function startEditing() {
    setName(user.full_name);
    setPhone(user.phone_number ?? '');
    setError('');
    setSaved('');
    setEditing(true);
  }

  async function save() {
    const problem = nameProblem(name) || phoneProblem(phone);
    if (problem) return setError(problem);
    setSaving(true);
    setError('');
    try {
      await updateProfile({ full_name: name.trim().replace(/\s+/g, ' '), phone_number: phone.trim() || null });
      setSaved('Your profile was updated.');
      setEditing(false);
    } catch (saveError) {
      setError(getApiError(saveError, "Your changes couldn't be saved. Please try again."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <View style={{ alignItems: 'center', gap: Spacing.sm }}>
        <Avatar name={user.full_name} />
        <AppText variant="heading">{user.full_name}</AppText>
        <AppText variant="muted">{user.email}</AppText>
        <Badge label={roleLabel(user.role)} tone="primary" />
      </View>
      <NoticeBanner message={saved} />

      {editing ? (
        <View style={{ gap: Spacing.md }}>
          <ErrorBanner message={error} />
          <TextField
            label="Name"
            value={name}
            onChangeText={setName}
            autoCapitalize="words"
            autoComplete="name"
            textContentType="name"
            maxLength={150}
            returnKeyType="next"
          />
          <TextField
            label="Phone number"
            hint="Staff may use this to reach you about your reports. Leave empty to remove it."
            value={phone}
            onChangeText={setPhone}
            placeholder="+91 98765 43210"
            keyboardType="phone-pad"
            autoComplete="tel"
            textContentType="telephoneNumber"
            maxLength={30}
            returnKeyType="done"
            onSubmitEditing={save}
          />
          <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
            <Button title="Cancel" variant="outline" disabled={saving} onPress={() => setEditing(false)} style={{ flex: 1 }} />
            <Button title={saving ? 'Saving...' : 'Save'} loading={saving} onPress={save} style={{ flex: 1 }} />
          </View>
        </View>
      ) : (
        <View style={{ gap: Spacing.md }}>
          <Row label="Phone" value={user.phone_number || 'Not added'} />
          <Row label="Department" value={user.department_id ? department ?? '...' : 'None'} />
          <AppText variant="small">
            Your email, role and department are set by a campus administrator; contact them if something here is wrong.
          </AppText>
          <Button title="Edit profile" variant="outline" onPress={startEditing} />
        </View>
      )}
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: Spacing.md }}>
      <AppText variant="muted">{label}</AppText>
      <AppText style={{ flexShrink: 1, textAlign: 'right' }}>{value}</AppText>
    </View>
  );
}
