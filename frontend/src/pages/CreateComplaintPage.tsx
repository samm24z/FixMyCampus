import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Send, TicketPlus } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CATEGORY_OPTIONS, getApiError, ticketsApi, type TicketPriority } from '@/lib/api';

export const CreateComplaintPage: React.FC = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({ title: '', description: '', category: CATEGORY_OPTIONS[0], location: '', priority: 'MEDIUM' as TicketPriority });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateField(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const response = await ticketsApi.create(form);
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
          <CardTitle className="flex items-center gap-2"><TicketPlus className="h-5 w-5 text-primary" /> Create Complaint</CardTitle>
          <CardDescription>Submit a campus issue for review. AI analysis pending.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-5" onSubmit={handleSubmit}>
            {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
            <div className="space-y-2">
              <label htmlFor="title" className="text-sm font-medium">Title</label>
              <input id="title" required minLength={5} value={form.title} onChange={(event) => updateField('title', event.target.value)} className="w-full rounded-lg border bg-background px-3 py-2 text-sm" placeholder="Briefly describe the issue" />
            </div>
            <div className="space-y-2">
              <label htmlFor="description" className="text-sm font-medium">Description</label>
              <textarea id="description" required minLength={10} rows={6} value={form.description} onChange={(event) => updateField('description', event.target.value)} className="w-full rounded-lg border bg-background px-3 py-2 text-sm" placeholder="Describe what happened and how it affects campus users" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="category" className="text-sm font-medium">Category</label>
                <select id="category" value={form.category} onChange={(event) => updateField('category', event.target.value)} className="w-full rounded-lg border bg-background px-3 py-2 text-sm">
                  {CATEGORY_OPTIONS.map((category) => <option key={category}>{category}</option>)}
                </select>
              </div>
              <div className="space-y-2">
                <label htmlFor="priority" className="text-sm font-medium">Priority</label>
                <select id="priority" value={form.priority} onChange={(event) => updateField('priority', event.target.value)} className="w-full rounded-lg border bg-background px-3 py-2 text-sm">
                  {(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as TicketPriority[]).map((priority) => <option key={priority}>{priority}</option>)}
                </select>
              </div>
            </div>
            <div className="space-y-2">
              <label htmlFor="location" className="text-sm font-medium">Location</label>
              <input id="location" required minLength={2} value={form.location} onChange={(event) => updateField('location', event.target.value)} className="w-full rounded-lg border bg-background px-3 py-2 text-sm" placeholder="Building, room, or campus area" />
            </div>
            <Button type="submit" className="gap-2" disabled={isSubmitting}><Send className="h-4 w-4" /> {isSubmitting ? 'Submitting...' : 'Submit Complaint'}</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};
