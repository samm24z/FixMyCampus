import { describe, expect, it } from 'vitest';
import { confidenceLabel, reportsLabel, similarityLabel } from './tickets';

describe('plain-language labels', () => {
  it('describes how sure a suggestion is in words', () => {
    expect(confidenceLabel(0.95)).toBe('Very sure (95%)');
    expect(confidenceLabel(0.82)).toBe('Fairly sure (82%)');
    expect(confidenceLabel(0.55)).toBe('Not fully sure (55%)');
    expect(confidenceLabel(0.2)).toBe('Just a guess (20%)');
  });

  it('shows similarity and group size without jargon', () => {
    expect(similarityLabel(0.853)).toBe('85% similar');
    expect(reportsLabel(3)).toBe('Reported by 3 people');
  });
});
