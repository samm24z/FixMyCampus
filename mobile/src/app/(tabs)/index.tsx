import Ionicons from '@expo/vector-icons/Ionicons';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { openBrowserAsync } from 'expo-web-browser';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, View } from 'react-native';
import { TicketRow } from '@/components/tickets/TicketRow';
import { AppText, Button, Card, EmptyState, ErrorBanner, Loading, Screen, SegmentedChoice, TextField } from '@/components/ui';
import { Spacing, useColors } from '@/constants/theme';
import { getApiError, ticketsApi, type TicketListParams } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { WEB_URL } from '@/lib/config';

type Filter = 'all' | 'open' | 'resolved' | 'closed';
const FILTERS: readonly Filter[] = ['all', 'open', 'resolved', 'closed'];
const FILTER_LABELS: Record<Filter, string> = { all: 'All', open: 'Open', resolved: 'Resolved', closed: 'Closed' };
const PAGE_SIZE = 10;

function filterParams(filter: Filter): TicketListParams {
  if (filter === 'open') return { open_only: true };
  if (filter === 'resolved') return { status: 'RESOLVED' };
  if (filter === 'closed') return { status: 'CLOSED' };
  return {};
}

export default function MyTicketsScreen() {
  const colors = useColors();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const summary = useQuery({ queryKey: ['summary'], queryFn: async () => (await ticketsApi.summary()).data });

  const tickets = useInfiniteQuery({
    queryKey: ['tickets', 'mine', filter, debouncedSearch],
    initialPageParam: 1,
    queryFn: async ({ pageParam }) =>
      (
        await ticketsApi.list({
          mine: true,
          ...filterParams(filter),
          search: debouncedSearch,
          page: pageParam,
          page_size: PAGE_SIZE,
        })
      ).data,
    getNextPageParam: (last) => (last.page < last.total_pages ? last.page + 1 : undefined),
  });

  const items = tickets.data?.pages.flatMap((page) => page.items) ?? [];
  const firstName = user?.full_name?.split(' ')[0] ?? '';
  const isStaff = user?.role === 'STAFF' || user?.role === 'COORDINATOR' || user?.role === 'ADMIN';

  async function refresh() {
    setRefreshing(true);
    try {
      await Promise.all([summary.refetch(), queryClient.resetQueries({ queryKey: ['tickets', 'mine', filter, debouncedSearch] })]);
    } finally {
      setRefreshing(false);
    }
  }

  const stats = [
    { label: 'Open', value: summary.data?.open_tickets },
    { label: 'Resolved', value: summary.data?.resolved_tickets },
    { label: 'Total', value: summary.data?.total_tickets },
  ];

  const header = (
    <View style={{ gap: Spacing.lg, paddingBottom: Spacing.md }}>
      <View style={{ gap: Spacing.xs }}>
        <AppText variant="title">{firstName ? `Hi, ${firstName}` : 'My tickets'}</AppText>
        <AppText variant="muted">Track the problems you have reported.</AppText>
      </View>

      <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
        {stats.map((stat) => (
          <Card key={stat.label} style={{ flex: 1, alignItems: 'center', gap: Spacing.xs, paddingVertical: Spacing.md }}>
            <AppText variant="title">{stat.value ?? '-'}</AppText>
            <AppText variant="small">{stat.label}</AppText>
          </Card>
        ))}
      </View>

      {isStaff ? (
        <Pressable onPress={() => openBrowserAsync(WEB_URL)}>
          <Card style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm }}>
            <Ionicons name="desktop-outline" size={20} color={colors.primary} />
            <AppText variant="muted" style={{ flex: 1 }}>
              Staff tools (assigning, triage, status updates) are on the web app. Tap to open it.
            </AppText>
          </Card>
        </Pressable>
      ) : null}

      <TextField
        value={search}
        onChangeText={setSearch}
        placeholder="Search by title, place or ticket number"
        returnKeyType="search"
        autoCapitalize="none"
        autoCorrect={false}
        clearButtonMode="while-editing"
      />
      <SegmentedChoice options={FILTERS} value={filter} onChange={setFilter} labelFor={(option) => FILTER_LABELS[option]} />
      <ErrorBanner message={tickets.isError ? getApiError(tickets.error, 'Tickets could not be loaded.') : null} />
    </View>
  );

  let empty: React.ReactElement | undefined;
  if (tickets.isPending) {
    empty = <Loading label="Loading tickets..." />;
  } else if (!tickets.isError) {
    const filtered = filter !== 'all' || debouncedSearch !== '';
    empty = (
      <EmptyState
        title={filtered ? 'No matching tickets' : 'No tickets yet'}
        message={filtered ? 'Try a different filter or search.' : 'Spotted something broken on campus? Report it and follow its progress here.'}
        action={filtered ? undefined : <Button title="Report a problem" onPress={() => router.push('/report')} />}
      />
    );
  }

  return (
    <Screen scroll={false}>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <TicketRow ticket={item} />}
        ListHeaderComponent={header}
        ListEmptyComponent={empty}
        ListFooterComponent={tickets.isFetchingNextPage ? <ActivityIndicator style={{ padding: Spacing.lg }} /> : undefined}
        ItemSeparatorComponent={() => <View style={{ height: Spacing.md }} />}
        contentContainerStyle={{ padding: Spacing.lg, paddingBottom: Spacing.xxl * 2 }}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        onEndReachedThreshold={0.4}
        onEndReached={() => {
          if (tickets.hasNextPage && !tickets.isFetchingNextPage) void tickets.fetchNextPage();
        }}
        refreshing={refreshing}
        onRefresh={refresh}
      />
    </Screen>
  );
}
