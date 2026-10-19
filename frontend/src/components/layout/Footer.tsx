import React from 'react';
import { Link } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { CAMPUS } from '@/lib/campus';

export const Footer: React.FC = () => {
  const { user } = useAuth();
  return (
    <footer className="border-t bg-muted/30 py-6 md:py-8 mt-auto">
      <div className="container flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-primary" />
          <span>FixMyCampus &copy; {new Date().getFullYear()} - {CAMPUS.name}</span>
        </div>
        <div className="flex items-center gap-4">
          {user && <Link to="/campus-guide" className="font-medium text-primary hover:underline">Campus guide</Link>}
          <span>Trouble using the site? Contact your campus administrator.</span>
        </div>
      </div>
    </footer>
  );
};
