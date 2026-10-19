import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { BotMessageSquare, ExternalLink, Map as MapIcon, Mail, Phone, Send, TicketPlus } from 'lucide-react';
import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LocationPicker } from '@/components/LocationPicker';
import { CATEGORY_OPTIONS, assistantApi, getApiError, ticketsApi, type AssistantAction, type TicketPriority } from '@/lib/api';
import {
  STARTER_QUESTIONS, historyForRequest, isAppLink, isWebLink, mailHref, runTicketAction, telHref,
  ticketActionButton, ticketActionDone, ticketActionTitle, type ChatMessage, type TicketAction,
} from '@/lib/assistant';
import { PRIORITIES, priorityLabel } from '@/lib/tickets';

const FIELD = 'w-full rounded-lg border bg-background px-3 py-2 text-sm';
const CARD = 'rounded-xl border bg-background p-4 text-sm space-y-3';
const ERROR_BOX = 'rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive';

function ReportCard({ action }: { action: Extract<AssistantAction, { type: 'report_problem' }> }) {
  const [form, setForm] = useState({
    title: action.title, description: action.description, category: action.category, location: action.location, priority: action.priority as TicketPriority,
  });
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [ticketNumber, setTicketNumber] = useState('');

  const update = (field: keyof typeof form, value: string) => setForm((current) => ({ ...current, [field]: value }));
  const ready = form.title.trim().length >= 5 && form.description.trim().length >= 10 && form.location.trim().length >= 2;

  async function send() {
    setError('');
    setSending(true);
    try {
      const response = await ticketsApi.create({ ...form, title: form.title.trim(), description: form.description.trim(), location: form.location.trim() });
      setTicketNumber(response.data.ticket_number);
    } catch (requestError) {
      setError(getApiError(requestError));
    } finally {
      setSending(false);
    }
  }

  if (ticketNumber) {
    return (
      <div className={CARD}>
        <p className="font-medium">Your report has been sent.</p>
        <Link to={`/tickets/${ticketNumber}`} className="text-primary underline-offset-2 hover:underline">View ticket {ticketNumber}</Link>
      </div>
    );
  }
  return (
    <div className={CARD}>
      <p className="flex items-center gap-1.5 font-medium"><TicketPlus className="h-4 w-4 text-primary" /> Report a problem</p>
      <p className="text-xs text-muted-foreground">Check the details, then send it. Nothing is sent until you click.</p>
      {error && <div className={ERROR_BOX}>{error}</div>}
      <input aria-label="Title" className={FIELD} value={form.title} onChange={(event) => update('title', event.target.value)} />
      <textarea aria-label="Description" rows={3} className={FIELD} value={form.description} onChange={(event) => update('description', event.target.value)} />
      <div className="grid gap-2 sm:grid-cols-2">
        <select aria-label="Category" className={FIELD} value={form.category} onChange={(event) => update('category', event.target.value)}>
          {CATEGORY_OPTIONS.map((category) => <option key={category}>{category}</option>)}
        </select>
        <select aria-label="How urgent is it?" className={FIELD} value={form.priority} onChange={(event) => update('priority', event.target.value)}>
          {PRIORITIES.map((priority) => <option key={priority} value={priority}>{priorityLabel(priority)}</option>)}
        </select>
      </div>
      <LocationPicker initial={action.location} onChange={(location) => update('location', location)} />
      <Button size="sm" className="gap-2" disabled={sending || !ready} onClick={send}>
        <Send className="h-4 w-4" /> {sending ? 'Sending...' : 'Send report'}
      </Button>
    </div>
  );
}

function TicketActionCard({ action }: { action: TicketAction }) {
  const [state, setState] = useState<'idle' | 'working' | 'done'>('idle');
  const [error, setError] = useState('');

  async function run() {
    setError('');
    setState('working');
    try {
      await runTicketAction(action);
      setState('done');
    } catch (requestError) {
      setError(getApiError(requestError));
      setState('idle');
    }
  }

  return (
    <div className={CARD}>
      <p className="font-medium">{ticketActionTitle(action.type)}</p>
      <p className="text-muted-foreground">
        <Link to={`/tickets/${action.ticket_number}`} className="text-primary underline-offset-2 hover:underline">{action.ticket_number}</Link> · {action.ticket_title}
      </p>
      {action.type === 'add_comment' && <p className="rounded-md bg-muted/60 px-3 py-2">{action.text}</p>}
      {error && <div className={ERROR_BOX}>{error}</div>}
      {state === 'done' ? (
        <p className="font-medium text-emerald-700 dark:text-emerald-400">{ticketActionDone(action.type)}</p>
      ) : (
        <Button size="sm" variant={action.type === 'cancel_ticket' ? 'outline' : 'default'} disabled={state === 'working'} onClick={run}>
          {state === 'working' ? 'Working...' : ticketActionButton(action.type)}
        </Button>
      )}
    </div>
  );
}

function ActionCard({ action }: { action: AssistantAction }) {
  switch (action.type) {
    case 'report_problem':
      return <ReportCard action={action} />;
    case 'contact':
      return (
        <div className={CARD}>
          <p className="font-medium">{action.label}</p>
          <div className="flex flex-wrap gap-3">
            {action.email && <a href={mailHref(action.email)} className="flex items-center gap-1.5 text-primary hover:underline"><Mail className="h-4 w-4" /> {action.email}</a>}
            {action.phone && <a href={telHref(action.phone)} className="flex items-center gap-1.5 text-primary hover:underline"><Phone className="h-4 w-4" /> {action.phone}</a>}
          </div>
        </div>
      );
    case 'open_link':
      if (isAppLink(action.url)) {
        return (
          <Link to={action.url} className={`${CARD} flex items-center gap-2 font-medium text-primary hover:underline`}>
            <MapIcon className="h-4 w-4" /> {action.label}
          </Link>
        );
      }
      return isWebLink(action.url) ? (
        <a href={action.url} target="_blank" rel="noreferrer" className={`${CARD} flex items-center gap-2 font-medium text-primary hover:underline`}>
          <ExternalLink className="h-4 w-4" /> {action.label}
        </a>
      ) : null;
    default:
      return <TicketActionCard action={action} />;
  }
}

function Bubble({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return <div className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-none bg-primary px-4 py-2.5 text-sm text-primary-foreground">{message.text}</div>;
  }
  const reply = message.reply;
  return (
    <div className="max-w-[90%] space-y-2">
      <div className={`whitespace-pre-wrap rounded-2xl rounded-bl-none border px-4 py-3 text-sm leading-relaxed ${message.failed ? 'border-destructive/30 bg-destructive/10 text-destructive' : 'bg-muted/70'}`}>
        {message.text}
      </div>
      {reply && reply.sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {reply.sources.map((source) => {
            const chip = 'inline-flex max-w-[16rem] items-center gap-1 truncate rounded-full border bg-background px-2.5 py-0.5 text-xs text-primary hover:bg-muted';
            const content = <><span className="font-semibold">{source.n}</span> <span className="truncate">{source.title}</span></>;
            return isAppLink(source.url)
              ? <Link key={source.n} to={source.url} title={source.section} className={chip}>{content}</Link>
              : <a key={source.n} href={source.url} target="_blank" rel="noreferrer" title={source.section} className={chip}>{content}</a>;
          })}
        </div>
      )}
      {reply?.actions.map((action, index) => <ActionCard key={index} action={action} />)}
    </div>
  );
}

export const AssistantPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [messages, busy]);

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    const history = historyForRequest(messages);
    setMessages((current) => [...current, { id: nextId.current++, role: 'user', text }]);
    setInput('');
    setBusy(true);
    try {
      const { data } = await assistantApi.chat(text, history);
      setMessages((current) => [...current, { id: nextId.current++, role: 'assistant', text: data.answer, reply: { sources: data.sources, actions: data.actions, status: data.status } }]);
    } catch (requestError) {
      setMessages((current) => [...current, { id: nextId.current++, role: 'assistant', text: getApiError(requestError, "Sorry, I couldn't get an answer. Please try again."), failed: true }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Ask a Question</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Ask about the college, check your tickets, or describe a problem and I'll help you report it.
          </p>
        </div>
        <Link to="/campus-guide" className="inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5 text-sm font-medium text-primary hover:bg-muted">
          <MapIcon className="h-4 w-4" /> Campus guide
        </Link>
      </div>

      <Card className="flex flex-col h-[600px]">
        <CardHeader className="py-3 px-5 border-b bg-muted/20">
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <BotMessageSquare className="h-4 w-4 text-primary" /> Campus help
          </span>
        </CardHeader>

        <CardContent className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.length === 0 ? (
            <div className="space-y-4">
              <div className="max-w-[85%] rounded-2xl rounded-bl-none border bg-muted/70 px-4 py-3 text-sm leading-relaxed">
                Hi! What would you like to know? Here are some things you can ask.
              </div>
              <div className="flex flex-wrap gap-2">
                {STARTER_QUESTIONS.map((question) => (
                  <button key={question} type="button" onClick={() => ask(question)} className="rounded-full border bg-background px-3 py-1.5 text-sm hover:bg-muted">
                    {question}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => <Bubble key={message.id} message={message} />)
          )}
          {busy && <p className="text-sm text-muted-foreground">Looking that up...</p>}
          <div ref={bottom} />
        </CardContent>

        <CardFooter className="flex-col items-stretch gap-2 p-3 border-t bg-background">
          <form className="flex w-full items-center gap-2" onSubmit={(event) => { event.preventDefault(); void ask(input); }}>
            <input
              type="text"
              value={input}
              maxLength={1000}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Type your question"
              aria-label="Your question"
              className="flex-1 px-4 py-2.5 text-sm border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <Button type="submit" size="icon" disabled={busy || !input.trim()} className="shrink-0" aria-label="Send">
              <Send className="h-4 w-4" />
            </Button>
          </form>
          <p className="text-xs text-muted-foreground">Answers come from the college website and may be out of date.</p>
        </CardFooter>
      </Card>
    </div>
  );
};
