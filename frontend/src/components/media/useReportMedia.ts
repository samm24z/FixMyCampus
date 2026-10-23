import axios from 'axios';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getApiError, uploadsApi } from '@/lib/api';
import { readPhotoMeta, shrinkPhoto, validatePhotoFile, type PhotoMeta } from '@/lib/media';

export interface MediaItem {
  localId: string;
  name: string;
  /** Object URL of the shrunk photo (empty while it is still being prepared). */
  previewUrl: string;
  /** Upload progress, 0 to 1. */
  progress: number;
  status: 'preparing' | 'uploading' | 'ready' | 'error';
  error?: string;
  attachmentId?: string;
  capturedAt: Date | null;
  gps: PhotoMeta['gps'];
}

let counter = 0;
const newLocalId = () => `photo-${Date.now()}-${counter++}`;

/**
 * The photos on a report, from picking a file to a finished draft upload on the server.
 * Photo GPS stays in the browser: only the time of capture is sent when an upload completes.
 */
export function useReportMedia() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [notice, setNotice] = useState('');
  const itemsRef = useRef<MediaItem[]>([]);
  const removed = useRef(new Set<string>());

  const commit = useCallback((next: MediaItem[]) => {
    itemsRef.current = next;
    setItems(next);
  }, []);

  const patch = useCallback((localId: string, changes: Partial<MediaItem>) => {
    commit(itemsRef.current.map((item) => (item.localId === localId ? { ...item, ...changes } : item)));
  }, [commit]);

  useEffect(() => () => {
    for (const item of itemsRef.current) if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  }, []);

  const process = useCallback(async (localId: string, file: File) => {
    let attachmentId: string | undefined;
    const gone = () => removed.current.has(localId);
    try {
      const meta = await readPhotoMeta(file);
      if (gone()) return;
      patch(localId, { capturedAt: meta.capturedAt, gps: meta.gps });
      const small = await shrinkPhoto(file);
      if (gone()) return;
      patch(localId, { previewUrl: URL.createObjectURL(small), status: 'uploading', progress: 0 });
      const { data: ticket } = await uploadsApi.create({ kind: 'image', content_type: small.type, size: small.size, file_name: small.name });
      attachmentId = ticket.upload_id;
      await uploadsApi.send(ticket, small, (fraction) => { if (!gone()) patch(localId, { progress: fraction }); });
      await uploadsApi.complete(ticket.upload_id, { captured_at: meta.capturedAt ? meta.capturedAt.toISOString() : null });
      if (gone()) {
        uploadsApi.remove(ticket.upload_id).catch(() => undefined);
        return;
      }
      patch(localId, { status: 'ready', progress: 1, attachmentId: ticket.upload_id });
    } catch (error) {
      if (attachmentId) uploadsApi.remove(attachmentId).catch(() => undefined);
      if (gone()) return;
      const fallback = "Couldn't upload this photo. Please try again.";
      const message = axios.isAxiosError(error) ? getApiError(error, fallback) : error instanceof Error ? error.message : fallback;
      patch(localId, { status: 'error', error: message });
    }
  }, [patch]);

  const add = useCallback((files: File[] | FileList) => {
    setNotice('');
    const list = Array.from(files);
    // Photos that failed don't use up a slot.
    let count = itemsRef.current.filter((item) => item.status !== 'error').length;
    const accepted: { item: MediaItem; file: File }[] = [];
    let firstProblem = '';
    for (const file of list) {
      const problem = validatePhotoFile(file, count);
      if (problem) {
        firstProblem = firstProblem || problem;
        continue;
      }
      count += 1;
      accepted.push({
        file,
        item: { localId: newLocalId(), name: file.name, previewUrl: '', progress: 0, status: 'preparing', capturedAt: null, gps: null },
      });
    }
    if (firstProblem) setNotice(firstProblem);
    if (accepted.length === 0) return;
    commit([...itemsRef.current, ...accepted.map((entry) => entry.item)]);
    for (const { item, file } of accepted) void process(item.localId, file);
  }, [commit, process]);

  const remove = useCallback((localId: string) => {
    const item = itemsRef.current.find((entry) => entry.localId === localId);
    if (!item) return;
    removed.current.add(localId);
    if (item.attachmentId) uploadsApi.remove(item.attachmentId).catch(() => undefined);
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    commit(itemsRef.current.filter((entry) => entry.localId !== localId));
  }, [commit]);

  /** Forget photos the server has already deleted (for example after it rejected them). */
  const drop = useCallback((attachmentIds: string[]) => {
    const ids = new Set(attachmentIds);
    for (const item of itemsRef.current) {
      if (item.attachmentId && ids.has(item.attachmentId)) {
        removed.current.add(item.localId);
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      }
    }
    commit(itemsRef.current.filter((item) => !(item.attachmentId && ids.has(item.attachmentId))));
  }, [commit]);

  /** Clear the list without deleting anything on the server: the photos are now part of a ticket. */
  const reset = useCallback(() => {
    for (const item of itemsRef.current) {
      removed.current.add(item.localId);
      if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    }
    setNotice('');
    commit([]);
  }, [commit]);

  const readyIds = useMemo(() => items.filter((i) => i.status === 'ready' && i.attachmentId).map((i) => i.attachmentId as string), [items]);
  const busy = items.some((i) => i.status === 'preparing' || i.status === 'uploading');
  const captures = useMemo(() => items.filter((i) => i.status !== 'error').map((i) => i.capturedAt), [items]);
  const firstPhotoGps = useMemo(() => items.find((i) => i.status !== 'error' && i.gps)?.gps ?? null, [items]);
  const slotsUsed = items.filter((i) => i.status !== 'error').length;

  return { items, notice, readyIds, busy, captures, firstPhotoGps, slotsUsed, add, remove, drop, reset };
}

export type ReportMedia = ReturnType<typeof useReportMedia>;
