import axios from 'axios';
import { isAuthError } from '@supabase/supabase-js';
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
}

export interface TicketDetail extends Ticket {
  created_by_name: string;
  assigned_to_name: string | null;
  department_name: string | null;
  comments: TicketComment[];
  history: TicketHistoryEntry[];
  permissions: TicketPermissions;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
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

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

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
};

export const departmentsApi = {
  list: () => api.get<Department[]>('/departments'),
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

export const ticketsApi = {
  list: (params: TicketListParams = {}) => api.get<Paginated<Ticket>>('/tickets', { params: clean(params) }),
  summary: () => api.get<DashboardSummary>('/tickets/summary'),
  create: (body: { title: string; description: string; category: string; location: string; priority: TicketPriority }) =>
    api.post<TicketDetail>('/tickets', body),
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
};

/** Drop empty filter values so they are not sent as `?status=`. */
function clean<T extends object>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== '' && value !== undefined && value !== null && value !== false),
  ) as Partial<T>;
}
