import { describe, expect, it } from 'vitest';
import { historyForRequest, isWebLink, mailHref, telHref, ticketActionButton, type ChatMessage } from './assistant';

const message = (id: number, role: 'user' | 'assistant', text: string, failed = false): ChatMessage => ({ id, role, text, failed });

describe('historyForRequest', () => {
  it('sends only the last eight turns and skips failed ones', () => {
    const messages = Array.from({ length: 12 }, (_, i) => message(i, i % 2 ? 'assistant' : 'user', `turn ${i}`));
    messages[11] = message(11, 'assistant', 'Something went wrong.', true);
    const history = historyForRequest(messages);
    expect(history).toHaveLength(8);
    expect(history[0].text).toBe('turn 3');
    expect(history.some((turn) => turn.text.includes('went wrong'))).toBe(false);
    expect(Object.keys(history[0])).toEqual(['role', 'text']);
  });
});

describe('card helpers', () => {
  it('uses plain words on buttons', () => {
    expect(ticketActionButton('confirm_fixed')).toBe("Yes, it's fixed");
    expect(ticketActionButton('cancel_ticket')).toBe('Cancel this report');
  });

  it('makes phone numbers dialable and keeps emails as they are', () => {
    expect(telHref('94417 95375')).toBe('tel:9441795375');
    expect(telHref('+91 98765-43210')).toBe('tel:+919876543210');
    expect(mailHref('exambranch@mvsrec.edu.in')).toBe('mailto:exambranch@mvsrec.edu.in');
  });

  it('only treats web addresses as links', () => {
    expect(isWebLink('https://mvsrec.edu.in/index.php?id=684')).toBe(true);
    expect(isWebLink('javascript:alert(1)')).toBe(false);
    expect(isWebLink('not a url')).toBe(false);
  });
});
