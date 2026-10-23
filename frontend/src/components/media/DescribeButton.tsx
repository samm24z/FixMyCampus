import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getApiError, uploadsApi, type MediaDraft } from '@/lib/api';
import type { ReportMedia } from './useReportMedia';

interface Props {
  media: ReportMedia;
  /** What the student has typed so far; sent as a hint, first 300 characters. */
  description: string;
  location: string;
  onDraft: (draft: MediaDraft) => void;
}

/** Asks the server to draft the report from the photos. The student always reviews the result. */
export const DescribeButton: React.FC<Props> = ({ media, description, location, onDraft }) => {
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');

  async function describe() {
    setError('');
    setWorking(true);
    const ids = media.readyIds;
    try {
      const { data } = await uploadsApi.describe({
        upload_ids: ids,
        note: description.trim().slice(0, 300) || null,
        place: location.trim() || null,
      });
      onDraft(data);
    } catch (requestError) {
      // 422: the server rejected and deleted these photos.
      if (axios.isAxiosError(requestError) && requestError.response?.status === 422) media.drop(ids);
      setError(getApiError(requestError, "Couldn't describe it right now — please type a short description."));
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="space-y-1.5">
      <Button type="button" variant="outline" size="sm" className="gap-1.5" disabled={working || media.busy || media.readyIds.length === 0} onClick={describe}>
        {working ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} {working ? 'Looking at your photos...' : 'Describe it for me'}
      </Button>
      {error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">{error}</div>}
    </div>
  );
};
