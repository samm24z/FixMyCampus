import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  AlarmClock,
  Bell,
  CheckCheck,
  CircleAlert,
  MessageSquare,
  RefreshCw,
  Star,
  TicketPlus,
  UserCheck,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { notificationsApi, type AppNotification, type NotificationType } from '@/lib/api';
import { badgeLabel, notificationLink, timeAgo } from '@/lib/notifications';

const POLL_MS = 60_000;

const TYPE_ICONS: Record<NotificationType, { icon: LucideIcon; colour: string }> = {
  TICKET_CREATED: { icon: TicketPlus, colour: 'text-indigo-600 dark:text-indigo-400' },
  STATUS_CHANGED: { icon: RefreshCw, colour: 'text-blue-600 dark:text-blue-400' },
  ASSIGNED: { icon: UserCheck, colour: 'text-violet-600 dark:text-violet-400' },
  SLA_WARNING: { icon: AlarmClock, colour: 'text-amber-600 dark:text-amber-400' },
  SLA_BREACH: { icon: CircleAlert, colour: 'text-red-600 dark:text-red-400' },
  FEEDBACK_REQUEST: { icon: Star, colour: 'text-amber-600 dark:text-amber-400' },
  FEEDBACK_RECEIVED: { icon: Star, colour: 'text-emerald-600 dark:text-emerald-400' },
  COMMENT_ADDED: { icon: MessageSquare, colour: 'text-sky-600 dark:text-sky-400' },
};

/** Bell in the top bar: shows how many updates are unread and opens a list of the latest ones. */
export const NotificationBell: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => setOpen(false), [location.pathname]);

  const refreshCount = useCallback(() => {
    notificationsApi
      .unreadCount()
      .then((response) => setUnread(response.data.count))
      .catch(() => {});
  }, []);

  // Check for new updates every minute and whenever the user comes back to this tab.
  useEffect(() => {
    refreshCount();
    const timer = window.setInterval(refreshCount, POLL_MS);
    window.addEventListener('focus', refreshCount);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('focus', refreshCount);
    };
  }, [refreshCount]);

  // Load the latest ten each time the panel opens.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    notificationsApi
      .list({ page: 1, page_size: 10 })
      .then((response) => {
        if (cancelled) return;
        setItems(response.data.items);
        setFailed(false);
      })
      .catch(() => !cancelled && setFailed(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      button.current?.focus();
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const openItem = (item: AppNotification) => {
    if (!item.is_read) {
      setItems((current) => current.map((entry) => (entry.id === item.id ? { ...entry, is_read: true } : entry)));
      setUnread((count) => Math.max(0, count - 1));
      notificationsApi
        .markRead([item.id])
        .then((response) => setUnread(response.data.count))
        .catch(refreshCount);
    }
    const link = notificationLink(item);
    if (link) {
      setOpen(false);
      navigate(link);
    }
  };

  const markAll = () => {
    setItems((current) => current.map((entry) => ({ ...entry, is_read: true })));
    setUnread(0);
    notificationsApi
      .markAllRead()
      .then((response) => setUnread(response.data.count))
      .catch(refreshCount);
  };

  const label = badgeLabel(unread);

  return (
    <div ref={wrapper} className="relative">
      <button
        ref={button}
        type="button"
        title="Notifications"
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
        className="relative flex h-10 w-10 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Bell className="h-5 w-5" />
        {label && (
          <span className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold leading-none text-white">
            {label}
          </span>
        )}
      </button>

      {open && (
        <div
          id={menuId}
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 top-12 z-50 w-[min(24rem,calc(100vw-3rem))] overflow-hidden rounded-[28px] border bg-secondary shadow-xl dark:bg-card"
        >
          <div className="flex items-center justify-between gap-2 px-5 py-3">
            <h2 className="text-base font-semibold tracking-tight">Notifications</h2>
            <button
              type="button"
              onClick={markAll}
              disabled={unread === 0}
              className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10 disabled:pointer-events-none disabled:opacity-40"
            >
              <CheckCheck className="h-4 w-4" />
              Mark all as read
            </button>
          </div>

          <div className="max-h-[min(26rem,70vh)] overflow-y-auto px-2 pb-2">
            {failed && items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground">Couldn't load your notifications. Please try again later.</p>
            ) : loading && items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground">Loading...</p>
            ) : items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground">You're all caught up.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {items.map((item) => {
                  const { icon: Icon, colour } = TYPE_ICONS[item.type] ?? TYPE_ICONS.STATUS_CHANGED;
                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => openItem(item)}
                        className={cn(
                          'flex w-full items-start gap-3 rounded-[20px] px-3 py-3 text-left transition-colors hover:bg-accent',
                          item.is_read ? 'bg-transparent' : 'bg-card dark:bg-secondary',
                        )}
                      >
                        <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', colour)} />
                        <span className="min-w-0 flex-1">
                          <span className={cn('block truncate text-sm', item.is_read ? 'font-normal' : 'font-bold')}>{item.title}</span>
                          <span className="line-clamp-2 text-sm text-muted-foreground">{item.message}</span>
                          <span className="mt-1 block text-xs text-muted-foreground">{timeAgo(item.created_at)}</span>
                        </span>
                        {!item.is_read && <span aria-label="Unread" className="mt-2 h-2 w-2 shrink-0 rounded-full bg-primary" />}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            {failed && items.length > 0 && (
              <p className="px-3 py-2 text-center text-xs text-muted-foreground">Couldn't refresh the list.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
