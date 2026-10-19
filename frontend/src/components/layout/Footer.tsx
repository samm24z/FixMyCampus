import React from 'react';
import { Shield } from 'lucide-react';
import { CAMPUS } from '@/lib/campus';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t bg-muted/30 py-6 md:py-8 mt-auto">
      <div className="container flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-primary" />
          <span>FixMyCampus &copy; {new Date().getFullYear()} - {CAMPUS.name}</span>
        </div>
        <div className="flex items-center gap-4">
          <span>Trouble using the site? Contact your campus administrator.</span>
        </div>
      </div>
    </footer>
  );
};
