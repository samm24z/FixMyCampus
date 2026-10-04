import React from 'react';
import { Shield, Sparkles } from 'lucide-react';
import { CAMPUS } from '@/lib/campus';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t bg-muted/30 py-6 md:py-8 mt-auto">
      <div className="container flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-primary" />
          <span>FixMyCampus AI &copy; {new Date().getFullYear()} - {CAMPUS.name}</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1">
            <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
            Human-in-the-Loop AI &bull; pgvector &bull; FastAPI &bull; React
          </span>
        </div>
      </div>
    </footer>
  );
};
