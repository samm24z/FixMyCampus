import React, { useEffect, useRef, useState } from 'react';
import { Camera, ChevronLeft, ChevronRight, Clock, ImageOff, MapPin, X } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { type AttachmentView, type TicketDetail, getApiError, uploadsApi } from '@/lib/api';
import { formatAccuracy, mapsLink, photoAgeNote } from '@/lib/gallery';

/** Signed links expire after 5 minutes; refresh the list before opening a photo if it is older than this. */
const REFRESH_AFTER_MS = 4 * 60 * 1000;

const navButtonClass =
  'absolute top-1/2 -translate-y-1/2 rounded-full bg-white/10 p-2 hover:bg-white/20 disabled:opacity-30 disabled:hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white';

export const TicketGallery: React.FC<{ ticket: TicketDetail }> = ({ ticket }) => {
  const [photos, setPhotos] = useState<AttachmentView[]>([]);
  const [fetchedAt, setFetchedAt] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  useEffect(() => {
    if (ticket.attachment_count === 0) {
      setPhotos([]);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    setError('');
    uploadsApi
      .forTicket(ticket.id)
      .then((response) => {
        if (cancelled) return;
        setPhotos(response.data);
        setFetchedAt(Date.now());
      })
      .catch((requestError) => {
        if (!cancelled) setError(getApiError(requestError, 'Photos could not be loaded.'));
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ticket.id, ticket.attachment_count]);

  // Nothing to show: no photos and no place on the map.
  if (ticket.attachment_count === 0 && ticket.report_lat == null) return null;

  /** Fetch a fresh list first when the signed links may have expired, then open the viewer. */
  async function openPhoto(index: number) {
    if (Date.now() - fetchedAt > REFRESH_AFTER_MS) {
      setIsRefreshing(true);
      setError('');
      try {
        const response = await uploadsApi.forTicket(ticket.id);
        setPhotos(response.data);
        setFetchedAt(Date.now());
      } catch (requestError) {
        setError(getApiError(requestError, 'Photos could not be loaded.'));
        return;
      } finally {
        setIsRefreshing(false);
      }
    }
    setOpenIndex(index);
  }

  const total = photos.length;
  const ageNote = photoAgeNote(
    photos.map((photo) => photo.captured_at),
    ticket.created_at,
  );
  const accuracy = formatAccuracy(ticket.report_accuracy_m);
  const hasLocation = ticket.report_lat != null && ticket.report_lng != null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-bold flex items-center gap-2">
          <Camera className="h-4 w-4 text-primary" /> Photos
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}

        {ticket.attachment_count > 0 && isLoading && <p className="text-sm text-muted-foreground">Loading photos...</p>}

        {total > 0 && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {photos.map((photo, index) => {
              const thumb = photo.thumb_url ?? photo.view_url;
              return (
                <button
                  key={photo.id}
                  type="button"
                  aria-label={`Open photo ${index + 1} of ${total}`}
                  disabled={isRefreshing}
                  onClick={() => openPhoto(index)}
                  className="aspect-square overflow-hidden rounded-lg border bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-70"
                >
                  {thumb ? (
                    <img src={thumb} alt="" loading="lazy" className="h-full w-full object-cover" />
                  ) : (
                    <span className="flex h-full w-full items-center justify-center text-muted-foreground"><ImageOff className="h-6 w-6" /></span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        {(ticket.observed_at || ageNote || hasLocation) && (
          <div className="space-y-3 border-t pt-4 text-xs">
            {ticket.observed_at && (
              <p className="flex items-center gap-1 text-muted-foreground">
                <Clock className="h-3.5 w-3.5 text-primary" /> Noticed: {new Date(ticket.observed_at).toLocaleString()}
              </p>
            )}
            {ageNote && (
              <p className="rounded-md border border-amber-500/40 bg-amber-500/5 p-2 text-amber-700 dark:text-amber-300">{ageNote}</p>
            )}
            {hasLocation && (
              <p className="flex flex-wrap items-center gap-2">
                <a
                  href={mapsLink(ticket.report_lat as number, ticket.report_lng as number)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                >
                  <MapPin className="h-3.5 w-3.5" /> Open in Maps
                </a>
                {accuracy && <span className="text-muted-foreground">{accuracy}</span>}
              </p>
            )}
          </div>
        )}
      </CardContent>

      {openIndex !== null && photos[openIndex] && (
        <Lightbox
          photos={photos}
          index={openIndex}
          onIndexChange={setOpenIndex}
          onClose={() => setOpenIndex(null)}
        />
      )}
    </Card>
  );
};

interface LightboxProps {
  photos: AttachmentView[];
  index: number;
  onIndexChange: (index: number) => void;
  onClose: () => void;
}

function Lightbox({ photos, index, onIndexChange, onClose }: LightboxProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const total = photos.length;
  const photo = photos[index];
  const url = photo.view_url ?? photo.thumb_url;

  // Focus the close button on open; give focus back to the thumbnail on close. Lock page scrolling meanwhile.
  useEffect(() => {
    const returnFocusTo = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      if (returnFocusTo instanceof HTMLElement) returnFocusTo.focus();
    };
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
      else if (event.key === 'ArrowLeft' && index > 0) onIndexChange(index - 1);
      else if (event.key === 'ArrowRight' && index < total - 1) onIndexChange(index + 1);
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [index, total, onClose, onIndexChange]);

  return (
    <div role="dialog" aria-modal="true" aria-label="Photo viewer" className="fixed inset-0 z-50 flex flex-col bg-black/95 text-white">
      <div className="flex items-center justify-between p-4">
        <span className="text-sm tabular-nums">{index + 1} / {total}</span>
        <button
          ref={closeRef}
          type="button"
          aria-label="Close photo viewer"
          onClick={onClose}
          className="rounded-full p-2 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
        >
          <X className="h-6 w-6" />
        </button>
      </div>

      <div className="relative flex min-h-0 flex-1 items-center justify-center px-14 pb-6">
        <button
          type="button"
          aria-label="Previous photo"
          disabled={index === 0}
          onClick={() => onIndexChange(index - 1)}
          className={`${navButtonClass} left-2`}
        >
          <ChevronLeft className="h-6 w-6" />
        </button>

        {url ? (
          <img src={url} alt={`Photo ${index + 1} of ${total}`} className="max-h-full max-w-full object-contain" />
        ) : (
          <p className="text-sm text-white/70">This photo can't be shown right now.</p>
        )}

        <button
          type="button"
          aria-label="Next photo"
          disabled={index === total - 1}
          onClick={() => onIndexChange(index + 1)}
          className={`${navButtonClass} right-2`}
        >
          <ChevronRight className="h-6 w-6" />
        </button>
      </div>
    </div>
  );
}
