import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  Sparkles, 
  ArrowRight, 
  CheckCircle2, 
  Layers, 
  CopyCheck, 
  Clock, 
  BotMessageSquare, 
  ShieldCheck, 
  Activity,
  Server
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import axios from 'axios';

export const HomePage: React.FC = () => {
  const [healthData, setHealthData] = useState<{
    status: string;
    version: string;
    environment: string;
    database: string;
  } | null>(null);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
    axios.get(`${apiBase}/health`)
      .then((res) => setHealthData(res.data))
      .catch(() => {
        // Fallback or offline indication
        setHealthData({
          status: 'ok (local client)',
          version: '0.1.0',
          environment: 'development',
          database: 'standby',
        });
      });
  }, []);

  const features = [
    {
      icon: Layers,
      title: 'Automated Category Triage',
      desc: 'Intelligent multi-class text classification categorizing complaints across 8 campus operational departments.',
    },
    {
      icon: CopyCheck,
      title: 'pgvector Deduplication',
      desc: 'Dense 384-dim semantic embeddings identify recurring grievances before redundant work orders are issued.',
    },
    {
      icon: Clock,
      title: 'Urgency & SLA Scoring',
      desc: 'Multi-factor severity scoring calculating dynamic resolution timeframes for emergency and high-impact issues.',
    },
    {
      icon: BotMessageSquare,
      title: 'Policy RAG Assistant',
      desc: 'Retrieval-Augmented Generation answering student inquiries grounded with verified handbook and SOP citations.',
    },
    {
      icon: ShieldCheck,
      title: 'Human-in-the-Loop Overrides',
      desc: 'Full coordinator control to verify, override, and audit every AI suggestion with complete transparency.',
    },
    {
      icon: Activity,
      title: 'End-to-End Audit Logs',
      desc: 'Immutable audit trail capturing all ticket transitions, assignments, and resolution notes.',
    },
  ];

  return (
    <div className="space-y-12 pb-8">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-b from-indigo-900/10 via-background to-background p-8 md:p-14 border shadow-sm">
        <div className="flex flex-col items-center text-center max-w-3xl mx-auto space-y-6">
          <Badge variant="outline" className="px-3 py-1 text-xs gap-1.5 border-indigo-500/30 bg-indigo-500/5 text-indigo-600 dark:text-indigo-400">
            <Sparkles className="h-3.5 w-3.5" />
            Phase 0: Project Foundation Active
          </Badge>

          <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight">
            Campus Grievance Management, <br />
            <span className="gradient-text">Supercharged by AI.</span>
          </h1>

          <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
            Report infrastructure, IT, sanitation, and academic-facility issues. 
            Powered by intelligent classification, semantic deduplication, and grounded policy assistance.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <Link to="/tickets">
              <Button size="lg" className="gap-2 text-base font-semibold shadow-lg shadow-indigo-500/20">
                Explore Tickets <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link to="/assistant">
              <Button size="lg" variant="outline" className="gap-2 text-base font-semibold">
                <BotMessageSquare className="h-4 w-4 text-indigo-500" />
                Ask Policy AI
              </Button>
            </Link>
          </div>

          {/* Backend Connection Status Card */}
          <div className="pt-6 w-full max-w-lg">
            <div className="rounded-xl border bg-card/60 p-4 backdrop-blur flex items-center justify-between text-xs">
              <div className="flex items-center gap-2.5">
                <Server className="h-4 w-4 text-primary" />
                <span className="font-semibold text-foreground">Backend API Status:</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground font-mono">v{healthData?.version || '0.1.0'}</span>
                <Badge variant="success" className="font-medium text-[11px]">
                  {healthData?.status || 'connecting...'}
                </Badge>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-2xl md:text-3xl font-bold tracking-tight">
            Core Architectural Capabilities
          </h2>
          <p className="text-sm text-muted-foreground">
            Built with strict human-in-the-loop governance and fail-soft reliability.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f, i) => {
            const Icon = f.icon;
            return (
              <Card key={i} className="hover:border-primary/40 hover:shadow-md transition-all">
                <CardHeader>
                  <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary mb-2">
                    <Icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-lg font-bold">{f.title}</CardTitle>
                  <CardDescription className="text-sm leading-relaxed">
                    {f.desc}
                  </CardDescription>
                </CardHeader>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Workflow Preview */}
      <section className="rounded-2xl border bg-card p-6 md:p-8 space-y-6">
        <h3 className="text-xl font-bold flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          Standard Complaint Resolution Lifecycle
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-3 text-center text-xs font-semibold">
          {['NEW', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'REOPENED', 'CLOSED'].map((st, idx) => (
            <div key={st} className="p-3 rounded-lg bg-muted/60 border flex flex-col items-center gap-1">
              <span className="text-muted-foreground text-[10px]">Step {idx + 1}</span>
              <span className="text-primary font-mono font-bold">{st}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
