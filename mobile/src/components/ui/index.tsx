/**
 * Small shared building blocks so every screen looks the same. Screens should compose these
 * instead of styling raw View/Text/Pressable from scratch.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Keyboard,
  LayoutAnimation,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type PressableProps,
  type StyleProp,
  type TextInputProps,
  type TextProps,
  type TextStyle,
  type ViewStyle,
} from 'react-native';
import { FontSize, Radius, Spacing, useColors } from '@/constants/theme';

// ----------------------------------------------------------------- text

type TextVariant = 'title' | 'heading' | 'body' | 'muted' | 'small' | 'label';

const TEXT_STYLES: Record<TextVariant, TextStyle> = {
  title: { fontSize: FontSize.xxl, fontWeight: '700' },
  heading: { fontSize: FontSize.lg, fontWeight: '600' },
  body: { fontSize: FontSize.md },
  muted: { fontSize: FontSize.sm },
  small: { fontSize: FontSize.xs },
  label: { fontSize: FontSize.sm, fontWeight: '600' },
};

export function AppText({ variant = 'body', style, ...rest }: TextProps & { variant?: TextVariant }) {
  const colors = useColors();
  const color = variant === 'muted' || variant === 'small' ? colors.textMuted : colors.text;
  return <Text {...rest} style={[{ color }, TEXT_STYLES[variant], style]} />;
}

// --------------------------------------------------------------- screen

/**
 * How far the iOS keyboard overlaps the view in `ref`, measured in window coordinates so it is
 * right under a header and above a tab bar. Android resizes the window itself, so it stays 0 there.
 */
function useKeyboardOverlap(ref: React.RefObject<React.ComponentRef<typeof View> | null>, enabled: boolean) {
  const [overlap, setOverlap] = useState(0);
  useEffect(() => {
    if (!enabled || Platform.OS !== 'ios') return;
    const animate = (duration: number) =>
      LayoutAnimation.configureNext(LayoutAnimation.create(duration || 250, LayoutAnimation.Types.keyboard, 'opacity'));
    const show = Keyboard.addListener('keyboardWillShow', (event) => {
      ref.current?.measureInWindow((_x, y, _width, height) => {
        animate(event.duration);
        setOverlap(Math.max(0, y + height - event.endCoordinates.screenY));
      });
    });
    const hide = Keyboard.addListener('keyboardWillHide', (event) => {
      animate(event.duration);
      setOverlap(0);
    });
    return () => {
      show.remove();
      hide.remove();
    };
  }, [ref, enabled]);
  return overlap;
}

/**
 * Page body with consistent padding, keyboard handling and optional pull-to-refresh.
 * Headers and safe areas are handled by the navigator, so screens don't add their own.
 */
export function Screen({
  children,
  onRefresh,
  refreshing = false,
  scroll = true,
  contentStyle,
}: {
  children: React.ReactNode;
  onRefresh?: () => void;
  refreshing?: boolean;
  /** Set false for screens that manage their own list (FlatList) or layout, like a chat with an input bar. */
  scroll?: boolean;
  contentStyle?: StyleProp<ViewStyle>;
}) {
  const colors = useColors();
  const frame = useRef<React.ComponentRef<typeof View>>(null);
  const keyboardOverlap = useKeyboardOverlap(frame, !scroll);
  if (scroll) {
    return (
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentInsetAdjustmentBehavior="automatic"
        // iOS insets the content and scrolls the focused field into view; Android resizes the window.
        automaticallyAdjustKeyboardInsets
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={[styles.screenContent, contentStyle]}
        refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} /> : undefined}>
        {children}
      </ScrollView>
    );
  }
  return (
    <View ref={frame} style={{ flex: 1, backgroundColor: colors.background, paddingBottom: keyboardOverlap }}>
      <View style={[{ flex: 1 }, contentStyle]}>{children}</View>
    </View>
  );
}

// --------------------------------------------------------------- button

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'destructive' | 'ghost';

export function Button({
  title,
  onPress,
  variant = 'primary',
  loading = false,
  disabled = false,
  icon,
  style,
  ...rest
}: Omit<PressableProps, 'style' | 'children'> & {
  title: string;
  variant?: ButtonVariant;
  loading?: boolean;
  icon?: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  const colors = useColors();
  const palette: Record<ButtonVariant, { bg: string; fg: string; border: string }> = {
    primary: { bg: colors.primary, fg: colors.primaryText, border: colors.primary },
    secondary: { bg: colors.secondary, fg: colors.secondaryText, border: colors.secondary },
    outline: { bg: 'transparent', fg: colors.text, border: colors.border },
    destructive: { bg: colors.destructive, fg: colors.destructiveText, border: colors.destructive },
    ghost: { bg: 'transparent', fg: colors.primary, border: 'transparent' },
  };
  const { bg, fg, border } = palette[variant];
  const inactive = disabled || loading;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: inactive, busy: loading }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: bg, borderColor: border, opacity: inactive ? 0.5 : pressed ? 0.8 : 1 },
        style,
      ]}
      {...rest}>
      {loading ? <ActivityIndicator color={fg} /> : icon}
      <Text style={[styles.buttonText, { color: fg }]}>{title}</Text>
    </Pressable>
  );
}

// ----------------------------------------------------------------- card

export function Card({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  const colors = useColors();
  return <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }, style]}>{children}</View>;
}

// ---------------------------------------------------------------- badge

export type BadgeTone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger';

export function Badge({ label, tone = 'neutral' }: { label: string; tone?: BadgeTone }) {
  const colors = useColors();
  const tones: Record<BadgeTone, { bg: string; fg: string }> = {
    neutral: { bg: colors.secondary, fg: colors.secondaryText },
    primary: { bg: colors.primary, fg: colors.primaryText },
    success: { bg: colors.successBg, fg: colors.success },
    warning: { bg: colors.warningBg, fg: colors.warning },
    danger: { bg: colors.dangerBg, fg: colors.danger },
  };
  const { bg, fg } = tones[tone];
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={[styles.badgeText, { color: fg }]}>{label}</Text>
    </View>
  );
}

// ---------------------------------------------------------------- input

export function TextField({
  label,
  error,
  hint,
  style,
  ...rest
}: TextInputProps & { label?: string; error?: string; hint?: string; ref?: React.Ref<React.ComponentRef<typeof TextInput>> }) {
  const colors = useColors();
  return (
    <View style={styles.field}>
      {label ? <AppText variant="label">{label}</AppText> : null}
      <TextInput
        placeholderTextColor={colors.textMuted}
        style={[
          styles.input,
          { color: colors.text, backgroundColor: colors.card, borderColor: error ? colors.destructive : colors.border },
          rest.multiline ? styles.multiline : null,
          style,
        ]}
        {...rest}
      />
      {error ? <AppText variant="small" style={{ color: colors.destructive }}>{error}</AppText> : null}
      {!error && hint ? <AppText variant="small">{hint}</AppText> : null}
    </View>
  );
}

/** A row of choices where exactly one is selected (role, priority, filters...). */
export function SegmentedChoice<T extends string>({
  options,
  value,
  onChange,
  labelFor = (option) => option,
}: {
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
  labelFor?: (option: T) => string;
}) {
  const colors = useColors();
  return (
    <View style={styles.chips}>
      {options.map((option) => {
        const selected = option === value;
        return (
          <Pressable
            key={option}
            accessibilityRole="button"
            accessibilityState={{ selected }}
            onPress={() => onChange(option)}
            style={[
              styles.chip,
              { borderColor: selected ? colors.primary : colors.border, backgroundColor: selected ? colors.primary : colors.card },
            ]}>
            <Text style={{ color: selected ? colors.primaryText : colors.text, fontSize: FontSize.sm, fontWeight: '500' }}>
              {labelFor(option)}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// ------------------------------------------------------- status blocks

export function ErrorBanner({ message }: { message?: string | null }) {
  const colors = useColors();
  if (!message) return null;
  return (
    <View accessibilityRole="alert" style={[styles.banner, { backgroundColor: colors.dangerBg }]}>
      <Text style={{ color: colors.danger, fontSize: FontSize.sm }}>{message}</Text>
    </View>
  );
}

export function NoticeBanner({ message }: { message?: string | null }) {
  const colors = useColors();
  if (!message) return null;
  return (
    <View style={[styles.banner, { backgroundColor: colors.successBg }]}>
      <Text style={{ color: colors.success, fontSize: FontSize.sm }}>{message}</Text>
    </View>
  );
}

export function Loading({ label = 'Loading...' }: { label?: string }) {
  return (
    <View style={styles.centered}>
      <ActivityIndicator />
      <AppText variant="muted">{label}</AppText>
    </View>
  );
}

export function EmptyState({ title, message, action }: { title: string; message?: string; action?: React.ReactNode }) {
  return (
    <View style={styles.centered}>
      <AppText variant="heading">{title}</AppText>
      {message ? <AppText variant="muted" style={{ textAlign: 'center' }}>{message}</AppText> : null}
      {action}
    </View>
  );
}

export const styles = StyleSheet.create({
  screenContent: { padding: Spacing.lg, gap: Spacing.lg, paddingBottom: Spacing.xxl * 2 },
  button: {
    minHeight: 48,
    borderRadius: Radius.md,
    borderWidth: 1,
    paddingHorizontal: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
  },
  buttonText: { fontSize: FontSize.md, fontWeight: '600' },
  card: { borderWidth: 1, borderRadius: Radius.lg, padding: Spacing.lg, gap: Spacing.md },
  badge: { alignSelf: 'flex-start', borderRadius: Radius.pill, paddingHorizontal: Spacing.sm, paddingVertical: 2 },
  badgeText: { fontSize: FontSize.xs, fontWeight: '600' },
  field: { gap: Spacing.xs },
  input: { minHeight: 48, borderWidth: 1, borderRadius: Radius.md, paddingHorizontal: Spacing.md, fontSize: FontSize.md },
  multiline: { minHeight: 110, paddingTop: Spacing.md, textAlignVertical: 'top' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  chip: { borderWidth: 1, borderRadius: Radius.pill, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm },
  banner: { borderRadius: Radius.md, padding: Spacing.md },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: Spacing.sm, padding: Spacing.xl },
});
