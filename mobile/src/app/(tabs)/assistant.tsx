import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, TextInput, View } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { useNavigation } from 'expo-router';
import { AppText, Screen } from '@/components/ui';
import { MessageBubble } from '@/components/assistant/MessageBubble';
import { FontSize, Radius, Spacing, useColors } from '@/constants/theme';
import { assistantApi, getApiError } from '@/lib/api';
import { STARTER_QUESTIONS, historyForRequest, type ChatMessage } from '@/lib/assistant';

export default function AssistantScreen() {
  const colors = useColors();
  const navigation = useNavigation();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);
  const generation = useRef(0); // bumped by "New chat" so a late reply to the old chat is dropped
  const list = useRef<FlatList<ChatMessage>>(null);

  const ask = useCallback(
    async (question: string, base: ChatMessage[], retryOf?: number) => {
      const text = question.trim();
      if (!text) return;
      const history = historyForRequest(base);
      const current = generation.current;
      // On retry, the original question stays and only the failed reply is replaced.
      setMessages((prev) =>
        retryOf === undefined
          ? [...prev, { id: nextId.current++, role: 'user', text }]
          : prev.filter((message) => message.id !== retryOf),
      );
      setBusy(true);
      try {
        const { data } = await assistantApi.chat(text, history);
        if (generation.current !== current) return;
        setMessages((prev) => [
          ...prev,
          {
            id: nextId.current++,
            role: 'assistant',
            text: data.answer,
            reply: { sources: data.sources, actions: data.actions, status: data.status },
          },
        ]);
      } catch (requestError) {
        if (generation.current !== current) return;
        setMessages((prev) => [
          ...prev,
          {
            id: nextId.current++,
            role: 'assistant',
            text: getApiError(requestError, "Sorry, I couldn't get an answer. Please try again."),
            failed: true,
          },
        ]);
      } finally {
        if (generation.current === current) setBusy(false);
      }
    },
    [],
  );

  function send(question: string) {
    if (busy || !question.trim()) return;
    setInput('');
    void ask(question, messages);
  }

  function retry(failed: ChatMessage) {
    if (busy) return;
    const index = messages.findIndex((message) => message.id === failed.id);
    const question = messages[index - 1];
    if (!question || question.role !== 'user') return;
    void ask(question.text, messages.slice(0, index - 1), failed.id);
  }

  const newChat = useCallback(() => {
    generation.current += 1;
    setMessages([]);
    setInput('');
    setBusy(false);
  }, []);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="New chat"
          onPress={newChat}
          hitSlop={8}
          style={styles.headerButton}>
          <Ionicons name="create-outline" size={22} color={colors.primary} />
        </Pressable>
      ),
    });
  }, [navigation, newChat, colors.primary]);

  const canSend = !busy && input.trim().length > 0;

  return (
    <Screen scroll={false}>
      <FlatList
        ref={list}
        data={messages}
        keyExtractor={(message) => String(message.id)}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="interactive"
        contentContainerStyle={styles.listContent}
        onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
        renderItem={({ item }) => (
          <MessageBubble message={item} onRetry={item.failed ? () => retry(item) : undefined} />
        )}
        ListHeaderComponent={
          messages.length === 0 ? (
            <View style={styles.empty}>
              <View style={[styles.greeting, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <AppText>Hi! What would you like to know? Here are some things you can ask.</AppText>
              </View>
              <View style={styles.chips}>
                {STARTER_QUESTIONS.map((question) => (
                  <Pressable
                    key={question}
                    accessibilityRole="button"
                    onPress={() => send(question)}
                    style={[styles.chip, { borderColor: colors.border, backgroundColor: colors.card }]}>
                    <AppText variant="muted" style={{ color: colors.text }}>{question}</AppText>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : undefined
        }
        ListFooterComponent={
          busy ? (
            <View style={styles.typing}>
              <ActivityIndicator size="small" color={colors.textMuted} />
              <AppText variant="muted">Looking that up...</AppText>
            </View>
          ) : undefined
        }
      />
      <View style={[styles.inputBar, { backgroundColor: colors.card, borderTopColor: colors.border }]}>
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Type your question"
          placeholderTextColor={colors.textMuted}
          accessibilityLabel="Your question"
          maxLength={1000}
          multiline
          returnKeyType="send"
          blurOnSubmit
          onSubmitEditing={() => send(input)}
          style={[styles.input, { color: colors.text, backgroundColor: colors.background, borderColor: colors.border }]}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Send"
          accessibilityState={{ disabled: !canSend }}
          disabled={!canSend}
          onPress={() => send(input)}
          style={[styles.sendButton, { backgroundColor: colors.primary, opacity: canSend ? 1 : 0.4 }]}>
          <Ionicons name="send" size={18} color={colors.primaryText} />
        </Pressable>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  listContent: { padding: Spacing.lg, gap: Spacing.lg, flexGrow: 1 },
  empty: { gap: Spacing.lg },
  greeting: { alignSelf: 'flex-start', maxWidth: '92%', borderWidth: 1, borderRadius: Radius.lg, borderBottomLeftRadius: Radius.sm, padding: Spacing.lg },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  chip: { borderWidth: 1, borderRadius: Radius.pill, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm },
  typing: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  inputBar: { flexDirection: 'row', alignItems: 'flex-end', gap: Spacing.sm, padding: Spacing.md, borderTopWidth: 1 },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    borderWidth: 1,
    borderRadius: Radius.lg,
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.sm + 2,
    paddingBottom: Spacing.sm + 2,
    fontSize: FontSize.md,
  },
  sendButton: { width: 44, height: 44, borderRadius: Radius.pill, alignItems: 'center', justifyContent: 'center' },
  headerButton: { paddingHorizontal: Spacing.md },
});
