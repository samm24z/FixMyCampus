import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Layers,
  Users,
  MapPin,
  ArrowUpRight,
  GitMerge,
  RotateCcw,
  Sparkles,
  CheckCircle2,
  Clock,
  Building,
  AlertCircle,
  HelpCircle,
  XCircle,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  getApiError,
  ticketsApi,
  type DuplicateClusterItem,
} from '@/lib/api';

export const DuplicateClustersView: React.FC = () => {
  const [clusters, setClusters] = useState<DuplicateClusterItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [manualTicketRefs, setManualTicketRefs] = useState<Record<string, string>>({});
  const [processingCluster, setProcessingCluster] = useState<string | null>(null);

  const loadClusters = async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await ticketsApi.clusters();
      setClusters(response.data);
    } catch (err) {
      setError(getApiError(err, 'Failed to load duplicate grievance clusters.'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadClusters();
  }, []);

  const handleMergeCandidate = async (primaryRef: string, candidateRef: string) => {
    setProcessingCluster(primaryRef);
    setActionMessage('');
    try {
      await ticketsApi.merge(primaryRef, [candidateRef]);
      setActionMessage(`Successfully merged ticket ${candidateRef} into master issue ${primaryRef}!`);
      await loadClusters();
    } catch (err) {
      setError(getApiError(err, 'Failed to merge ticket.'));
    } finally {
      setProcessingCluster(null);
    }
  };

  const handleDismissCandidate = async (primaryRef: string, candidateRef: string) => {
    setProcessingCluster(primaryRef);
    setActionMessage('');
    try {
      await ticketsApi.dismissDuplicate(primaryRef, candidateRef);
      setActionMessage(`Marked ticket ${candidateRef} as not a duplicate. Dismissed from master issue ${primaryRef}.`);
      await loadClusters();
    } catch (err) {
      setError(getApiError(err, 'Failed to dismiss duplicate suggestion.'));
    } finally {
      setProcessingCluster(null);
    }
  };

  const handleUnmerge = async (primaryRef: string, duplicateRef: string) => {
    if (!window.confirm(`Unmerge ticket ${duplicateRef} from master issue ${primaryRef}?`)) return;
    setProcessingCluster(primaryRef);
    setActionMessage('');
    try {
      await ticketsApi.unmerge(primaryRef, duplicateRef);
      setActionMessage(`Ticket ${duplicateRef} unmerged and reopened for independent tracking.`);
      await loadClusters();
    } catch (err) {
      setError(getApiError(err, 'Failed to unmerge ticket.'));
    } finally {
      setProcessingCluster(null);
    }
  };

  const handleManualMerge = async (primaryRef: string) => {
    const refToMerge = manualTicketRefs[primaryRef]?.trim();
    if (!refToMerge) return;
    setProcessingCluster(primaryRef);
    setActionMessage('');
    try {
      await ticketsApi.merge(primaryRef, [refToMerge]);
      setActionMessage(`Merged ${refToMerge} into master issue ${primaryRef}!`);
      setManualTicketRefs((prev) => ({ ...prev, [primaryRef]: '' }));
      await loadClusters();
    } catch (err) {
      setError(getApiError(err, 'Failed to merge ticket.'));
    } finally {
      setProcessingCluster(null);
    }
  };

  const totalDuplicatesMerged = clusters.reduce((acc, c) => acc + c.merged_tickets.length, 0);
  const totalBlocksAffected = new Set(clusters.flatMap((c) => c.locations)).size;

  return (
    <Card className="border-primary/20 shadow-sm">
      <CardHeader className="border-b bg-muted/20 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle className="text-xl flex items-center gap-2">
              <Layers className="h-5 w-5 text-primary" /> Multi-Student Duplicate Grievances
            </CardTitle>
            <CardDescription className="mt-1">
              Consolidated view of repeated campus grievances raised by multiple students across blocks.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={loadClusters} disabled={isLoading} className="self-start sm:self-auto">
            Refresh Clusters
          </Button>
        </div>

        {/* Aggregate Insight Badges */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
          <div className="rounded-lg border bg-background p-3 flex items-center gap-3">
            <div className="p-2 rounded-md bg-primary/10 text-primary">
              <Layers className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Consolidated Clusters</p>
              <p className="text-lg font-bold">{clusters.length} Issues</p>
            </div>
          </div>
          <div className="rounded-lg border bg-background p-3 flex items-center gap-3">
            <div className="p-2 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Redundant Reports Merged</p>
              <p className="text-lg font-bold">{totalDuplicatesMerged} Complaints</p>
            </div>
          </div>
          <div className="rounded-lg border bg-background p-3 flex items-center gap-3">
            <div className="p-2 rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400">
              <Building className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Campus Blocks Impacted</p>
              <p className="text-lg font-bold">{totalBlocksAffected} Locations</p>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-5 space-y-6">
        {actionMessage && (
          <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-300 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{actionMessage}</span>
          </div>
        )}

        {error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {isLoading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Analyzing campus complaint clusters...</p>
        ) : clusters.length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground border rounded-lg border-dashed">
            <Layers className="mx-auto mb-2 h-8 w-8 text-muted-foreground/50" />
            <p>No multi-student duplicate issues currently detected.</p>
          </div>
        ) : (
          <div className="space-y-5">
            {clusters.map((cluster) => {
              const primaryRef = cluster.primary_ticket_number;
              return (
                <div
                  key={cluster.primary_ticket_id}
                  className="rounded-xl border bg-card p-5 shadow-sm hover:border-primary/40 transition-all space-y-4"
                >
                  {/* Master Header */}
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2.5 py-0.5 rounded">
                          {cluster.primary_ticket_number} (Master)
                        </span>
                        <Badge variant="outline">{cluster.category}</Badge>
                        <Badge variant={cluster.priority === 'CRITICAL' ? 'destructive' : 'secondary'}>
                          {cluster.priority}
                        </Badge>
                        <Badge variant="success">{cluster.status}</Badge>
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          <Clock className="h-3 w-3" /> {new Date(cluster.created_at).toLocaleDateString()}
                        </span>
                      </div>

                      <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                        {cluster.title}
                      </h3>
                      <p className="text-xs text-muted-foreground line-clamp-2">{cluster.description}</p>
                    </div>

                    <Link to={`/tickets/${cluster.primary_ticket_number}`}>
                      <Button variant="outline" size="sm" className="gap-1.5 shrink-0">
                        View Master Issue <ArrowUpRight className="h-3.5 w-3.5" />
                      </Button>
                    </Link>
                  </div>

                  {/* Highlights: Students Count & Blocks Involved */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 rounded-lg bg-muted/30 p-3.5 border border-muted">
                    <div>
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-primary mb-1.5">
                        <Users className="h-4 w-4" />
                        <span>Raised by {cluster.student_count} Students:</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {cluster.students.map((name) => (
                          <span
                            key={name}
                            className="text-xs px-2 py-0.5 rounded-full bg-background border font-medium text-foreground flex items-center gap-1"
                          >
                            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                            {name}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground mb-1.5">
                        <MapPin className="h-4 w-4 text-rose-500" />
                        <span>Affected Campus Blocks / Rooms:</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {cluster.locations.map((loc) => (
                          <span
                            key={loc}
                            className="text-xs px-2 py-0.5 rounded bg-background border text-muted-foreground font-mono"
                          >
                            📍 {loc}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Pending Candidates Detected by AI */}
                  {cluster.pending_candidates.length > 0 && (
                    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3.5 space-y-2">
                      <div className="flex items-center gap-2 text-xs font-semibold text-amber-800 dark:text-amber-200">
                        <Sparkles className="h-4 w-4 text-amber-600 dark:text-amber-400 animate-pulse" />
                        <span>AI Duplicate Detection: {cluster.pending_candidates.length} matching grievance pending review</span>
                      </div>
                      <div className="space-y-2">
                        {cluster.pending_candidates.map((candidate) => (
                          <div
                            key={candidate.ticket_id}
                            className="rounded-md border border-amber-500/20 bg-background/80 p-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                          >
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-bold text-primary">{candidate.ticket_number}</span>
                                <span className="font-semibold">{candidate.title}</span>
                                <Badge variant="warning" className="text-[10px]">
                                  {Math.round(candidate.similarity_score * 100)}% Match
                                </Badge>
                              </div>
                              <p className="text-muted-foreground mt-0.5">
                                Reported by <span className="font-medium text-foreground">{candidate.student_name}</span> at{' '}
                                <span className="font-medium text-foreground">{candidate.location}</span>
                              </p>
                            </div>
                            <div className="flex flex-wrap items-center gap-2 shrink-0">
                              <Button
                                size="sm"
                                className="gap-1.5 bg-amber-600 hover:bg-amber-700 text-white font-medium"
                                disabled={processingCluster === primaryRef}
                                onClick={() => handleMergeCandidate(primaryRef, candidate.ticket_number)}
                              >
                                <GitMerge className="h-3.5 w-3.5" /> Merge into Master Issue
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                className="gap-1.5 border-rose-300 text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:border-rose-900/60 dark:text-rose-400 dark:hover:bg-rose-950/30 font-medium"
                                disabled={processingCluster === primaryRef}
                                onClick={() => handleDismissCandidate(primaryRef, candidate.ticket_number)}
                              >
                                <XCircle className="h-3.5 w-3.5" /> Not a Duplicate
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Merged Duplicate Reports Table / Cards */}
                  {cluster.merged_tickets.length > 0 ? (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-muted-foreground">
                        Merged Duplicate Reports ({cluster.merged_tickets.length}):
                      </p>
                      <div className="grid gap-2">
                        {cluster.merged_tickets.map((dup) => (
                          <div
                            key={dup.ticket_id}
                            className="rounded-lg border bg-muted/15 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                          >
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <Link
                                  to={`/tickets/${dup.ticket_number}`}
                                  className="font-mono font-bold text-primary hover:underline"
                                >
                                  {dup.ticket_number}
                                </Link>
                                <span className="font-medium text-foreground">{dup.title}</span>
                                <Badge variant="outline" className="text-[10px]">
                                  {Math.round(dup.similarity_score * 100)}% Match
                                </Badge>
                              </div>
                              <p className="text-muted-foreground text-[11px] line-clamp-1 italic">
                                "{dup.description}"
                              </p>
                              <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                                <span>Reporter: <strong className="text-foreground">{dup.student_name}</strong> ({dup.student_email})</span>
                                <span>Location: <strong className="text-foreground">{dup.location}</strong></span>
                                <span>{new Date(dup.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-xs text-muted-foreground hover:text-destructive gap-1 self-start sm:self-center shrink-0"
                              disabled={processingCluster === primaryRef}
                              onClick={() => handleUnmerge(primaryRef, dup.ticket_number)}
                            >
                              <RotateCcw className="h-3 w-3" /> Unmerge
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {/* Manual Merge Input */}
                  <div className="flex items-center gap-2 pt-2 border-t">
                    <input
                      type="text"
                      placeholder="Enter ticket ID to merge into this issue (e.g. TICK-2026-0005)..."
                      value={manualTicketRefs[primaryRef] || ''}
                      onChange={(e) =>
                        setManualTicketRefs((prev) => ({ ...prev, [primaryRef]: e.target.value }))
                      }
                      className="flex-1 rounded-md border bg-background px-3 py-1.5 text-xs focus:ring-1 focus:ring-primary focus:outline-none"
                    />
                    <Button
                      size="sm"
                      variant="secondary"
                      className="gap-1 text-xs"
                      disabled={!manualTicketRefs[primaryRef]?.trim() || processingCluster === primaryRef}
                      onClick={() => handleManualMerge(primaryRef)}
                    >
                      <GitMerge className="h-3 w-3" /> Merge
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
