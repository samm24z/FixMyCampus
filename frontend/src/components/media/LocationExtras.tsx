import React, { useEffect, useRef, useState } from 'react';
import { Loader2, MapPin } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { LocationSource } from '@/lib/api';

export interface ReportPoint {
  lat: number;
  lng: number;
  accuracy_m: number | null;
  source: Extract<LocationSource, 'device' | 'photo'>;
}

interface Props {
  /** GPS read from a photo in the browser, if any. */
  photoGps: { lat: number; lng: number } | null;
  onChange: (point: ReportPoint | null) => void;
}

function geolocationError(error: GeolocationPositionError): string {
  if (error.code === error.PERMISSION_DENIED) return "Location is turned off for this site. You can still choose the place above.";
  if (error.code === error.TIMEOUT) return "Couldn't get your location in time. You can still choose the place above.";
  return "Couldn't find your location. You can still choose the place above.";
}

/** Optional exact location: the device's position (only when asked) or the position stored in a photo. */
export const LocationExtras: React.FC<Props> = ({ photoGps, onChange }) => {
  const [device, setDevice] = useState<{ lat: number; lng: number; accuracy: number } | null>(null);
  const [includePhoto, setIncludePhoto] = useState(true);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState('');
  const emit = useRef(onChange);
  emit.current = onChange;

  // Device location wins over photo location.
  const point: ReportPoint | null = device
    ? { lat: device.lat, lng: device.lng, accuracy_m: Math.round(device.accuracy), source: 'device' }
    : photoGps && includePhoto
      ? { lat: photoGps.lat, lng: photoGps.lng, accuracy_m: null, source: 'photo' }
      : null;
  const key = point ? `${point.source}:${point.lat}:${point.lng}:${point.accuracy_m}` : '';

  useEffect(() => {
    emit.current(point);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  function locate() {
    setError('');
    if (!navigator.geolocation) {
      setError("This device can't share its location. You can still choose the place above.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        setDevice({ lat: position.coords.latitude, lng: position.coords.longitude, accuracy: position.coords.accuracy });
      },
      (failure) => {
        setLocating(false);
        setError(geolocationError(failure));
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  }

  return (
    <div className="space-y-2">
      {device ? (
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <MapPin className="h-4 w-4 text-primary" aria-hidden="true" /> Location added (±{Math.round(device.accuracy)} m)
          <button type="button" className="text-xs text-primary underline-offset-2 hover:underline" onClick={() => setDevice(null)}>Remove</button>
        </p>
      ) : (
        <Button type="button" variant="outline" size="sm" className="gap-1.5" disabled={locating} onClick={locate}>
          {locating ? <Loader2 className="h-4 w-4 animate-spin" /> : <MapPin className="h-4 w-4" />} {locating ? 'Finding you...' : 'Use my location'}
        </Button>
      )}
      {error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">{error}</div>}
      {photoGps && (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5" checked={includePhoto} onChange={(event) => setIncludePhoto(event.target.checked)} />
          <span>
            Include photo location
            <span className="block text-xs text-muted-foreground">
              Your photo has a location in it. Only staff handling the report can see it{device ? '; your device location is used instead.' : '.'}
            </span>
          </span>
        </label>
      )}
    </div>
  );
};
