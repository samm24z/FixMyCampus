import React from 'react';
import { cn } from '@/lib/utils';
import { avatarColour, initials } from '@/lib/account';
import type { User } from '@/lib/api';

/** Round initials avatar, coloured per person (like Google's). Decorative: callers label the control around it. */
export const UserAvatar: React.FC<{ user: Pick<User, 'id' | 'full_name'>; className?: string }> = ({ user, className }) => (
  <span
    aria-hidden="true"
    className={cn('inline-flex shrink-0 select-none items-center justify-center rounded-full font-medium text-white', className)}
    style={{ backgroundColor: avatarColour(user.id) }}
  >
    {initials(user.full_name)}
  </span>
);
