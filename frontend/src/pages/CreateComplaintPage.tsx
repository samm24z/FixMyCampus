import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Send, TicketPlus } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LocationPicker } from '@/components/LocationPicker';
import { MediaSection } from '@/components/media/MediaSection';
import type { ReportPoint } from '@/components/media/LocationExtras';
import { useReportMedia } from '@/components/media/useReportMedia';
import { CATEGORY_OPTIONS, getApiError, ticketsApi, type MediaDraft, type TicketPriority } from '@/lib/api';
import { PRIORITIES, priorityLabel } from '@/lib/tickets';

export const CreateComplaintPage: React.FC = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({ title: '', description: '', category: CATEGORY_OPTIONS[0], location: '', priority: 'MEDIUM' as TicketPriority });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const media = useReportMedia();
  const [point, setPoint] = useState<ReportPoint | null>(null);
  const [observedAt, setObservedAt] = useState<Date | null>(null);
  // LocationPicker only reads `initial` when it mounts, so a new place from the photos remounts it.
  const [picker, setPicker] = useState({ key: 0, initial: '' });

  function updateField(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function applyDraft(draft: MediaDraft) {
    setForm((current) => ({
      ...current,
      title: draft.title,
      description: draft.description,
      category: CATEGORY_OPTIONS.includes(draft.category) ? draft.category : current.category,
      priority: PRIORITIES.includes(draft.priority) ? draft.priority : current.priority,
      location: current.location || draft.location_hint || '',
    }));
    if (!form.location && draft.location_hint) setPicker((current) => ({ key: current.key + 1, initial: draft.location_hint as string }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const response = await ticketsApi.create({
        ...form,
        attachment_ids: media.readyIds,
        observed_at: observedAt ? observedAt.toISOString() : null,
        report_lat: point?.lat ?? null,
        report_lng: point?.lng ?? null,
        report_accuracy_m: point?.accuracy_m ?? null,
        location_source: point?.source ?? null,
      });
      navigate(`/tickets/${response.data.ticket_number}`, { state: { created: true } });
    } catch (submissionError) {
      setError(getApiError(submissionError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/tickets')}>
        <ArrowLeft className="h-4 w-4" /> Back to Tickets
      </Button>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><TicketPlus className="h-5 w-5 text-primary" /> Report a Problem</CardTitle>
          <CardDescription>Tell us what's wrong and where. We'll pass it to the right team.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-5" onSubmit={handleSubmit}>
            {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
            <div className="space-y-2">
              <label htmlFor="title" className="text-sm font-medium">Title</label>
              <input id="title" required minLength={5} value={form.title} onChange={(event) => updateField('title', event.target.value)} className="w-full rounded-lg border bg-background px-3 py-2 text-sm" placeholder="For example: Projector not working in Room 204" />
            </div>
            <div className="space-y-2">
              <label htmlFor="description" className="text-sm font-medium">Description</label>
              <textarea id="description" required minLength={10} rows={6} value={form.description} onChange={(event) => updateField('description', event.target.value)} className="w-full rounded-lg border bg-background px-3 py-2 text-sm" placeholder="What's wrong, since when, and who is affected?" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="category" className="text-sm font-medium">Category</label>
                <select id="category" value={form.category} onChange={(event) => updateField('category', event.target.value)} className="w-full rounded-lg border bg-background px-3 py-2 text-sm">
                  {CATEGORY_OPTIONS.map((category) => <option key={category}>{category}</option>)}
                </select>
              </div>
              <div className="space-y-2">
                <label htmlFor="priority" className="text-sm font-medium">How urgent is it?</label>
                <select id="priority" value={form.priority} onChange={(event) => updateField('priority', event.target.value)} className="w-full rounded-lg border bg-background px-3 py-2 text-sm">
                  {PRIORITIES.map((priority) => <option key={priority} value={priority}>{priorityLabel(priority)}</option>)}
                </select>
              </div>
            </div>
            <LocationPicker key={picker.key} initial={picker.initial} onChange={(location) => updateField('location', location)} />
            <MediaSection media={media} description={form.description} location={form.location} onDraft={applyDraft} onPoint={setPoint} onObservedAt={setObservedAt} />
            <Button type="submit" className="gap-2" disabled={isSubmitting || media.busy}><Send className="h-4 w-4" /> {isSubmitting ? 'Sending...' : media.busy ? 'Waiting for photos...' : 'Send Report'}</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};
