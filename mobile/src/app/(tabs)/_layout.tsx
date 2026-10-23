import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router';
import type { ColorValue } from 'react-native';
import { useColors } from '@/constants/theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

const icon = (name: IconName) => ({ color, size }: { color: ColorValue; size: number }) => <Ionicons name={name} color={color as string} size={size} />;

export default function TabLayout() {
  const colors = useColors();
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarStyle: { backgroundColor: colors.card, borderTopColor: colors.border },
        headerStyle: { backgroundColor: colors.card },
        headerTitleStyle: { color: colors.text },
        sceneStyle: { backgroundColor: colors.background },
      }}>
      <Tabs.Screen name="index" options={{ title: 'My tickets', tabBarLabel: 'Tickets', tabBarIcon: icon('list') }} />
      <Tabs.Screen name="report" options={{ title: 'Report an issue', tabBarLabel: 'Report', tabBarIcon: icon('add-circle') }} />
      <Tabs.Screen name="assistant" options={{ title: 'Campus assistant', tabBarLabel: 'Assistant', tabBarIcon: icon('chatbubbles') }} />
      <Tabs.Screen name="account" options={{ title: 'Account', tabBarIcon: icon('person-circle') }} />
    </Tabs>
  );
}
