import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { Alert, Linking, Pressable, StyleSheet, View } from 'react-native';
import { AppText, Button } from '@/components/ui';
import { Radius, Spacing, useColors } from '@/constants/theme';
import type { MediaItem, ReportMedia } from '@/hooks/useReportMedia';
import { MAX_PHOTOS } from '@/lib/media';

const PICK_OPTIONS = { mediaTypes: ['images'] as ImagePicker.MediaType[], exif: true, quality: 1 };

function Thumb({ item, onRemove }: { item: MediaItem; onRemove: () => void }) {
  const colors = useColors();
  const working = item.status === 'preparing' || item.status === 'uploading';
  return (
    <View style={styles.thumbWrap}>
      <View style={[styles.thumb, { borderColor: item.status === 'error' ? colors.destructive : colors.border, backgroundColor: colors.secondary }]}>
        <Image source={{ uri: item.previewUri }} style={StyleSheet.absoluteFill} contentFit="cover" />
        {working ? (
          <View style={styles.overlay}>
            <AppText variant="small" style={{ color: '#FFFFFF', fontWeight: '600' }}>
              {item.status === 'preparing' ? 'Preparing' : `${Math.round(item.progress * 100)}%`}
            </AppText>
            {item.status === 'uploading' ? (
              <View style={styles.barTrack}>
                <View style={[styles.barFill, { width: `${Math.round(item.progress * 100)}%`, backgroundColor: colors.primary }]} />
              </View>
            ) : null}
          </View>
        ) : null}
        {item.status === 'error' ? (
          <View style={[styles.overlay, { backgroundColor: 'rgba(127,29,29,0.75)' }]}>
            <Ionicons name="alert-circle" size={20} color="#FFFFFF" />
          </View>
        ) : null}
        {item.status === 'ready' ? (
          <View style={[styles.tick, { backgroundColor: colors.success }]}>
            <Ionicons name="checkmark" size={12} color="#FFFFFF" />
          </View>
        ) : null}
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Remove photo ${item.name}`}
        hitSlop={8}
        onPress={onRemove}
        style={[styles.remove, { backgroundColor: colors.text }]}>
        <Ionicons name="close" size={14} color={colors.background} />
      </Pressable>
      {item.status === 'error' ? (
        <AppText variant="small" numberOfLines={3} style={{ color: colors.destructive, width: 96 }}>
          {item.error}
        </AppText>
      ) : null}
    </View>
  );
}

/** Take a photo / choose from the library, plus thumbnails of what has been added. */
export function PhotoPicker({ media }: { media: ReportMedia }) {
  const colors = useColors();
  const [message, setMessage] = useState('');
  const remaining = MAX_PHOTOS - media.slotsUsed;
  const full = remaining <= 0;

  async function takePhoto() {
    setMessage('');
    try {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        setMessage('Camera access is turned off. You can allow it in Settings, or choose a photo from your library.');
        if (!permission.canAskAgain) {
          Alert.alert('Camera is turned off', 'Allow camera access in Settings to take photos.', [
            { text: 'Not now', style: 'cancel' },
            { text: 'Open Settings', onPress: () => void Linking.openSettings() },
          ]);
        }
        return;
      }
      const result = await ImagePicker.launchCameraAsync(PICK_OPTIONS);
      if (!result.canceled) media.add(result.assets);
    } catch {
      setMessage("Couldn't open the camera. You can choose a photo from your library instead.");
    }
  }

  async function choosePhotos() {
    setMessage('');
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        ...PICK_OPTIONS,
        allowsMultipleSelection: remaining > 1,
        selectionLimit: Math.max(remaining, 1),
      });
      if (!result.canceled) media.add(result.assets);
    } catch {
      setMessage("Couldn't open your photos. Please try again.");
    }
  }

  return (
    <View style={{ gap: Spacing.md }}>
      <View>
        <AppText variant="label">Photos (optional)</AppText>
        <AppText variant="small">
          Add up to {MAX_PHOTOS}. {media.slotsUsed}/{MAX_PHOTOS} added. A photo can help us describe the problem for you.
        </AppText>
      </View>
      <View style={styles.row}>
        <Button
          title="Take photo"
          variant="outline"
          disabled={full}
          onPress={takePhoto}
          icon={<Ionicons name="camera-outline" size={18} color={colors.text} />}
          style={styles.flex}
        />
        <Button
          title="Choose from library"
          variant="outline"
          disabled={full}
          onPress={choosePhotos}
          icon={<Ionicons name="images-outline" size={18} color={colors.text} />}
          style={styles.flex}
        />
      </View>
      {message || media.notice ? (
        <AppText variant="small" style={{ color: colors.warning }}>
          {message || media.notice}
        </AppText>
      ) : null}
      {media.items.length > 0 ? (
        <View style={styles.thumbs}>
          {media.items.map((item) => (
            <Thumb key={item.localId} item={item} onRemove={() => media.remove(item.localId)} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: Spacing.sm },
  flex: { flex: 1, paddingHorizontal: Spacing.sm },
  thumbs: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.md },
  thumbWrap: { gap: Spacing.xs },
  thumb: { width: 96, height: 96, borderRadius: Radius.md, borderWidth: 1, overflow: 'hidden' },
  overlay: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.xs,
  },
  barTrack: { width: '70%', height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.35)', overflow: 'hidden' },
  barFill: { height: '100%' },
  tick: { position: 'absolute', right: 4, bottom: 4, width: 18, height: 18, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  remove: { position: 'absolute', top: -6, right: -6, width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
});
