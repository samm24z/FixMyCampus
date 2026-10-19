import { useEffect, useState } from 'react';
import { campusApi, type Place } from '@/lib/api';

let request: Promise<Place[]> | null = null;

/** The campus places, fetched once per page load; a failed request is tried again next time. */
export function loadPlaces(): Promise<Place[]> {
  request ??= campusApi.places().then(
    (response) => response.data,
    (error) => {
      request = null;
      throw error;
    },
  );
  return request;
}

/** `places` is empty until they load, and stays empty (with `failed` set) if the request fails. */
export function useCampusPlaces() {
  const [state, setState] = useState<{ places: Place[]; loading: boolean; failed: boolean }>({ places: [], loading: true, failed: false });
  useEffect(() => {
    let active = true;
    loadPlaces().then(
      (places) => active && setState({ places, loading: false, failed: false }),
      () => active && setState({ places: [], loading: false, failed: true }),
    );
    return () => { active = false; };
  }, []);
  return state;
}

/** "CSE Block, Room 204", or just "CSE Block". */
export const composeLocation = (placeName: string, detail: string) =>
  [placeName.trim(), detail.trim()].filter(Boolean).join(', ');

const SEPARATORS = /^[\s,;:\-–]+|[\s,;:\-–]+$/g;

/** Splits a location like "CSE Block, Room 204" into the place it names (longest name wins) and the rest. */
export function splitLocation(location: string, places: Place[]): { place: Place | null; detail: string } {
  const lower = location.toLowerCase();
  const found = [...places]
    .sort((a, b) => b.name.length - a.name.length)
    .find((place) => lower.includes(place.name.toLowerCase()));
  if (!found) return { place: null, detail: location.trim() };
  const at = lower.indexOf(found.name.toLowerCase());
  const rest = `${location.slice(0, at)} ${location.slice(at + found.name.length)}`;
  return { place: found, detail: rest.replace(SEPARATORS, '').replace(/\s+/g, ' ') };
}
