import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center text-center py-20 space-y-4">
      <div className="p-4 rounded-full bg-destructive/10 text-destructive mb-2">
        <ShieldAlert className="h-10 w-10" />
      </div>
      <h1 className="text-4xl font-extrabold">404 - Page Not Found</h1>
      <p className="text-muted-foreground text-sm max-w-md">
        The requested grievance portal page or route does not exist.
      </p>
      <Link to="/">
        <Button className="gap-2 mt-4">
          <ArrowLeft className="h-4 w-4" /> Return to Overview
        </Button>
      </Link>
    </div>
  );
};
