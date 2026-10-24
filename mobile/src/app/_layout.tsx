import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';
import { useColorScheme } from 'react-native';
import { Colors } from '@/constants/theme';
import { AuthProvider, useAuth } from '@/lib/auth';

SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

/** Signed-out people only see the (auth) screens; signed-in people only see the app. */
function RootNavigator() {
  const { user, isLoading } = useAuth();
  const scheme = useColorScheme() === 'dark' ? 'dark' : 'light';

  useEffect(() => {
    if (!isLoading) SplashScreen.hideAsync();
  }, [isLoading]);

  if (isLoading) return null;
  return (
    <Stack
      screenOptions={{
        headerTintColor: Colors[scheme].primary,
        headerTitleStyle: { color: Colors[scheme].text },
        contentStyle: { backgroundColor: Colors[scheme].background },
      }}>
      <Stack.Protected guard={!!user}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="ticket/[ref]" options={{ title: 'Ticket', headerBackTitle: 'Back' }} />
        <Stack.Screen name="notifications" options={{ title: 'Notifications', headerBackTitle: 'Back' }} />
      </Stack.Protected>
      <Stack.Protected guard={!user}>
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  const scheme = useColorScheme();
  return (
    <ThemeProvider value={scheme === 'dark' ? DarkTheme : DefaultTheme}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RootNavigator />
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
