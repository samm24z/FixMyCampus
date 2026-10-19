import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Clock, ListChecks, Mail, Star, TicketPlus, Users } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

const features = [
  { icon: TicketPlus, title: 'Report in a minute', desc: "Say what's wrong and where. You get a ticket number to keep track of it." },
  { icon: Users, title: 'Sent to the right team', desc: 'A coordinator passes your report to the department that can fix it.' },
  { icon: Clock, title: 'Follow every step', desc: 'See when your ticket is picked up, worked on and fixed, with notes from staff.' },
  { icon: CheckCircle2, title: "You say when it's fixed", desc: 'Confirm the fix, or reopen the ticket if the problem comes back.' },
  { icon: Star, title: 'Rate the fix', desc: 'Give 1 to 5 stars so the campus knows what is working well.' },
  { icon: Mail, title: 'Your college account', desc: 'Sign in with your MVSR college email address.' },
];

const steps = [
  { name: 'New', desc: 'You report the problem' },
  { name: 'Under review', desc: 'A coordinator checks it' },
  { name: 'Assigned', desc: 'A staff member gets the job' },
  { name: 'In progress', desc: 'Work has started' },
  { name: 'Resolved', desc: 'Staff say it is fixed' },
  { name: 'Closed', desc: 'You confirm, or it closes after a few days' },
];

export const HomePage: React.FC = () => {
  return (
    <div className="space-y-12 pb-8">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-b from-indigo-900/10 via-background to-background p-8 md:p-14 border shadow-sm">
        <div className="flex flex-col items-center text-center max-w-3xl mx-auto space-y-6">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight">
            Something broken on campus? <br />
            <span className="gradient-text">Report it here.</span>
          </h1>

          <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
            Tell us about broken equipment, Wi-Fi trouble, water leaks, cleanliness or anything else on campus,
            and follow your report until it's fixed.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <Link to="/tickets/new">
              <Button size="lg" className="gap-2 text-base font-semibold shadow-lg shadow-indigo-500/20">
                Report a Problem <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link to="/tickets">
              <Button size="lg" variant="outline" className="gap-2 text-base font-semibold">
                <ListChecks className="h-4 w-4 text-indigo-500" />
                View My Tickets
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-2xl md:text-3xl font-bold tracking-tight">How it helps</h2>
          <p className="text-sm text-muted-foreground">From the moment you report a problem until it's sorted.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <Card key={f.title} className="hover:border-primary/40 hover:shadow-md transition-all">
                <CardHeader>
                  <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary mb-2">
                    <Icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-lg font-bold">{f.title}</CardTitle>
                  <CardDescription className="text-sm leading-relaxed">{f.desc}</CardDescription>
                </CardHeader>
              </Card>
            );
          })}
        </div>
      </section>

      <section className="rounded-2xl border bg-card p-6 md:p-8 space-y-6">
        <h3 className="text-xl font-bold flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          What happens after you report a problem
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 text-center text-xs">
          {steps.map((step, idx) => (
            <div key={step.name} className="p-3 rounded-lg bg-muted/60 border flex flex-col items-center gap-1">
              <span className="text-muted-foreground text-[10px]">Step {idx + 1}</span>
              <span className="text-primary font-bold text-sm">{step.name}</span>
              <span className="text-muted-foreground">{step.desc}</span>
            </div>
          ))}
        </div>
        <p className="text-sm text-muted-foreground">Not fixed after all? You can reopen your ticket at any time.</p>
      </section>
    </div>
  );
};
