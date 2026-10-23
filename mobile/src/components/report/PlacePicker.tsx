import { View } from 'react-native';
import { AppText, SegmentedChoice, TextField } from '@/components/ui';
import type { Place } from '@/lib/api';

export const OTHER_PLACE = '__other__';

export interface PlaceValue {
  placeKey: string;
  detail: string;
  other: string;
}

export const EMPTY_PLACE: PlaceValue = { placeKey: '', detail: '', other: '' };

/** "Where is it?" as chips for the campus places (or free text if they can't load), plus a room/spot. */
export function PlacePicker({
  places,
  loading,
  failed,
  value,
  onChange,
  error,
}: {
  places: Place[];
  loading: boolean;
  failed: boolean;
  value: PlaceValue;
  onChange: (value: PlaceValue) => void;
  error?: string;
}) {
  const freeText = failed || (!loading && places.length === 0) || value.placeKey === OTHER_PLACE;
  const labels = new Map(places.map((place) => [place.key, place.name]));
  const blocks = places.filter((place) => place.kind === 'block');
  const facilities = places.filter((place) => place.kind === 'facility');
  const choose = (placeKey: string) => onChange({ ...value, placeKey });

  return (
    <View style={{ gap: 12 }}>
      <View style={{ gap: 8 }}>
        <AppText variant="label">Where is it?</AppText>
        {loading ? <AppText variant="small">Loading campus places...</AppText> : null}
        {blocks.length > 0 ? (
          <View style={{ gap: 4 }}>
            <AppText variant="small">Blocks</AppText>
            <SegmentedChoice options={blocks.map((p) => p.key)} value={value.placeKey} onChange={choose} labelFor={(key) => labels.get(key) ?? key} />
          </View>
        ) : null}
        {facilities.length > 0 ? (
          <View style={{ gap: 4 }}>
            <AppText variant="small">Other places</AppText>
            <SegmentedChoice options={facilities.map((p) => p.key)} value={value.placeKey} onChange={choose} labelFor={(key) => labels.get(key) ?? key} />
          </View>
        ) : null}
        {places.length > 0 ? (
          <SegmentedChoice options={[OTHER_PLACE]} value={value.placeKey} onChange={choose} labelFor={() => 'Somewhere else'} />
        ) : null}
      </View>
      {freeText ? (
        <TextField
          label={failed || places.length === 0 ? 'Where is it?' : 'Describe the place'}
          placeholder="For example: Bus stop near the main gate"
          value={value.other}
          onChangeText={(other) => onChange({ ...value, placeKey: value.placeKey || OTHER_PLACE, other })}
          error={error}
        />
      ) : (
        <TextField
          label="Room or spot (optional)"
          placeholder="For example: Room 204, 2nd floor"
          value={value.detail}
          onChangeText={(detail) => onChange({ ...value, detail })}
          error={error}
        />
      )}
    </View>
  );
}
