import { useColorScheme } from 'react-native';

/** Same palette as the web app (frontend/src/index.css), in light and dark. */
export const Colors = {
  light: {
    background: '#F8F9FC',
    card: '#FFFFFF',
    text: '#0F172A',
    textMuted: '#64748B',
    border: '#E2E8F0',
    primary: '#4F46E5',
    primaryText: '#F8FAFC',
    secondary: '#E8ECF2',
    secondaryText: '#0F172A',
    destructive: '#EF4444',
    destructiveText: '#FFFFFF',
    success: '#16A34A',
    successBg: '#DCFCE7',
    warning: '#B45309',
    warningBg: '#FEF3C7',
    danger: '#B91C1C',
    dangerBg: '#FEE2E2',
  },
  dark: {
    background: '#030712',
    card: '#0B1120',
    text: '#E2E8F0',
    textMuted: '#94A3B8',
    border: '#1E293B',
    primary: '#6366F1',
    primaryText: '#030712',
    secondary: '#1A2236',
    secondaryText: '#F8FAFC',
    destructive: '#DC2626',
    destructiveText: '#FFFFFF',
    success: '#4ADE80',
    successBg: '#052E16',
    warning: '#FBBF24',
    warningBg: '#422006',
    danger: '#F87171',
    dangerBg: '#450A0A',
  },
} as const;

export type ThemeColors = { [K in keyof typeof Colors.light]: string };

export const Spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const Radius = { sm: 6, md: 10, lg: 14, pill: 999 } as const;
export const FontSize = { xs: 12, sm: 14, md: 16, lg: 18, xl: 22, xxl: 28 } as const;

export function useColors(): ThemeColors {
  return Colors[useColorScheme() === 'dark' ? 'dark' : 'light'];
}
