import { useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { useQueryClient } from '@tanstack/react-query';
import { openBrowserAsync } from 'expo-web-browser';
import { useRouter } from 'expo-router';
import { AppText, Button, Card, ErrorBanner, NoticeBanner } from '@/components/ui';
import { Spacing, useColors } from '@/constants/theme';
import { WEB_URL } from '@/lib/config';
import { getApiError, type AssistantAction } from '@/lib/api';
import {
  isAppLink,
  isWebLink,
  mailHref,
  runTicketAction,
  telHref,
  ticketActionButton,
  ticketActionDone,
  ticketActionTitle,
  type TicketAction,
} from '@/lib/assistant';

type ReportAction = Extract<AssistantAction, { type: 'report_problem' }>;

function ReportCard({ action }: { action: ReportAction }) {
  const router = useRouter();
  const colors = useColors();
  return (
    <Card>
      <View style={styles.titleRow}>
        <Ionicons name="add-circle-outline" size={18} color={colors.primary} />
        <AppText variant="label">Report a problem</AppText>
      </View>
      <AppText variant="muted">{action.title}</AppText>
      <AppText variant="small">Check the details on the next screen. Nothing is sent until you tap Send.</AppText>
      <Button
        title="Fill in a report"
        onPress={() =>
          router.push({
            pathname: '/report',
            params: {
              title: action.title,
              description: action.description,
              category: action.category,
              location: action.location,
              priority: action.priority,
              prefill: String(Date.now()),
            },
          })
        }
      />
    </Card>
  );
}

function TicketActionCard({ action }: { action: TicketAction }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [state, setState] = useState<'idle' | 'working' | 'done'>('idle');
  const [error, setError] = useState('');

  async function run() {
    setError('');
    setState('working');
    try {
      await runTicketAction(action);
      setState('done');
      void queryClient.invalidateQueries({ queryKey: ['tickets'] });
      void queryClient.invalidateQueries({ queryKey: ['summary'] });
      void queryClient.invalidateQueries({ queryKey: ['ticket', action.ticket_number] });
    } catch (requestError) {
      setError(getApiError(requestError));
      setState('idle');
    }
  }

  return (
    <Card>
      <AppText variant="label">{ticketActionTitle(action.type)}</AppText>
      <AppText variant="muted">
        {action.ticket_number} · {action.ticket_title}
      </AppText>
      {action.type === 'add_comment' ? <AppText>{action.text}</AppText> : null}
      <ErrorBanner message={error} />
      {state === 'done' ? (
        <NoticeBanner message={ticketActionDone(action.type)} />
      ) : (
        <Button
          title={state === 'working' ? 'Working...' : ticketActionButton(action.type)}
          variant={action.type === 'cancel_ticket' ? 'outline' : 'primary'}
          loading={state === 'working'}
          onPress={run}
        />
      )}
      <Button title="View ticket" variant="ghost" onPress={() => router.push(`/ticket/${action.ticket_number}`)} />
    </Card>
  );
}

function ContactCard({ action }: { action: Extract<AssistantAction, { type: 'contact' }> }) {
  const colors = useColors();
  return (
    <Card>
      <AppText variant="label">{action.label}</AppText>
      {action.phone ? (
        <Button
          title={`Call ${action.phone}`}
          variant="outline"
          icon={<Ionicons name="call-outline" size={18} color={colors.text} />}
          onPress={() => void Linking.openURL(telHref(action.phone as string))}
        />
      ) : null}
      {action.email ? (
        <Button
          title={`Email ${action.email}`}
          variant="outline"
          icon={<Ionicons name="mail-outline" size={18} color={colors.text} />}
          onPress={() => void Linking.openURL(mailHref(action.email as string))}
        />
      ) : null}
    </Card>
  );
}

function LinkCard({ action }: { action: Extract<AssistantAction, { type: 'open_link' }> }) {
  const colors = useColors();
  const target = isAppLink(action.url) ? `${WEB_URL}${action.url}` : isWebLink(action.url) ? action.url : null;
  if (!target) return null;
  return (
    <Card>
      <Button
        title={action.label}
        variant="outline"
        icon={<Ionicons name="open-outline" size={18} color={colors.text} />}
        onPress={() => void openBrowserAsync(target)}
      />
    </Card>
  );
}

export function ActionCard({ action }: { action: AssistantAction }) {
  switch (action.type) {
    case 'report_problem':
      return <ReportCard action={action} />;
    case 'contact':
      return <ContactCard action={action} />;
    case 'open_link':
      return <LinkCard action={action} />;
    default:
      return <TicketActionCard action={action} />;
  }
}

const styles = StyleSheet.create({
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
});
