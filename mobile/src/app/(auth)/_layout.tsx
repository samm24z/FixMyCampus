import { Stack } from 'expo-router';
import { useColors } from '@/constants/theme';

export default function AuthLayout() {
  const colors = useColors();
  return (
    <Stack screenOptions={{ headerTintColor: colors.primary, headerBackTitle: 'Back', contentStyle: { backgroundColor: colors.background } }}>
      <Stack.Screen name="login" options={{ headerShown: false }} />
      <Stack.Screen name="register" options={{ title: 'Create account' }} />
      <Stack.Screen name="forgot-password" options={{ title: 'Reset password' }} />
    </Stack>
  );
}
