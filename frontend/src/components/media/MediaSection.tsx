import React, { useState } from 'react';
import type { MediaDraft } from '@/lib/api';
import { DescribeButton } from './DescribeButton';
import { LocationExtras, type ReportPoint } from './LocationExtras';
import { MediaUploader } from './MediaUploader';
import { ObservedAtField } from './ObservedAtField';
import type { ReportMedia } from './useReportMedia';

interface Props {
  media: ReportMedia;
  description: string;
  location: string;
  /** Fill the form from the draft; the section shows the "please check it" notes itself. */
  onDraft: (draft: MediaDraft) => void;
  onPoint: (point: ReportPoint | null) => void;
  onObservedAt: (value: Date | null) => void;
  compact?: boolean;
}

/** Photos (optional): uploader, "Describe it for me", exact location and the time it was noticed. */
export const MediaSection: React.FC<Props> = ({ media, description, location, onDraft, onPoint, onObservedAt, compact = false }) => {
  const [draft, setDraft] = useState<MediaDraft | null>(null);

  return (
    <div className={compact ? 'space-y-2' : 'space-y-4'}>
      <p className="text-sm font-medium">Photos (optional)</p>
      <MediaUploader media={media} compact={compact} />
      <DescribeButton media={media} description={description} location={location} onDraft={(next) => { setDraft(next); onDraft(next); }} />
      {draft && (
        <div className="space-y-1 text-xs text-muted-foreground">
          <p>Filled in from your photos — please check it before sending.</p>
          {draft.contains_people && <p className="text-amber-700 dark:text-amber-400">A person may be visible in a photo — consider removing it.</p>}
        </div>
      )}
      <LocationExtras photoGps={media.firstPhotoGps} onChange={onPoint} />
      <ObservedAtField captures={media.captures} onChange={onObservedAt} />
    </div>
  );
};
