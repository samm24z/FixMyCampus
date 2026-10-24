import axios from 'axios';
import { isAuthError } from '@supabase/supabase-js';
import { File } from 'expo-file-system';
import { API_BASE_URL } from './config';
import { supabase } from './supabase';

// ---------------------------------------------------------------- types

export type Role = 'STUDENT' | 'FACULTY' | 'STAFF' | 'COORDINATOR' | 'ADMIN';
export type TicketStatus = 'NEW' | 'UNDER_REVIEW' | 'ASSIGNED' | 'IN_PROGRESS' | 'RESOLVED' | 'REOPENED' | 'CLOSED';
export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  department_id: string | null;
  phone_number: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface Department {
  id: string;
  name: string;
  code: string;
  description: string | null;
  is_active: boolean;
}

export interface Place {
  key: string;
  name: string;
  kind: 'block' | 'facility';
  description: string;
}

export interface Ticket {
  id: string;
  ticket_number: string;
  title: string;
  description: string;
  category: string;
  location: string;
  priority: TicketPriority;
  status: TicketStatus;
  suggested_category: string | null;
  confirmed_category: string | null;
  confirmed_department_id: string | null;
  ai_confidence: number | null;
  report_count: number;
  parent_ticket_id: string | null;
  /** Only coordinators and admins get this. */
  parent_ticket_number: string | null;
  created_by: string;
  assigned_to: string | null;
  sla_deadline: string | null;
  resolved_at: string | null;
  reopened_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TicketComment {
  id: string;
  user_id: string;
  author_name: string | null;
  author_role: Role | null;
  content: string;
  is_internal: boolean;
  created_at: string;
}

export interface TicketHistoryEntry {
  id: string;
  changed_by: string | null;
  from_status: TicketStatus | null;
  to_status: TicketStatus;
  remarks: string | null;
  created_at: string;
}

/** What the signed-in user may do with a ticket; computed by the backend. */
export interface TicketPermissions {
  allowed_statuses: TicketStatus[];
  can_assign: boolean;
  can_edit_triage: boolean;
  can_comment: boolean;
  can_comment_internal: boolean;
  can_reopen: boolean;
  can_confirm: boolean;
  can_withdraw: boolean;
  can_give_feedback: boolean;
  can_review_suggestions: boolean;
  can_split_group: boolean;
  statuses_requiring_remarks: TicketStatus[];
}

export interface TicketFeedback {
  id: string;
  rating: number;
  comments: string | null;
  created_at: string;
}

/** What the system suggests for a ticket; coordinators and admins only. */
export interface TicketSuggestions {
  status: 'pending' | 'done' | 'failed';
  category: string | null;
  priority: TicketPriority | null;
  department_id: string | null;
  department_name: string | null;
  confidence: number | null;
  reason: string | null;
  source: 'gemini' | 'keywords' | null;
  analyzed_at: string | null;
}

export interface PossibleDuplicate {
  ticket_id: string;
  ticket_number: string;
  title: string;
  similarity_score: number;
  status: TicketStatus;
}

export interface GroupMember {
  ticket_id: string;
  ticket_number: string;
  title: string;
  status: TicketStatus;
  created_at: string;
}

export type LocationSource = 'picker' | 'device' | 'photo';

export interface GeoPoint {
  lat: number;
  lng: number;
  accuracy_m?: number | null;
}

export interface TicketCreateBody {
  title: string;
  description: string;
  category: string;
  location: string;
  priority: TicketPriority;
  /** Ids of the user's own finished uploads (status "ready"), at most 5. */
  attachment_ids?: string[];
  /** When the student noticed the problem (ISO string); defaults to now on the server. */
  observed_at?: string | null;
  report_lat?: number | null;
  report_lng?: number | null;
  report_accuracy_m?: number | null;
  location_source?: LocationSource | null;
}

export type MediaKind = 'image' | 'video';

/** Where the browser sends the file: `upload_method upload_url` with `upload_headers`, raw bytes as body. */
export interface UploadTicket {
  upload_id: string;
  upload_url: string;
  upload_method: string;
  upload_headers: Record<string, string>;
  expires_at: string;
}

export interface UploadCompleteBody {
  captured_at?: string | null;
  gps?: GeoPoint | null;
  duration_s?: number | null;
}

export interface Attachment {
  id: string;
  ticket_id: string | null;
  kind: MediaKind;
  status: 'draft' | 'ready' | 'rejected';
  file_name: string;
  file_size: number;
  mime_type: string;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  captured_at: string | null;
  created_at: string;
}

/** A ticket's photo/video with short-lived signed links. Time and GPS only for the reporter and staff. */
export interface AttachmentView {
  id: string;
  kind: MediaKind;
  file_name: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  created_at: string;
  view_url: string | null;
  thumb_url: string | null;
  captured_at: string | null;
  gps_lat: number | null;
  gps_lng: number | null;
  gps_accuracy_m: number | null;
}

/** Gemini's draft from the photos; the student reviews it before sending. */
export interface MediaDraft {
  title: string;
  description: string;
  category: string;
  priority: TicketPriority;
  location_hint: string | null;
  confidence: number;
  contains_people: boolean;
}

export interface TicketDetail extends Ticket {
  observed_at: string | null;
  location_source: LocationSource | null;
  /** Only for the reporter and for staff, coordinators and admins. */
  report_lat: number | null;
  report_lng: number | null;
  report_accuracy_m: number | null;
  attachment_count: number;
  created_by_name: string;
  assigned_to_name: string | null;
  department_name: string | null;
  comments: TicketComment[];
  history: TicketHistoryEntry[];
  feedback: TicketFeedback | null;
  permissions: TicketPermissions;
  suggestions: TicketSuggestions | null;
  duplicates: PossibleDuplicate[];
  group_members: GroupMember[];
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export type NotificationType =
  | 'TICKET_CREATED'
  | 'STATUS_CHANGED'
  | 'ASSIGNED'
  | 'SLA_WARNING'
  | 'SLA_BREACH'
  | 'FEEDBACK_REQUEST'
  | 'FEEDBACK_RECEIVED'
  | 'COMMENT_ADDED';

export interface AppNotification {
  id: string;
  ticket_id: string | null;
  ticket_number: string | null;
  title: string;
  message: string;
  type: NotificationType;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListParams {
  unread_only?: boolean;
  page?: number;
  page_size?: number;
}

export interface DashboardSummary {
  total_tickets: number;
  open_tickets: number;
  resolved_tickets: number;
  by_status: Partial<Record<TicketStatus, number>>;
  recent_tickets: Ticket[];
}

export interface TicketListParams {
  search?: string;
  status?: TicketStatus | '';
  category?: string;
  priority?: TicketPriority | '';
  department_id?: string;
  assigned_to?: string;
  mine?: boolean;
  open_only?: boolean;
  page?: number;
  page_size?: number;
}

export interface AssistantTurn {
  role: 'user' | 'assistant';
  text: string;
}

export interface AssistantSource {
  n: number;
  title: string;
  url: string;
  section: string;
}

/** Suggestions from the assistant. Nothing happens until the person clicks. */
export type AssistantAction =
  | { type: 'report_problem'; title: string; description: string; category: string; location: string; priority: TicketPriority }
  | { type: 'confirm_fixed' | 'reopen_ticket' | 'cancel_ticket'; ticket_number: string; ticket_title: string }
  | { type: 'add_comment'; ticket_number: string; ticket_title: string; text: string }
  | { type: 'contact'; label: string; email: string | null; phone: string | null }
  | { type: 'open_link'; label: string; url: string };

export interface AssistantReply {
  answer: string;
  sources: AssistantSource[];
  actions: AssistantAction[];
  status: 'answered' | 'not_found' | 'fallback';
}

export const CATEGORY_OPTIONS = [
  'IT / Network',
  'Electrical',
  'Sanitation',
  'Water / Plumbing',
  'Classroom Equipment',
  'Civil Maintenance',
  'Academic Facilities',
  'Other',
];

// --------------------------------------------------------------- client

export { API_BASE_URL };

export const api = axios.create({ baseURL: API_BASE_URL });

// Supabase keeps the session fresh: getSession() refreshes an expired access token on its own.
api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession();
  if (data.session) config.headers.Authorization = `Bearer ${data.session.access_token}`;
  return config;
});

// A 401 despite a session means the account was deactivated or removed: sign out locally so the
// UI returns to the login page instead of showing broken screens.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const { data } = await supabase.auth.getSession();
      if (data.session) await supabase.auth.signOut();
    }
    return Promise.reject(error);
  },
);

// --------------------------------------------------------------- errors

interface ErrorBody {
  error?: { message?: string; details?: unknown };
  detail?: unknown;
}

/** Turn any thrown value into a message that is safe to show the user. */
export function getApiError(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (isAuthError(error)) return error.message; // Supabase Auth messages are written for end users
  if (axios.isAxiosError<ErrorBody>(error)) {
    if (!error.response) return 'Cannot reach the server. Check your connection and try again.';
    const body = error.response.data;
    const details = body?.error?.details;
    if (Array.isArray(details) && details.length > 0) {
      return details
        .map((item: { loc?: unknown[]; msg?: string }) => {
          const field = Array.isArray(item.loc) ? item.loc.filter((part) => part !== 'body').join('.') : '';
          return field ? `${field}: ${item.msg}` : item.msg;
        })
        .join('; ');
    }
    if (body?.error?.message) return body.error.message;
    if (typeof body?.detail === 'string') return body.detail;
  }
  return fallback;
}

// ------------------------------------------------------------ endpoints

export const authApi = {
  /** Profile (role, department) of the signed-in Supabase user; created on first call. */
  me: () => api.get<User>('/auth/me'),
  /** Self-service edits; role, department and email stay admin-only. */
  updateMe: (body: { full_name?: string; phone_number?: string | null }) => api.patch<User>('/auth/me', body),
};

export const departmentsApi = {
  list: () => api.get<Department[]>('/departments'),
};

export const campusApi = {
  places: () => api.get<Place[]>('/campus/places'),
};

export const usersApi = {
  list: (params: { q?: string; role?: Role | ''; is_active?: boolean; page?: number; page_size?: number } = {}) =>
    api.get<Paginated<User>>('/users', { params: clean(params) }),
  staff: (departmentId?: string) => api.get<User[]>('/users/staff', { params: clean({ department_id: departmentId }) }),
  create: (body: { email: string; full_name: string; password: string; role: Role; department_id?: string | null }) =>
    api.post<User>('/users', body),
  update: (id: string, body: { role?: Role; department_id?: string | null; is_active?: boolean }) =>
    api.patch<User>(`/users/${id}`, body),
};

export const uploadsApi = {
  /** Step 1: ask for a signed link and create a draft upload. */
  create: (body: { kind: MediaKind; content_type: string; size: number; file_name: string }) =>
    api.post<UploadTicket>('/uploads', body),
  /**
   * Step 2: send the file at `fileUri` straight to storage. Uses the native uploader, not `api`:
   * the signed link carries its own token and must not get our Authorization header.
   */
  send: async (ticket: UploadTicket, fileUri: string, onProgress?: (fraction: number) => void) => {
    const result = await new File(fileUri).upload(ticket.upload_url, {
      httpMethod: ticket.upload_method.toUpperCase() as 'POST' | 'PUT' | 'PATCH',
      headers: ticket.upload_headers,
      // iOS reports these as BigInt despite the `number` type; dividing BigInts would give a BigInt.
      onProgress: ({ bytesSent, totalBytes }) => {
        const sent = Number(bytesSent);
        const total = Number(totalBytes);
        if (onProgress && total > 0) onProgress(Math.min(1, sent / total));
      },
    });
    if (result.status < 200 || result.status >= 300) throw new Error("Couldn't upload this photo. Please try again.");
  },
  /** Step 3: the server checks the file, strips metadata and makes a thumbnail. */
  complete: (id: string, body: UploadCompleteBody) => api.post<Attachment>(`/uploads/${id}/complete`, body),
  remove: (id: string) => api.delete<void>(`/uploads/${id}`),
  describe: (body: { upload_ids: string[]; note?: string | null; place?: string | null }) =>
    api.post<MediaDraft>('/uploads/describe', body),
  forTicket: (ref: string) => api.get<AttachmentView[]>(`/tickets/${ref}/attachments`),
};

export const ticketsApi = {
  list: (params: TicketListParams = {}) => api.get<Paginated<Ticket>>('/tickets', { params: clean(params) }),
  summary: () => api.get<DashboardSummary>('/tickets/summary'),
  create: (body: TicketCreateBody) => api.post<TicketDetail>('/tickets', body),
  detail: (ref: string) => api.get<TicketDetail>(`/tickets/${ref}`),
  triage: (ref: string, body: { category?: string; priority?: TicketPriority }) =>
    api.patch<TicketDetail>(`/tickets/${ref}`, body),
  changeStatus: (ref: string, status: TicketStatus, remarks?: string) =>
    api.post<TicketDetail>(`/tickets/${ref}/status`, { status, remarks: remarks || null }),
  assign: (ref: string, assignedTo: string, departmentId?: string | null, notes?: string) =>
    api.post<TicketDetail>(`/tickets/${ref}/assign`, {
      assigned_to: assignedTo,
      department_id: departmentId || null,
      notes: notes || null,
    }),
  comment: (ref: string, content: string, isInternal = false) =>
    api.post<TicketDetail>(`/tickets/${ref}/comments`, { content, is_internal: isInternal }),
  reopen: (ref: string, reason?: string) =>
    api.post<TicketDetail>(`/tickets/${ref}/reopen`, { reason: reason || null }),
  confirm: (ref: string) => api.post<TicketDetail>(`/tickets/${ref}/confirm`),
  withdraw: (ref: string, reason?: string) =>
    api.post<TicketDetail>(`/tickets/${ref}/withdraw`, { reason: reason || null }),
  submitFeedback: (ref: string, rating: number, comments?: string) =>
    api.post<TicketDetail>(`/tickets/${ref}/feedback`, { rating, comments: comments || null }),
  acceptSuggestions: (ref: string) => api.post<TicketDetail>(`/tickets/${ref}/suggestions/accept`),
  refreshSuggestions: (ref: string) => api.post<TicketDetail>(`/tickets/${ref}/suggestions/refresh`),
  sameProblem: (ref: string, otherRef: string) => api.post<TicketDetail>(`/tickets/${ref}/duplicates/${otherRef}/group`),
  notSameProblem: (ref: string, otherRef: string) => api.post<TicketDetail>(`/tickets/${ref}/duplicates/${otherRef}/dismiss`),
  splitFromGroup: (ref: string) => api.post<TicketDetail>(`/tickets/${ref}/group/split`),
};

export const notificationsApi = {
  list: (params: NotificationListParams = {}) =>
    api.get<Paginated<AppNotification>>('/notifications', { params: clean(params) }),
  unreadCount: () => api.get<{ count: number }>('/notifications/unread-count'),
  /** Both calls return how many notifications are still unread. */
  markRead: (ids: string[]) => api.post<{ count: number }>('/notifications/read', { ids }),
  markAllRead: () => api.post<{ count: number }>('/notifications/read', { all: true }),
};

export const assistantApi = {
  chat: (message: string, history: AssistantTurn[]) => api.post<AssistantReply>('/assistant/chat', { message, history }),
};

/** Drop empty filter values so they are not sent as `?status=`. */
function clean<T extends object>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== '' && value !== undefined && value !== null && value !== false),
  ) as Partial<T>;
}
