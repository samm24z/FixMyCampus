import React from 'react';
import { Link } from 'react-router-dom';
import { BotMessageSquare, Send } from 'lucide-react';
import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export const AssistantPage: React.FC = () => {
  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-3xl font-bold tracking-tight">Ask a Question</h1>
          <Badge variant="outline">Coming soon</Badge>
        </div>
        <p className="text-muted-foreground text-sm mt-1">
          Soon you'll be able to ask about campus rules and how to get things fixed, right here.
        </p>
      </div>

      <Card className="flex flex-col h-[420px]">
        <CardHeader className="py-3 px-5 border-b bg-muted/20">
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <BotMessageSquare className="h-4 w-4 text-primary" /> Campus help
          </span>
        </CardHeader>

        <CardContent className="flex-1 overflow-y-auto p-5">
          <div className="max-w-[85%] rounded-2xl rounded-bl-none border bg-muted/70 px-4 py-3 text-sm leading-relaxed">
            Hi! This feature isn't ready yet. To get something fixed on campus, please{' '}
            <Link to="/tickets/new" className="font-medium text-primary underline-offset-2 hover:underline">report a problem</Link>.
          </div>
        </CardContent>

        <CardFooter className="p-3 border-t bg-background">
          <div className="flex w-full items-center gap-2">
            <input
              type="text"
              placeholder="Coming soon"
              className="flex-1 px-4 py-2.5 text-sm border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              disabled
            />
            <Button size="icon" disabled className="shrink-0" aria-label="Send">
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
};
