import { useQueryClient } from '@tanstack/react-query';
import * as Location from 'expo-location';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { View } from 'react-native';
import { DescribeButton } from '@/components/report/DescribeButton';
import { LocationShare, type ReportPoint } from '@/components/report/LocationShare';
import { ObservedAtChoice, type ObservedMode } from '@/components/report/ObservedAtChoice';
import { PhotoPicker } from '@/components/report/PhotoPicker';
import { EMPTY_PLACE, OTHER_PLACE, PlacePicker, type PlaceValue } from '@/components/report/PlacePicker';
import { AppText, Button, Card, ErrorBanner, Screen, SegmentedChoice, TextField } from '@/components/ui';
import { useReportMedia } from '@/hooks/useReportMedia';
import { CATEGORY_OPTIONS, getApiError, ticketsApi, type MediaDraft, type TicketPriority } from '@/lib/api';
import { pickObservedAt } from '@/lib/media';
import { composeLocation, splitLocation, useCampusPlaces } from '@/lib/places';
import { PRIORITIES, priorityLabel } from '@/lib/tickets';

interface FormState {
  title: string;
  description: string;
  category: string;
  priority: TicketPriority;
}

const INITIAL_FORM: FormState = { title: '', description: '', category: CATEGORY_OPTIONS[0], priority: 'MEDIUM' };
const HOUR_MS = 60 * 60 * 1000;

function observedAtFor(mode: ObservedMode, captures: (Date | null)[], now: Date): Date {
  if (mode === 'photo') return pickObservedAt(captures, now);
  if (mode === 'yesterday') return new Date(now.getTime() - 24 * HOUR_MS);
  if (mode === 'earlier') {
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return new Date(Math.max(startOfToday.getTime(), now.getTime() - 3 * HOUR_MS));
  }
  return now;
}

export default function ReportScreen() {
  const params = useLocalSearchParams<{
    title?: string;
    description?: string;
    category?: string;
    location?: string;
    priority?: string;
    prefill?: string;
  }>();
  const queryClient = useQueryClient();
  const media = useReportMedia();
  const { places, loading: placesLoading, failed: placesFailed } = useCampusPlaces();

  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [place, setPlace] = useState<PlaceValue>(EMPTY_PLACE);
  const [point, setPoint] = useState<ReportPoint | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState('');
  const [observedMode, setObservedMode] = useState<ObservedMode>('photo');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{ title?: string; description?: string; place?: string }>({});
  const [submitting, setSubmitting] = useState(false);

  const setField = <K extends keyof FormState>(field: K, value: FormState[K]) => setForm((current) => ({ ...current, [field]: value }));

  // ---- location text (campus place + detail, or free text)
  const chosenPlace = places.find((p) => p.key === place.placeKey);
  const locationText =
    place.placeKey && place.placeKey !== OTHER_PLACE && chosenPlace ? composeLocation(chosenPlace.name, place.detail) : place.other.trim();

  function applyLocationText(text: string) {
    const { place: found, detail } = splitLocation(text, places);
    setPlace(found ? { placeKey: found.key, detail, other: '' } : { placeKey: OTHER_PLACE, detail: '', other: text.trim() });
  }

  // ---- prefill from the assistant screen
  const appliedPrefill = useRef('');
  useEffect(() => {
    const signature = params.prefill ?? [params.title, params.description, params.category, params.location, params.priority].join('|');
    const hasAny = [params.title, params.description, params.category, params.location, params.priority].some((value) => value);
    if (!hasAny || appliedPrefill.current === signature) return;
    // Wait for the places so the location can be matched to one of them.
    if (params.location && placesLoading) return;
    appliedPrefill.current = signature;
    setForm((current) => ({
      title: params.title ?? current.title,
      description: params.description ?? current.description,
      category: params.category && CATEGORY_OPTIONS.includes(params.category) ? params.category : current.category,
      priority: PRIORITIES.includes(params.priority as TicketPriority) ? (params.priority as TicketPriority) : current.priority,
    }));
    if (params.location) applyLocationText(params.location);
    setFieldErrors({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.prefill, params.title, params.description, params.category, params.location, params.priority, placesLoading]);

  // ---- AI draft
  function applyDraft(draft: MediaDraft) {
    setForm((current) => ({
      title: draft.title,
      description: draft.description,
      category: CATEGORY_OPTIONS.includes(draft.category) ? draft.category : current.category,
      priority: PRIORITIES.includes(draft.priority) ? draft.priority : current.priority,
    }));
    if (!locationText && draft.location_hint) applyLocationText(draft.location_hint);
    setFieldErrors({});
  }

  // ---- exact location
  const photoGps = media.firstPhotoGps;
  const shownPoint = point?.source === 'photo' && !photoGps ? null : point;

  async function useDeviceLocation() {
    setLocationError('');
    setLocating(true);
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (!permission.granted) {
        setLocationError('Location is turned off for this app. You can still choose the place above.');
        return;
      }
      const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      setPoint({
        lat: position.coords.latitude,
        lng: position.coords.longitude,
        accuracy_m: position.coords.accuracy != null ? Math.round(position.coords.accuracy) : null,
        source: 'device',
      });
    } catch {
      setLocationError("Couldn't find your location. You can still choose the place above.");
    } finally {
      setLocating(false);
    }
  }

  function usePhotoLocation() {
    if (photoGps) setPoint({ lat: photoGps.lat, lng: photoGps.lng, accuracy_m: null, source: 'photo' });
  }

  // ---- submit
  async function submit() {
    setError('');
    const errors: typeof fieldErrors = {};
    if (form.title.trim().length < 5) errors.title = 'Please give it a title of at least 5 characters.';
    if (form.description.trim().length < 10) errors.description = 'Please describe the problem in at least 10 characters.';
    if (locationText.length < 2) errors.place = 'Please tell us where it is.';
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    const attachmentIds = media.readyIds;
    try {
      const { data } = await ticketsApi.create({
        title: form.title.trim(),
        description: form.description.trim(),
        category: form.category,
        priority: form.priority,
        location: locationText,
        attachment_ids: attachmentIds,
        observed_at: observedAtFor(observedMode, media.captures, new Date()).toISOString(),
        report_lat: shownPoint?.lat ?? null,
        report_lng: shownPoint?.lng ?? null,
        report_accuracy_m: shownPoint?.accuracy_m ?? null,
        location_source: shownPoint?.source ?? null,
      });
      setForm(INITIAL_FORM);
      setPlace(EMPTY_PLACE);
      setPoint(null);
      setObservedMode('photo');
      setFieldErrors({});
      media.reset();
      void queryClient.invalidateQueries({ queryKey: ['tickets'] });
      void queryClient.invalidateQueries({ queryKey: ['summary'] });
      router.push(`/ticket/${data.ticket_number}`);
    } catch (submissionError) {
      // A photo the server can't link (expired, already used) comes back as a 422 that asks the
      // user to remove and re-add it; the photos stay listed so they can do that.
      setError(getApiError(submissionError));
    } finally {
      setSubmitting(false);
    }
  }

  const hasPhotoTime = media.captures.some((d) => d !== null);

  return (
    <Screen>
      <View style={{ gap: 4 }}>
        <AppText variant="title">Report a problem</AppText>
        <AppText variant="muted">Tell us what&apos;s wrong and where. We&apos;ll pass it to the right team.</AppText>
      </View>

      <ErrorBanner message={error} />

      <Card>
        <PhotoPicker media={media} />
        {media.items.length > 0 ? (
          <DescribeButton media={media} description={form.description} location={locationText} onDraft={applyDraft} />
        ) : null}
      </Card>

      <TextField
        label="Title"
        placeholder="For example: Projector not working in Room 204"
        value={form.title}
        onChangeText={(value) => setField('title', value)}
        error={fieldErrors.title}
      />
      <TextField
        label="Description"
        placeholder="What's wrong, since when, and who is affected?"
        multiline
        value={form.description}
        onChangeText={(value) => setField('description', value)}
        error={fieldErrors.description}
      />

      <View style={{ gap: 8 }}>
        <AppText variant="label">Category</AppText>
        <SegmentedChoice options={CATEGORY_OPTIONS} value={form.category} onChange={(value) => setField('category', value)} />
      </View>

      <View style={{ gap: 8 }}>
        <AppText variant="label">How urgent is it?</AppText>
        <SegmentedChoice
          options={PRIORITIES}
          value={form.priority}
          onChange={(value) => setField('priority', value)}
          labelFor={priorityLabel}
        />
      </View>

      <PlacePicker
        places={places}
        loading={placesLoading}
        failed={placesFailed}
        value={place}
        onChange={setPlace}
        error={fieldErrors.place}
      />

      <LocationShare
        point={shownPoint}
        photoGpsAvailable={photoGps !== null}
        locating={locating}
        error={locationError}
        onUseDevice={useDeviceLocation}
        onUsePhoto={usePhotoLocation}
        onClear={() => setPoint(null)}
      />

      <ObservedAtChoice mode={observedMode} hasPhotoTime={hasPhotoTime} onChange={setObservedMode} />

      <Button
        title={submitting ? 'Sending...' : media.busy ? 'Waiting for photos...' : 'Send report'}
        loading={submitting}
        disabled={media.busy}
        onPress={submit}
      />
    </Screen>
  );
}
