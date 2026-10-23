import React, { useEffect, useId, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LogOut, X } from 'lucide-react';
import { UserAvatar } from '@/components/UserAvatar';
import type { User } from '@/lib/api';

/** Google-style account button: initials avatar that opens a card with "Manage your account" and "Sign out". */
export const AccountMenu: React.FC<{ user: User; onSignOut: () => void }> = ({ user, onSignOut }) => {
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const location = useLocation();

  useEffect(() => setOpen(false), [location.pathname]);

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

  const firstName = user.full_name.split(' ')[0];

  return (
    <div ref={wrapper} className="relative">
      <button
        ref={button}
        type="button"
        title={user.full_name}
        aria-label={`Account: ${user.full_name}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
        className="flex h-10 w-10 items-center justify-center rounded-full transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <UserAvatar user={user} className="h-8 w-8 text-sm" />
      </button>

      {open && (
        <div
          id={menuId}
          role="dialog"
          aria-label="Your account"
          className="absolute right-0 top-12 z-50 w-[min(22rem,calc(100vw-3rem))] rounded-[28px] border bg-secondary p-2 shadow-xl dark:bg-card"
        >
          <div className="relative px-10 pb-1 pt-3 text-center text-sm font-medium">
            <span className="block truncate" title={user.email}>{user.email}</span>
            <button
              type="button"
              aria-label="Close"
              onClick={() => setOpen(false)}
              className="absolute right-1 top-1 flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="flex flex-col items-center gap-3 px-4 pb-5 pt-4">
            <UserAvatar user={user} className="h-20 w-20 text-3xl" />
            <h2 className="text-center text-xl font-semibold tracking-tight">Hi, {firstName}!</h2>
            <Link
              to="/account"
              className="rounded-full border border-foreground/30 px-6 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/10"
            >
              Manage your account
            </Link>
          </div>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
            className="flex w-full items-center justify-center gap-2 rounded-[20px] bg-card px-4 py-3.5 text-sm font-medium transition-colors hover:bg-accent dark:bg-secondary"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
};
