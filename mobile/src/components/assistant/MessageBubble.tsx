import { Pressable, StyleSheet, View } from 'react-native';
import { openBrowserAsync } from 'expo-web-browser';
import { AppText, Button } from '@/components/ui';
import { FontSize, Radius, Spacing, useColors } from '@/constants/theme';
import { isAppLink, isWebLink, type ChatMessage } from '@/lib/assistant';
import { WEB_URL } from '@/lib/config';
import { ActionCard } from './ActionCard';

export function MessageBubble({ message, onRetry }: { message: ChatMessage; onRetry?: () => void }) {
  const colors = useColors();

  if (message.role === 'user') {
    return (
      <View style={[styles.bubble, styles.user, { backgroundColor: colors.primary }]}>
        <AppText style={{ color: colors.primaryText }}>{message.text}</AppText>
      </View>
    );
  }

  const reply = message.reply;
  const sources = (reply?.sources ?? []).filter((source) => isWebLink(source.url) || isAppLink(source.url));
  return (
    <View style={styles.assistantWrap}>
      <View
        style={[
          styles.bubble,
          styles.assistant,
          message.failed
            ? { backgroundColor: colors.dangerBg, borderColor: colors.danger }
            : { backgroundColor: colors.card, borderColor: colors.border },
        ]}>
        <AppText style={message.failed ? { color: colors.danger } : undefined}>{message.text}</AppText>
      </View>
      {message.failed && onRetry ? <Button title="Try again" variant="outline" onPress={onRetry} style={styles.retry} /> : null}
      {sources.length > 0 ? (
        <View style={styles.sources}>
          {sources.map((source) => {
            const url = isAppLink(source.url) ? `${WEB_URL}${source.url}` : source.url;
            return (
              <Pressable
                key={source.n}
                accessibilityRole="link"
                accessibilityLabel={`Source ${source.n}: ${source.title}`}
                onPress={() => void openBrowserAsync(url)}
                style={[styles.source, { borderColor: colors.border, backgroundColor: colors.card }]}>
                <AppText numberOfLines={1} style={{ color: colors.primary, fontSize: FontSize.xs }}>
                  <AppText style={{ color: colors.primary, fontSize: FontSize.xs, fontWeight: '700' }}>{source.n}</AppText> {source.title}
                </AppText>
              </Pressable>
            );
          })}
        </View>
      ) : null}
      {reply?.actions.map((action, index) => <ActionCard key={index} action={action} />)}
    </View>
  );
}

const styles = StyleSheet.create({
  bubble: { borderRadius: Radius.lg, paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md },
  user: { alignSelf: 'flex-end', maxWidth: '85%', borderBottomRightRadius: Radius.sm },
  assistantWrap: { alignSelf: 'flex-start', maxWidth: '92%', gap: Spacing.sm },
  assistant: { borderWidth: 1, borderBottomLeftRadius: Radius.sm },
  retry: { alignSelf: 'flex-start', minHeight: 40 },
  sources: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.xs },
  source: { maxWidth: 260, borderWidth: 1, borderRadius: Radius.pill, paddingHorizontal: Spacing.sm, paddingVertical: Spacing.xs },
});
