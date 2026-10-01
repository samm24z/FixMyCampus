import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  ShieldAlert, 
  LayoutDashboard, 
  Ticket, 
  BotMessageSquare, 
  UserCheck, 
  ShieldCheck, 
  LogIn, 
  UserPlus 
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/lib/auth';
import type { Role } from '@/lib/api';

export const Navbar: React.FC = () => {
  const location = useLocation();
  const { user, logout } = useAuth();

  const allLinks: { to: string; label: string; icon: typeof Ticket; badge?: string; roles?: Role[] }[] = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/tickets', label: 'Tickets', icon: Ticket },
    { to: '/assistant', label: 'Policy AI', icon: BotMessageSquare, badge: 'RAG' },
    { to: '/staff', label: 'Staff Desk', icon: UserCheck, roles: ['STAFF', 'COORDINATOR', 'ADMIN'] },
    { to: '/admin', label: 'Admin', icon: ShieldCheck, roles: ['ADMIN'] },
  ];
  const navLinks = user ? allLinks.filter((link) => !link.roles || link.roles.includes(user.role)) : [];

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-8">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-tr from-indigo-600 to-violet-500 text-white shadow-md shadow-indigo-500/25 group-hover:scale-105 transition-transform">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-lg leading-tight tracking-tight">
                FixMyCampus <span className="gradient-text font-black">AI</span>
              </span>
              <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">
                Grievance Resolution Platform
              </span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-1 text-sm font-medium">
            {navLinks.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname.startsWith(item.to);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-md transition-colors text-muted-foreground hover:text-foreground hover:bg-accent',
                    isActive && 'text-primary font-semibold bg-primary/10 hover:bg-primary/15'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                  {item.badge && (
                    <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-bold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                      {item.badge}
                    </Badge>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 mr-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-xs text-muted-foreground font-medium">Core API Ready</span>
          </div>

          {user ? (
            <>
              <span className="hidden lg:inline text-xs text-muted-foreground">{user.full_name}</span>
              <button type="button" onClick={logout} className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent rounded-md transition-colors">
                <LogIn className="h-4 w-4" />
                <span>Sign Out</span>
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent rounded-md transition-colors"><LogIn className="h-4 w-4" /><span>Sign In</span></Link>
              <Link to="/register" className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 rounded-md shadow-sm transition-colors"><UserPlus className="h-4 w-4" /><span>Register</span></Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
