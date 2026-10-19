import React, { useEffect, useId, useRef, useState } from 'react';
import { composeLocation, splitLocation, useCampusPlaces } from '@/lib/places';

const FIELD = 'w-full rounded-lg border bg-background px-3 py-2 text-sm';
const OTHER = '__other__';

interface Props {
  /** A location to start from (for example one the assistant wrote); the matching place is pre-selected. */
  initial?: string;
  onChange: (location: string) => void;
  className?: string;
}

/** "Where is it?" (a campus place or somewhere else) and an optional room or spot, composed into one location text. */
export const LocationPicker: React.FC<Props> = ({ initial = '', onChange, className = FIELD }) => {
  const idPrefix = useId();
  const { places, loading, failed } = useCampusPlaces();
  const [placeKey, setPlaceKey] = useState('');
  const [detail, setDetail] = useState('');
  const [other, setOther] = useState(initial);
  const touched = useRef(false);
  const blocks = places.filter((place) => place.kind === 'block');
  const facilities = places.filter((place) => place.kind === 'facility');
  const freeText = failed || (!loading && places.length === 0) || placeKey === OTHER;

  useEffect(() => {
    if (touched.current || places.length === 0 || !initial) return;
    const { place, detail: rest } = splitLocation(initial, places);
    setPlaceKey(place ? place.key : OTHER);
    setDetail(place ? rest : '');
    setOther(place ? '' : initial);
    onChange(place ? composeLocation(place.name, rest) : initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [places]);

  function emit(nextKey: string, nextDetail: string, nextOther: string) {
    touched.current = true;
    const place = places.find((p) => p.key === nextKey);
    onChange(nextKey === OTHER || !place ? nextOther : composeLocation(place.name, nextDetail));
  }
  const labelClass = 'text-sm font-medium';

  if (freeText && placeKey !== OTHER) {
    return (
      <div className="space-y-2">
        <label htmlFor={`${idPrefix}-other`} className={labelClass}>Where is it?</label>
        <input id={`${idPrefix}-other`} required minLength={2} className={className} placeholder="For example: CSE Block, Room 204, 2nd floor" value={other}
          onChange={(event) => { setOther(event.target.value); emit(OTHER, '', event.target.value); }} />
      </div>
    );
  }
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <div className="space-y-2">
        <label htmlFor={`${idPrefix}-place`} className={labelClass}>Where is it?</label>
        <select id={`${idPrefix}-place`} required className={className} value={placeKey}
          onChange={(event) => { setPlaceKey(event.target.value); emit(event.target.value, detail, other); }}>
          <option value="" disabled>Choose a place</option>
          {blocks.length > 0 && <optgroup label="Blocks">{blocks.map((place) => <option key={place.key} value={place.key}>{place.name}</option>)}</optgroup>}
          {facilities.length > 0 && <optgroup label="Other places">{facilities.map((place) => <option key={place.key} value={place.key}>{place.name}</option>)}</optgroup>}
          <option value={OTHER}>Somewhere else</option>
        </select>
      </div>
      <div className="space-y-2">
        {placeKey === OTHER ? (
          <>
            <label htmlFor={`${idPrefix}-other`} className={labelClass}>Describe the place</label>
            <input id={`${idPrefix}-other`} required minLength={2} className={className} placeholder="For example: Bus stop near the main gate" value={other}
              onChange={(event) => { setOther(event.target.value); emit(OTHER, detail, event.target.value); }} />
          </>
        ) : (
          <>
            <label htmlFor={`${idPrefix}-detail`} className={labelClass}>Room or spot (optional)</label>
            <input id={`${idPrefix}-detail`} className={className} placeholder="For example: Room 204, 2nd floor" value={detail}
              onChange={(event) => { setDetail(event.target.value); emit(placeKey, event.target.value, other); }} />
          </>
        )}
      </div>
    </div>
  );
};
