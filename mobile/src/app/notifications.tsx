import Ionicons from '@expo/vector-icons/Ionicons';
import { useInfiniteQuery, useMutation, useQueryClient, type InfiniteData } from '@tanstack/react-query';
import { router, Stack } from 'expo-router';
import React, { useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, View } from 'react-native';
import { UNREAD_COUNT_KEY } from '@/components/notifications/NotificationBell';
import { timeAgo } from '@/components/notifications/format';
import { AppText, Card, EmptyState, ErrorBanner, Loading, Screen } from '@/components/ui';
import { Spacing, useColors } from '@/constants/theme';
import { getApiError, notificationsApi, type AppNotification, type NotificationType, type Paginated } from '@/lib/api';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

const ICONS: Record<NotificationType, IconName> = {
  TICKET_CREATED: 'add-circle-outline',
  STATUS_CHANGED: 'swap-horizontal-outline',
  ASSIGNED: 'person-outline',
  SLA_WARNING: 'time-outline',
  SLA_BREACH: 'alert-circle-outline',
  FEEDBACK_REQUEST: 'star-outline',
  FEEDBACK_RECEIVED: 'chatbox-ellipses-outline',
  COMMENT_ADDED: 'chatbubble-outline',
};

const LIST_KEY = ['notifications', 'list'] as const;
const PAGE_SIZE = 20;

type NotificationPages = InfiniteData<Paginated<AppNotification>>;

function NotificationRow({ item, onPress }: { item: AppNotification; onPress: () => void }) {
  const colors = useColors();
  const urgent = item.type === 'SLA_BREACH' || item.type === 'SLA_WARNING';
  const iconColor = urgent ? colors.danger : colors.primary;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${item.is_read ? '' : 'Unread. '}${item.title}`}
      onPress={onPress}
      style={({ pressed }) => ({ opacity: pressed ? 0.8 : 1 })}>
      <Card style={{ flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.md }}>
        <Ionicons name={ICONS[item.type] ?? 'notifications-outline'} size={22} color={iconColor} style={{ marginTop: 2 }} />
        <View style={{ flex: 1, gap: Spacing.xs }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm }}>
            <AppText variant="label" numberOfLines={1} style={{ flex: 1, fontWeight: item.is_read ? '400' : '700' }}>
              {item.title}
            </AppText>
            {item.is_read ? null : (
              <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: colors.primary }} />
            )}
          </View>
          <AppText variant="muted" numberOfLines={2}>{item.message}</AppText>
          <AppText variant="small">{timeAgo(item.created_at)}</AppText>
        </View>
      </Card>
    </Pressable>
  );
}

export default function NotificationsScreen() {
  const colors = useColors();
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  const notifications = useInfiniteQuery({
    queryKey: LIST_KEY,
    initialPageParam: 1,
    queryFn: async ({ pageParam }) => (await notificationsApi.list({ page: pageParam, page_size: PAGE_SIZE })).data,
    getNextPageParam: (last) => (last.page < last.total_pages ? last.page + 1 : undefined),
  });

  const items = notifications.data?.pages.flatMap((page) => page.items) ?? [];
  const hasUnread = items.some((item) => !item.is_read);

  /** Mark rows as read in the list right away, then refresh the bell's count. */
  function markLocally(ids: string[] | 'all') {
    queryClient.setQueryData<NotificationPages>(LIST_KEY, (data) =>
      data && {
        ...data,
        pages: data.pages.map((page) => ({
          ...page,
          items: page.items.map((item) => (ids === 'all' || ids.includes(item.id) ? { ...item, is_read: true } : item)),
        })),
      },
    );
  }

  const markRead = useMutation({
    mutationFn: (ids: string[]) => notificationsApi.markRead(ids),
    onMutate: (ids) => markLocally(ids),
    onSettled: () => queryClient.invalidateQueries({ queryKey: UNREAD_COUNT_KEY }),
  });

  const markAllRead = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onMutate: () => markLocally('all'),
    onSettled: () => queryClient.invalidateQueries({ queryKey: UNREAD_COUNT_KEY }),
  });

  function open(item: AppNotification) {
    if (!item.is_read) markRead.mutate([item.id]);
    if (item.ticket_number) router.push(`/ticket/${item.ticket_number}`);
  }

  async function refresh() {
    setRefreshing(true);
    try {
      await Promise.all([
        queryClient.resetQueries({ queryKey: LIST_KEY }),
        queryClient.invalidateQueries({ queryKey: UNREAD_COUNT_KEY }),
      ]);
    } finally {
      setRefreshing(false);
    }
  }

  let empty: React.ReactElement | undefined;
  if (notifications.isPending) {
    empty = <Loading label="Loading notifications..." />;
  } else if (!notifications.isError) {
    empty = <EmptyState title="You're all caught up." message="New updates about your tickets will show up here." />;
  }

  return (
    <Screen scroll={false}>
      <Stack.Screen
        options={{
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              disabled={!hasUnread || markAllRead.isPending}
              hitSlop={8}
              onPress={() => markAllRead.mutate()}
              style={({ pressed }) => ({ opacity: !hasUnread ? 0.4 : pressed ? 0.6 : 1 })}>
              <AppText variant="label" style={{ color: colors.primary }}>Mark all read</AppText>
            </Pressable>
          ),
        }}
      />
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <NotificationRow item={item} onPress={() => open(item)} />}
        ListHeaderComponent={
          notifications.isError ? (
            <ErrorBanner message={getApiError(notifications.error, 'Notifications could not be loaded.')} />
          ) : undefined
        }
        ListEmptyComponent={empty}
        ListFooterComponent={notifications.isFetchingNextPage ? <ActivityIndicator style={{ padding: Spacing.lg }} /> : undefined}
        ItemSeparatorComponent={() => <View style={{ height: Spacing.md }} />}
        contentContainerStyle={{ padding: Spacing.lg, paddingBottom: Spacing.xxl * 2, flexGrow: 1 }}
        onEndReachedThreshold={0.4}
        onEndReached={() => {
          if (notifications.hasNextPage && !notifications.isFetchingNextPage) void notifications.fetchNextPage();
        }}
        refreshing={refreshing}
        onRefresh={refresh}
      />
    </Screen>
  );
}
