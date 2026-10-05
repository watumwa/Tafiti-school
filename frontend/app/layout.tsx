import './globals.css';
import type { Metadata } from 'next';

import { ToastProvider } from '@/components/ui/ToastProvider';

export const metadata: Metadata = {
  title: {
    default: 'Tafiti School Management System',
    template: '%s | Tafiti',
  },
  description: 'One connected workspace for school academics, finance, administration and communication.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body><ToastProvider>{children}</ToastProvider></body>
    </html>
  );
}
