import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Building2, MapPin } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useCampusPlaces } from '@/lib/places';
import { CAMPUS } from '@/lib/campus';
import type { Place } from '@/lib/api';

function PlaceList({ title, places }: { title: string; places: Place[] }) {
  if (places.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-semibold">{title}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {places.map((place) => (
          <Card key={place.key} id={place.key} className="scroll-mt-24 target:ring-2 target:ring-primary">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                {place.kind === 'block' ? <Building2 className="h-4 w-4 text-primary" /> : <MapPin className="h-4 w-4 text-primary" />} {place.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{place.description}</CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}

export const CampusGuidePage: React.FC = () => {
  const { places, loading, failed } = useCampusPlaces();
  const { hash } = useLocation();

  useEffect(() => {
    if (hash && places.length > 0) document.getElementById(hash.slice(1))?.scrollIntoView?.({ block: 'center' });
  }, [hash, places]);

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Campus guide</h1>
        <p className="text-muted-foreground text-sm mt-1">Where things are at {CAMPUS.name}, and which block each branch has its classes in.</p>
      </div>
      {loading && <p className="text-sm text-muted-foreground">Loading the campus guide...</p>}
      {failed && <p className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">Sorry, the campus guide could not be loaded. Please try again.</p>}
      <PlaceList title="Blocks" places={places.filter((place) => place.kind === 'block')} />
      <PlaceList title="Other places" places={places.filter((place) => place.kind === 'facility')} />
    </div>
  );
};
