import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { avatarColour, initials } from '@/lib/account';

export function Avatar({ name, size = 88 }: { name: string; size?: number }) {
  return (
    <View
      accessibilityLabel={`Avatar for ${name}`}
      style={[styles.circle, { width: size, height: size, borderRadius: size / 2, backgroundColor: avatarColour(name) }]}>
      <Text style={{ color: '#FFFFFF', fontSize: size * 0.4, fontWeight: '600' }}>{initials(name)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({ circle: { alignItems: 'center', justifyContent: 'center' } });
