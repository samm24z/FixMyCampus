import { View } from 'react-native';
import { AppText, SegmentedChoice } from '@/components/ui';

export type ObservedMode = 'photo' | 'now' | 'earlier' | 'yesterday';

const LABELS: Record<ObservedMode, string> = {
  photo: 'When photo was taken',
  now: 'Just now',
  earlier: 'Earlier today',
  yesterday: 'Yesterday',
};

/** "When did you notice it?" with a few presets; the actual time is worked out at submit. */
export function ObservedAtChoice({
  mode,
  hasPhotoTime,
  onChange,
}: {
  mode: ObservedMode;
  hasPhotoTime: boolean;
  onChange: (mode: ObservedMode) => void;
}) {
  const options: ObservedMode[] = hasPhotoTime ? ['photo', 'now', 'earlier', 'yesterday'] : ['now', 'earlier', 'yesterday'];
  const effective: ObservedMode = mode === 'photo' && !hasPhotoTime ? 'now' : mode;
  return (
    <View style={{ gap: 8 }}>
      <AppText variant="label">When did you notice it?</AppText>
      <SegmentedChoice options={options} value={effective} onChange={onChange} labelFor={(option) => LABELS[option]} />
    </View>
  );
}
