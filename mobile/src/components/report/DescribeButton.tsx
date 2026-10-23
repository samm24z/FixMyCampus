import Ionicons from '@expo/vector-icons/Ionicons';
import axios from 'axios';
import { useState } from 'react';
import { View } from 'react-native';
import { AppText, Button, ErrorBanner, NoticeBanner } from '@/components/ui';
import { useColors } from '@/constants/theme';
import type { ReportMedia } from '@/hooks/useReportMedia';
import { getApiError, uploadsApi, type MediaDraft } from '@/lib/api';

/** Asks the server to draft the report from the photos. The user always reviews the result. */
export function DescribeButton({
  media,
  description,
  location,
  onDraft,
}: {
  media: ReportMedia;
  /** What the user has typed so far; sent as a hint, first 300 characters. */
  description: string;
  location: string;
  onDraft: (draft: MediaDraft) => void;
}) {
  const colors = useColors();
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState<MediaDraft | null>(null);

  async function describe() {
    setError('');
    setDone(null);
    setWorking(true);
    const ids = media.readyIds;
    try {
      const { data } = await uploadsApi.describe({
        upload_ids: ids,
        note: description.trim().slice(0, 300) || null,
        place: location.trim() || null,
      });
      onDraft(data);
      setDone(data);
    } catch (requestError) {
      // 422: the server rejected and deleted these photos.
      if (axios.isAxiosError(requestError) && requestError.response?.status === 422) media.drop(ids);
      setError(getApiError(requestError, "Couldn't describe it right now. Please type a short description instead."));
    } finally {
      setWorking(false);
    }
  }

  const disabled = media.busy || media.readyIds.length === 0;
  return (
    <View style={{ gap: 8 }}>
      <Button
        title={working ? 'Looking at your photos...' : 'Describe it for me'}
        variant="secondary"
        loading={working}
        disabled={disabled}
        onPress={describe}
        icon={<Ionicons name="sparkles-outline" size={18} color={colors.secondaryText} />}
      />
      {disabled && !working ? (
        <AppText variant="small">{media.busy ? 'Waiting for your photos to finish uploading...' : 'Add a photo first.'}</AppText>
      ) : null}
      <ErrorBanner message={error} />
      {done ? <NoticeBanner message="We filled in the title, description and details below. Please check them and fix anything that is off." /> : null}
      {done?.contains_people ? (
        <AppText variant="small" style={{ color: colors.warning }}>
          Your photo seems to show people. Consider retaking it without anyone in the frame, if you can.
        </AppText>
      ) : null}
    </View>
  );
}
