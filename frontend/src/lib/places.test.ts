import { describe, expect, it } from 'vitest';
import type { Place } from './api';
import { composeLocation, splitLocation } from './places';

const place = (key: string, name: string): Place => ({ key, name, kind: 'block', description: '' });
const PLACES = [place('as-block', 'AS&H Block (First-year block)'), place('cse', 'CSE Block'), place('as2', 'AS2 (Exam Branch)'), place('lib', 'Library')];

describe('composeLocation', () => {
  it('joins the place and the room, and leaves out an empty room', () => {
    expect(composeLocation('CSE Block', 'Room 204, 2nd floor')).toBe('CSE Block, Room 204, 2nd floor');
    expect(composeLocation('CSE Block', '  ')).toBe('CSE Block');
  });
});

describe('splitLocation', () => {
  it('finds the place at the start and keeps the rest as the room', () => {
    expect(splitLocation('CSE Block, Room 204', PLACES)).toEqual({ place: PLACES[1], detail: 'Room 204' });
    expect(splitLocation('cse block', PLACES)).toEqual({ place: PLACES[1], detail: '' });
  });

  it('finds a place named after the room too', () => {
    expect(splitLocation('Room 204, CSE Block', PLACES)).toEqual({ place: PLACES[1], detail: 'Room 204' });
    expect(splitLocation('AS2 (Exam Branch), Exam Hall 2', PLACES).detail).toBe('Exam Hall 2');
  });

  it('keeps unknown places as free text', () => {
    expect(splitLocation('Room 204 of B Block', PLACES)).toEqual({ place: null, detail: 'Room 204 of B Block' });
  });
});
