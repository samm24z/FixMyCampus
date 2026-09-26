import React, { useState } from 'react';
import { BotMessageSquare, Send, BookOpen, Sparkles, ExternalLink } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export const AssistantPage: React.FC = () => {
  const [messages, setMessages] = useState([
    {
      sender: 'bot',
      text: 'Hello! I am the FixMyCampus AI Policy Assistant. Ask me anything regarding campus grievance resolution timelines, student housing SOPs, lab equipment protocols, or escalation policies.',
      citations: [],
    },
    {
      sender: 'user',
      text: 'What is the maximum turnaround time for emergency electrical repairs in student hostels?',
      citations: [],
    },
    {
      sender: 'bot',
      text: 'According to the Campus Hostel Operations Manual (Section 3.4), all emergency electrical complaints (sparks, outages, exposed wiring) are classified as CRITICAL priority and must be inspected and mitigated within 4 hours of submission.',
      citations: [
        {
          title: 'Campus Hostel Operations & Safety Manual 2026',
          page: 28,
          section: '3.4 Emergency Hazard Protocols',
        },
      ],
    },
  ]);

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold tracking-tight">Campus Policy Assistant</h1>
            <Badge variant="outline" className="text-xs bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 gap-1">
              <Sparkles className="h-3 w-3" /> Grounded RAG
            </Badge>
          </div>
          <p className="text-muted-foreground text-sm mt-1">
            Answers queries exclusively from approved university handbooks with verifiable citations.
          </p>
        </div>
      </div>

      <Card className="flex flex-col h-[560px]">
        <CardHeader className="py-3 px-5 border-b bg-muted/20">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <BookOpen className="h-4 w-4 text-primary" /> Verified Knowledge Base: 12 Approved Campus Documents
            </span>
            <Badge variant="success" className="text-[10px]">Zero-Hallucination Guardrail Active</Badge>
          </div>
        </CardHeader>

        <CardContent className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex flex-col ${
                m.sender === 'user' ? 'items-end' : 'items-start'
              }`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                  m.sender === 'user'
                    ? 'bg-primary text-primary-foreground rounded-br-none'
                    : 'bg-muted/70 text-foreground rounded-bl-none border'
                }`}
              >
                <p className="leading-relaxed">{m.text}</p>
              </div>

              {m.citations && m.citations.length > 0 && (
                <div className="mt-2 max-w-[85%] space-y-1">
                  {m.citations.map((c, ci) => (
                    <div
                      key={ci}
                      className="p-2 rounded-md bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-500/20 text-[11px] text-muted-foreground flex items-center justify-between gap-2"
                    >
                      <span className="font-medium text-indigo-600 dark:text-indigo-400">
                        Citation: {c.title} &bull; Page {c.page} ({c.section})
                      </span>
                      <ExternalLink className="h-3 w-3 shrink-0 text-indigo-500" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </CardContent>

        <CardFooter className="p-3 border-t bg-background">
          <div className="flex w-full items-center gap-2">
            <input
              type="text"
              placeholder="Ask a campus policy question (Full LangChain RAG pipeline active in Phase 7)..."
              className="flex-1 px-4 py-2.5 text-sm border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              disabled
            />
            <Button size="icon" disabled className="shrink-0">
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
};
