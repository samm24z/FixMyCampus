import Ionicons from '@expo/vector-icons/Ionicons';
import { useQuery } from '@tanstack/react-query';
import { router, useFocusEffect } from 'expo-router';
import React, { useCallback } from 'react';
import { Pressable, View } from 'react-native';
import { AppText } from '@/components/ui';
import { Spacing, useColors } from '@/constants/theme';
import { notificationsApi } from '@/lib/api';

export const UNREAD_COUNT_KEY = ['notifications', 'unread-count'] as const;

/** Header bell with a badge for unread notifications. Opens the notifications screen. */
export function NotificationBell() {
  const colors = useColors();
  const unread = useQuery({
    queryKey: UNREAD_COUNT_KEY,
    queryFn: async () => (await notificationsApi.unreadCount()).data.count,
    refetchInterval: 60_000,
  });
  const { refetch } = unread;

  // Refresh when the screen comes back into view (for example after reading notifications).
  useFocusEffect(
    useCallback(() => {
      void refetch();
    }, [refetch]),
  );

  const count = unread.data ?? 0;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={count > 0 ? `Notifications, ${count} unread` : 'Notifications'}
      hitSlop={8}
      onPress={() => router.push('/notifications')}
      style={({ pressed }) => ({ opacity: pressed ? 0.6 : 1, paddingHorizontal: Spacing.lg })}>
      <Ionicons name="notifications-outline" size={24} color={colors.text} />
      {count > 0 ? (
        <View
          style={{
            position: 'absolute',
            top: -4,
            right: Spacing.lg - 8,
            minWidth: 18,
            height: 18,
            borderRadius: 9,
            paddingHorizontal: 4,
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: colors.destructive,
          }}>
          <AppText variant="small" style={{ color: colors.destructiveText, fontSize: 11, fontWeight: '700' }}>
            {count > 9 ? '9+' : count}
          </AppText>
        </View>
      ) : null}
    </Pressable>
  );
}
