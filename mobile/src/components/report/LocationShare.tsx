import Ionicons from '@expo/vector-icons/Ionicons';
import { View } from 'react-native';
import { AppText, Button, Card, ErrorBanner } from '@/components/ui';
import { useColors } from '@/constants/theme';
import type { LocationSource } from '@/lib/api';

export interface ReportPoint {
  lat: number;
  lng: number;
  accuracy_m: number | null;
  source: Extract<LocationSource, 'device' | 'photo'>;
}

/** Optional exact location: the phone's position (only when asked) or the position stored in a photo. */
export function LocationShare({
  point,
  photoGpsAvailable,
  locating,
  error,
  onUseDevice,
  onUsePhoto,
  onClear,
}: {
  point: ReportPoint | null;
  photoGpsAvailable: boolean;
  locating: boolean;
  error: string;
  onUseDevice: () => void;
  onUsePhoto: () => void;
  onClear: () => void;
}) {
  const colors = useColors();
  return (
    <View style={{ gap: 8 }}>
      <AppText variant="label">Exact location (optional)</AppText>
      <AppText variant="small">Helps staff find the spot faster. Only staff handling the report can see it.</AppText>
      {point ? (
        <Card style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Ionicons name="location" size={18} color={colors.primary} />
            <AppText variant="label" style={{ flex: 1 }}>
              {point.source === 'device' ? 'Your phone location' : 'Location from your photo'}
              {point.accuracy_m !== null ? ` (within ${point.accuracy_m} m)` : ''}
            </AppText>
          </View>
          <AppText variant="small">
            Will be shared: {point.lat.toFixed(5)}, {point.lng.toFixed(5)}
          </AppText>
          <Button title="Don't share it" variant="outline" onPress={onClear} />
        </Card>
      ) : (
        <View style={{ gap: 8 }}>
          <Button
            title={locating ? 'Finding you...' : 'Use my location'}
            variant="outline"
            loading={locating}
            onPress={onUseDevice}
            icon={<Ionicons name="locate-outline" size={18} color={colors.text} />}
          />
          {photoGpsAvailable ? (
            <Button
              title="Use photo location"
              variant="ghost"
              onPress={onUsePhoto}
              icon={<Ionicons name="image-outline" size={18} color={colors.primary} />}
            />
          ) : null}
        </View>
      )}
      {point?.source === 'device' && photoGpsAvailable ? (
        <Button title="Use photo location instead" variant="ghost" onPress={onUsePhoto} />
      ) : null}
      <ErrorBanner message={error} />
    </View>
  );
}
