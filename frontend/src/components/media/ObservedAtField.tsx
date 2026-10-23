import React, { useEffect, useId, useRef, useState } from 'react';
import { fromDateTimeLocal, pickObservedAt, toDateTimeLocal } from '@/lib/media';

interface Props {
  /** Capture times of the photos; the earliest recent one is suggested. */
  captures: (Date | null)[];
  onChange: (value: Date | null) => void;
  className?: string;
}

/** "When did you notice it?" Starts at the photos' time (or now) until the student changes it. */
export const ObservedAtField: React.FC<Props> = ({ captures, onChange, className = 'w-full rounded-lg border bg-background px-3 py-2 text-sm' }) => {
  const id = useId();
  const edited = useRef(false);
  const emit = useRef(onChange);
  emit.current = onChange;
  const [value, setValue] = useState(() => toDateTimeLocal(new Date()));
  const capturesKey = captures.map((d) => (d ? d.getTime() : '')).join(',');

  useEffect(() => {
    if (edited.current) return;
    const suggested = pickObservedAt(captures, new Date());
    setValue(toDateTimeLocal(suggested));
    emit.current(fromDateTimeLocal(toDateTimeLocal(suggested)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [capturesKey]);

  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-sm font-medium">When did you notice it?</label>
      <input
        id={id}
        type="datetime-local"
        className={className}
        value={value}
        max={toDateTimeLocal(new Date())}
        onChange={(event) => {
          edited.current = true;
          setValue(event.target.value);
          onChange(fromDateTimeLocal(event.target.value));
        }}
      />
    </div>
  );
};
