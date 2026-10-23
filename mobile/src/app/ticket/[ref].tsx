import Ionicons from '@expo/vector-icons/Ionicons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Stack, router, useLocalSearchParams } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { Alert, Pressable, View } from 'react-native';
import { formatDateTime, priorityTone, statusTone } from '@/components/tickets/format';
import { TicketGallery } from '@/components/tickets/TicketGallery';
import { AppText, Badge, Button, Card, ErrorBanner, Loading, Screen, TextField } from '@/components/ui';
import { Spacing, useColors } from '@/constants/theme';
import { getApiError, ticketsApi, type TicketDetail } from '@/lib/api';
import { priorityLabel, reportsLabel, roleLabel, statusLabel } from '@/lib/tickets';

function Fact({ icon, label, value }: { icon: React.ComponentProps<typeof Ionicons>['name']; label: string; value: string }) {
  const colors = useColors();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm }}>
      <Ionicons name={icon} size={16} color={colors.primary} style={{ marginTop: 2 }} />
      <View style={{ flex: 1 }}>
        <AppText variant="small">{label}</AppText>
        <AppText variant="body">{value}</AppText>
      </View>
    </View>
  );
}

export default function TicketScreen() {
  const colors = useColors();
  const queryClient = useQueryClient();
  const { ref } = useLocalSearchParams<{ ref: string }>();
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [comment, setComment] = useState('');
  const [reopenReason, setReopenReason] = useState('');
  const [withdrawReason, setWithdrawReason] = useState('');
  const [rating, setRating] = useState(0);
  const [feedbackComments, setFeedbackComments] = useState('');

  const query = useQuery({
    queryKey: ['ticket', ref],
    queryFn: async () => (await ticketsApi.detail(ref)).data,
    enabled: Boolean(ref),
  });
  const ticket = query.data;

  // Keep the rating form in step with the saved feedback.
  const savedRating = ticket?.feedback?.rating;
  const savedComments = ticket?.feedback?.comments;
  useEffect(() => {
    setRating(savedRating ?? 0);
    setFeedbackComments(savedComments ?? '');
  }, [savedRating, savedComments]);

  const mutation = useMutation({
    mutationFn: (action: () => Promise<{ data: TicketDetail }>) => action(),
    onMutate: () => setError(''),
    onSuccess: (response) => {
      queryClient.setQueryData(['ticket', ref], response.data);
      void queryClient.invalidateQueries({ queryKey: ['tickets'] });
      void queryClient.invalidateQueries({ queryKey: ['summary'] });
    },
    onError: (requestError) => setError(getApiError(requestError)),
  });
  const saving = mutation.isPending;

  function perform(action: () => Promise<{ data: TicketDetail }>, onDone?: () => void) {
    mutation.mutate(action, { onSuccess: onDone });
  }

  async function refresh() {
    setRefreshing(true);
    try {
      await Promise.all([query.refetch(), queryClient.invalidateQueries({ queryKey: ['ticket', ref, 'attachments'] })]);
    } finally {
      setRefreshing(false);
    }
  }

  function confirmWithdraw() {
    Alert.alert('Cancel this ticket?', 'The team will stop working on it. This cannot be undone.', [
      { text: 'Keep ticket', style: 'cancel' },
      {
        text: 'Cancel ticket',
        style: 'destructive',
        onPress: () => perform(() => ticketsApi.withdraw(ref, withdrawReason), () => setWithdrawReason('')),
      },
    ]);
  }

  const options = <Stack.Screen options={{ title: ticket?.ticket_number ?? ref ?? 'Ticket' }} />;

  if (query.isPending) {
    return (
      <Screen>
        {options}
        <Loading label="Loading ticket..." />
      </Screen>
    );
  }
  if (!ticket) {
    return (
      <Screen onRefresh={refresh} refreshing={refreshing}>
        {options}
        <ErrorBanner message={getApiError(query.error, 'Ticket could not be loaded.')} />
        <Button title="Back to tickets" variant="outline" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
      </Screen>
    );
  }

  const { permissions } = ticket;
  const groupedNote = ticket.report_count > 1 || ticket.parent_ticket_id;

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      {options}
      <ErrorBanner message={error} />

      <Card>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm }}>
          <Badge label={statusLabel(ticket.status)} tone={statusTone(ticket.status)} />
          <Badge label={`${priorityLabel(ticket.priority)} priority`} tone={priorityTone(ticket.priority)} />
          {ticket.report_count > 1 ? <Badge label={reportsLabel(ticket.report_count)} tone="warning" /> : null}
        </View>
        <AppText variant="title" style={{ fontSize: 22 }}>{ticket.title}</AppText>
        {groupedNote ? (
          <AppText variant="muted">Other people reported the same problem. We're fixing them together.</AppText>
        ) : null}
        <View style={{ gap: Spacing.md, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: Spacing.md }}>
          <Fact icon="pricetag-outline" label="Category" value={ticket.category} />
          <Fact icon="location-outline" label="Location" value={ticket.location} />
          <Fact icon="business-outline" label="Department" value={ticket.department_name || 'Not assigned'} />
          <Fact icon="person-outline" label="Assigned to" value={ticket.assigned_to_name || 'Not assigned yet'} />
          <Fact icon="time-outline" label="Reported" value={formatDateTime(ticket.created_at)} />
          {ticket.observed_at ? <Fact icon="eye-outline" label="Noticed" value={formatDateTime(ticket.observed_at)} /> : null}
          {ticket.sla_deadline ? <Fact icon="calendar-outline" label="Fix by" value={formatDateTime(ticket.sla_deadline)} /> : null}
        </View>
      </Card>

      <Card>
        <AppText variant="heading">What's wrong</AppText>
        <AppText>{ticket.description}</AppText>
      </Card>

      <TicketGallery ticketRef={ticket.ticket_number} reportedAt={ticket.created_at} />

      {permissions.can_confirm ? (
        <Card style={{ borderColor: colors.success }}>
          <AppText variant="heading">Is the issue fixed?</AppText>
          <AppText variant="muted">
            If it's fixed, confirm to close the ticket. If you don't reply, it will close by itself after a few days.
          </AppText>
          <Button
            title="Yes, it's fixed"
            loading={saving}
            icon={<Ionicons name="checkmark-circle" size={20} color={colors.primaryText} />}
            onPress={() => perform(() => ticketsApi.confirm(ticket.ticket_number))}
          />
        </Card>
      ) : null}

      {permissions.can_reopen ? (
        <Card>
          <AppText variant="heading">Not fixed?</AppText>
          <TextField
            value={reopenReason}
            onChangeText={setReopenReason}
            placeholder="Why is it not fixed? (optional)"
            maxLength={500}
          />
          <Button
            title="Reopen ticket"
            variant="outline"
            disabled={saving}
            icon={<Ionicons name="refresh" size={18} color={colors.text} />}
            onPress={() => perform(() => ticketsApi.reopen(ticket.ticket_number, reopenReason), () => setReopenReason(''))}
          />
        </Card>
      ) : null}

      {permissions.can_give_feedback || ticket.feedback ? (
        <Card>
          <AppText variant="heading">Rate the fix</AppText>
          {permissions.can_give_feedback ? <AppText variant="muted">How happy are you with how this was fixed?</AppText> : null}
          <View style={{ flexDirection: 'row', gap: Spacing.xs }} accessibilityRole="radiogroup">
            {[1, 2, 3, 4, 5].map((value) => (
              <Pressable
                key={value}
                accessibilityRole="radio"
                accessibilityLabel={`${value} star${value > 1 ? 's' : ''}`}
                accessibilityState={{ selected: rating === value }}
                disabled={!permissions.can_give_feedback || saving}
                onPress={() => setRating(value)}
                hitSlop={4}>
                <Ionicons name={value <= rating ? 'star' : 'star-outline'} size={32} color={value <= rating ? '#F59E0B' : colors.textMuted} />
              </Pressable>
            ))}
          </View>
          {permissions.can_give_feedback ? (
            <>
              <TextField
                value={feedbackComments}
                onChangeText={setFeedbackComments}
                placeholder="Comments (optional)"
                multiline
                maxLength={2000}
              />
              <Button
                title={ticket.feedback ? 'Update rating' : 'Send rating'}
                loading={saving}
                disabled={rating === 0 || (rating === ticket.feedback?.rating && feedbackComments === (ticket.feedback?.comments ?? ''))}
                onPress={() => perform(() => ticketsApi.submitFeedback(ticket.ticket_number, rating, feedbackComments))}
              />
            </>
          ) : ticket.feedback?.comments ? (
            <AppText variant="muted">{ticket.feedback.comments}</AppText>
          ) : null}
        </Card>
      ) : null}

      <Card>
        <AppText variant="heading">History</AppText>
        {ticket.history.length === 0 ? <AppText variant="muted">No updates yet.</AppText> : null}
        {ticket.history.map((item) => (
          <View key={item.id} style={{ borderLeftWidth: 2, borderLeftColor: colors.primary, paddingLeft: Spacing.md, gap: 2 }}>
            <AppText variant="label">
              {item.from_status ? `${statusLabel(item.from_status)} → ` : ''}
              {statusLabel(item.to_status)}
            </AppText>
            {item.remarks ? <AppText variant="muted" style={{ color: colors.text }}>{item.remarks}</AppText> : null}
            <AppText variant="small">
              {item.changed_by === null ? 'System' : 'Updated'} · {formatDateTime(item.created_at)}
            </AppText>
          </View>
        ))}
      </Card>

      <Card>
        <AppText variant="heading">Comments</AppText>
        {ticket.comments.length === 0 ? <AppText variant="muted">No comments yet.</AppText> : null}
        {ticket.comments.map((item) => (
          <View key={item.id} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: Spacing.md, gap: Spacing.xs }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, flexWrap: 'wrap' }}>
              <AppText variant="label">{item.author_name || 'Unknown'}</AppText>
              {item.author_role ? <AppText variant="small">{roleLabel(item.author_role)}</AppText> : null}
              {item.is_internal ? <Badge label="Staff only" tone="warning" /> : null}
            </View>
            <AppText>{item.content}</AppText>
            <AppText variant="small">{formatDateTime(item.created_at)}</AppText>
          </View>
        ))}
        {permissions.can_comment ? (
          <View style={{ gap: Spacing.sm }}>
            <TextField value={comment} onChangeText={setComment} placeholder="Add a comment" multiline maxLength={2000} />
            <Button
              title="Send comment"
              loading={saving}
              disabled={!comment.trim()}
              icon={<Ionicons name="send" size={16} color={colors.primaryText} />}
              onPress={() => perform(() => ticketsApi.comment(ticket.ticket_number, comment.trim()), () => setComment(''))}
            />
          </View>
        ) : ticket.status === 'CLOSED' ? (
          <AppText variant="muted">This ticket is closed. Reopen it to add a comment.</AppText>
        ) : null}
      </Card>

      {permissions.can_withdraw ? (
        <Card>
          <AppText variant="heading">Cancel this ticket</AppText>
          <TextField
            value={withdrawReason}
            onChangeText={setWithdrawReason}
            placeholder="Why are you cancelling? (optional)"
            maxLength={500}
          />
          <Button
            title="Cancel ticket"
            variant="outline"
            disabled={saving}
            icon={<Ionicons name="arrow-undo" size={18} color={colors.text} />}
            onPress={confirmWithdraw}
          />
        </Card>
      ) : null}
    </Screen>
  );
}
