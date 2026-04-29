'use client';

import type { ReactNode } from 'react';

export default function ConnectorsLayout({ children }: { children: ReactNode }): JSX.Element {
  return <div className="h-full">{children}</div>;
}
