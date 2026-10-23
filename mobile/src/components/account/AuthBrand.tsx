import React from 'react';
import { StyleSheet, View } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { AppText } from '@/components/ui';
import { FontSize, Radius, Spacing, useColors } from '@/constants/theme';
import { CAMPUS } from '@/lib/config';

/** Branded top of the login screen (which has no navigator header). */
export function AuthBrand() {
  const colors = useColors();
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.wrap, { paddingTop: insets.top + Spacing.xl }]}>
      <View style={[styles.logo, { backgroundColor: colors.primary }]}>
        <Ionicons name="construct" size={32} color={colors.primaryText} />
      </View>
      <AppText variant="title">FixMyCampus</AppText>
      <AppText variant="muted" style={{ fontSize: FontSize.sm }}>{CAMPUS.name}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', gap: Spacing.xs, paddingBottom: Spacing.md },
  logo: { width: 64, height: 64, borderRadius: Radius.lg, alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.sm },
});
