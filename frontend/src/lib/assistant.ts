import { ticketsApi, type AssistantAction, type AssistantSource, type AssistantTurn, type TicketDetail } from '@/lib/api';

export const STARTER_QUESTIONS = [
  'Who is the head of the CSE department?',
  'How do I pay my fees?',
  'How do I contact the exam branch?',
  'What are the bus routes?',
  'Check my tickets',
];

export const MAX_HISTORY_TURNS = 8;

export interface ChatMessage extends AssistantTurn {
  id: number;
  reply?: { sources: AssistantSource[]; actions: AssistantAction[]; status: string };
  failed?: boolean;
}

/** The last few turns, in the shape the server expects; errors and empty turns are left out. */
export function historyForRequest(messages: ChatMessage[]): AssistantTurn[] {
  return messages
    .filter((message) => !message.failed && message.text.trim())
    .slice(-MAX_HISTORY_TURNS)
    .map(({ role, text }) => ({ role, text: text.slice(0, 2000) }));
}

export type TicketAction = Extract<AssistantAction, { ticket_number: string }>;

const BUTTON_LABELS: Record<TicketAction['type'], string> = {
  confirm_fixed: "Yes, it's fixed",
  reopen_ticket: 'Reopen this ticket',
  cancel_ticket: 'Cancel this report',
  add_comment: 'Add this comment',
};
const CARD_TITLES: Record<TicketAction['type'], string> = {
  confirm_fixed: 'Mark as fixed',
  reopen_ticket: 'Reopen a ticket',
  cancel_ticket: 'Cancel a report',
  add_comment: 'Add a comment',
};
const DONE_TEXT: Record<TicketAction['type'], string> = {
  confirm_fixed: 'Marked as fixed. Thank you!',
  reopen_ticket: 'Reopened. Someone will look at it again.',
  cancel_ticket: 'Report cancelled.',
  add_comment: 'Comment added.',
};

export const ticketActionButton = (type: TicketAction['type']) => BUTTON_LABELS[type];
export const ticketActionTitle = (type: TicketAction['type']) => CARD_TITLES[type];
export const ticketActionDone = (type: TicketAction['type']) => DONE_TEXT[type];

/** Runs the ticket change a card describes, through the same endpoints the ticket page uses. */
export function runTicketAction(action: TicketAction): Promise<{ data: TicketDetail }> {
  switch (action.type) {
    case 'confirm_fixed':
      return ticketsApi.confirm(action.ticket_number);
    case 'reopen_ticket':
      return ticketsApi.reopen(action.ticket_number);
    case 'cancel_ticket':
      return ticketsApi.withdraw(action.ticket_number);
    case 'add_comment':
      return ticketsApi.comment(action.ticket_number, action.text);
  }
}

/** Phone numbers as published, made dialable. */
export const telHref = (phone: string) => `tel:${phone.replace(/[^\d+]/g, '')}`;
export const mailHref = (email: string) => `mailto:${email}`;

/** Only web links from the college site are opened; anything else is not shown as a link. */
export function isWebLink(url: string) {
  try {
    return ['http:', 'https:'].includes(new URL(url).protocol);
  } catch {
    return false;
  }
}
