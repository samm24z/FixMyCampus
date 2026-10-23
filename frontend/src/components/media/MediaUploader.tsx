import React, { useId, useRef, useState } from 'react';
import { Camera, ImagePlus, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MAX_PHOTOS } from '@/lib/media';
import type { ReportMedia } from './useReportMedia';

interface Props {
  media: ReportMedia;
  compact?: boolean;
}

/** Drop zone, "Add photos" button and thumbnails with progress. */
export const MediaUploader: React.FC<Props> = ({ media, compact = false }) => {
  const inputId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const full = media.slotsUsed >= MAX_PHOTOS;

  function pick(files: FileList | null) {
    if (files && files.length > 0) media.add(files);
    if (input.current) input.current.value = '';
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); if (!full) pick(event.dataTransfer.files); }}
        className={`flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-center ${compact ? 'p-3' : 'p-5'} ${dragging ? 'border-primary bg-primary/5' : 'bg-muted/20'}`}
      >
        <Camera className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <p className="text-xs text-muted-foreground">Take or choose photos of the problem, or drop them here.</p>
        <input id={inputId} ref={input} type="file" accept="image/*" multiple className="sr-only" aria-label="Choose photos" onChange={(event) => pick(event.target.files)} disabled={full} />
        <Button type="button" variant="outline" size="sm" className="gap-1.5" disabled={full} onClick={() => input.current?.click()}>
          <ImagePlus className="h-4 w-4" /> Add photos
        </Button>
        <p className="text-xs text-muted-foreground">{media.slotsUsed} / {MAX_PHOTOS} · Please avoid photographing people.</p>
      </div>
      {media.notice && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">{media.notice}</div>}
      {media.items.length > 0 && (
        <ul className={`grid gap-2 ${compact ? 'grid-cols-3' : 'grid-cols-3 sm:grid-cols-5'}`}>
          {media.items.map((item) => (
            <li key={item.localId} className="space-y-1">
              <div className="relative aspect-square overflow-hidden rounded-md border bg-muted">
                {item.previewUrl && <img src={item.previewUrl} alt={`Photo: ${item.name}`} className="h-full w-full object-cover" />}
                {(item.status === 'preparing' || item.status === 'uploading') && (
                  <div className="absolute inset-0 flex items-center justify-center bg-background/50">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-label={item.status === 'preparing' ? 'Preparing photo' : 'Uploading photo'} />
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => media.remove(item.localId)}
                  aria-label={`Remove photo ${item.name}`}
                  className="absolute right-1 top-1 rounded-full bg-background/90 p-1 shadow hover:bg-background"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              {item.status === 'uploading' && (
                <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label="Upload progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(item.progress * 100)}>
                  <div className="h-full bg-primary transition-all" style={{ width: `${Math.round(item.progress * 100)}%` }} />
                </div>
              )}
              {item.status === 'error' && <p className="text-xs text-destructive">{item.error}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
