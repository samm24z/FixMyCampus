import { Alert } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { Button, Screen } from '@/components/ui';
import { PasswordCard } from '@/components/account/PasswordCard';
import { ProfileCard } from '@/components/account/ProfileCard';
import { useColors } from '@/constants/theme';
import { useAuth } from '@/lib/auth';

export default function AccountScreen() {
  const { user, logout } = useAuth();
  const colors = useColors();
  if (!user) return null;

  function confirmSignOut() {
    Alert.alert('Sign out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign out', style: 'destructive', onPress: () => void logout() },
    ]);
  }

  return (
    <Screen>
      <ProfileCard key={user.id} user={user} />
      <PasswordCard key={`pw-${user.id}`} />
      <Button
        title="Sign out"
        variant="destructive"
        icon={<Ionicons name="log-out-outline" size={20} color={colors.destructiveText} />}
        onPress={confirmSignOut}
      />
    </Screen>
  );
}
