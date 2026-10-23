import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import React from 'react';
import { Pressable, View } from 'react-native';
import { AppText, Badge, Card } from '@/components/ui';
import { Spacing, useColors } from '@/constants/theme';
import type { Ticket } from '@/lib/api';
import { priorityLabel, statusLabel } from '@/lib/tickets';
import { priorityTone, relativeDate, statusTone } from './format';

export function TicketRow({ ticket }: { ticket: Ticket }) {
  const colors = useColors();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Ticket ${ticket.ticket_number}, ${ticket.title}`}
      onPress={() => router.push(`/ticket/${ticket.ticket_number}`)}
      style={({ pressed }) => ({ opacity: pressed ? 0.8 : 1 })}>
      <Card style={{ gap: Spacing.sm }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: Spacing.sm }}>
          <AppText variant="label" style={{ color: colors.primary }}>{ticket.ticket_number}</AppText>
          <AppText variant="small">{relativeDate(ticket.created_at)}</AppText>
        </View>
        <AppText variant="heading" numberOfLines={2}>{ticket.title}</AppText>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.xs }}>
          <Ionicons name="location-outline" size={14} color={colors.textMuted} />
          <AppText variant="muted" numberOfLines={1} style={{ flex: 1 }}>{ticket.location}</AppText>
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm }}>
          <Badge label={statusLabel(ticket.status)} tone={statusTone(ticket.status)} />
          <Badge label={`${priorityLabel(ticket.priority)} priority`} tone={priorityTone(ticket.priority)} />
        </View>
      </Card>
    </Pressable>
  );
}
