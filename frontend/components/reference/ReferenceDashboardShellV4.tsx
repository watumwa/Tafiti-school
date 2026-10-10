'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { createPortal } from 'react-dom';
import { BookOpen, CircleDollarSign, ReceiptText, UsersRound } from 'lucide-react';

import { ReferenceDashboardShellV3 } from './ReferenceDashboardShellV3';

type BillingLink = {
  slug: string;
  label: string;
  icon: typeof UsersRound;
};

const BILLING_LINKS: BillingLink[] = [
  { slug: 'fees', label: 'Student Accounts', icon: UsersRound },
  { slug: 'fees-class-bills', label: 'Class Bills', icon: ReceiptText },
  { slug: 'fees-bill-items', label: 'Fee Categories', icon: BookOpen },
  { slug: 'fees-payments', label: 'Payments', icon: CircleDollarSign },
];

function BillingSidebarLinks({ host }: { host: HTMLElement }) {
  const pathname = usePathname();
  const dashboardPath = pathname.match(/^\/dashboard\/[^/]+/)?.[0] ?? '';

  if (!dashboardPath) return null;

  return createPortal(
    <div className="mb-1 ml-4 mt-1 space-y-0.5 border-l border-blue-200/20 pl-2" aria-label="Fees and billing navigation">
      <p className="px-2 pb-0.5 pt-1 text-[7px] font-extrabold uppercase tracking-[.15em] text-blue-100/40">Billing</p>
      {BILLING_LINKS.map((item) => {
        const href = `${dashboardPath}/${item.slug}`;
        const active = pathname === href || pathname.startsWith(`${href}/`);
        const Icon = item.icon;
        return (
          <Link
            key={item.slug}
            href={href}
            className={`group flex min-h-[30px] items-center gap-2 rounded-md px-2 text-[10px] font-bold transition ${active ? 'bg-white/[.11] text-white' : 'text-blue-50/60 hover:bg-white/[.07] hover:text-white'}`}
          >
            <Icon size={13} className={active ? 'text-blue-200' : 'text-blue-100/45 group-hover:text-blue-100'} />
            <span className="min-w-0 flex-1">{item.label}</span>
          </Link>
        );
      })}
    </div>,
    host,
  );
}

export function ReferenceDashboardShellV4() {
  const [billingHost, setBillingHost] = useState<HTMLElement | null>(null);

  useEffect(() => {
    let mountedHost: HTMLElement | null = null;

    const install = () => {
      const feesLink = document.querySelector<HTMLAnchorElement>('aside nav a[href$="/fees"]');
      if (!feesLink?.parentElement) return false;

      const parent = feesLink.parentElement;
      const existing = parent.querySelector<HTMLElement>('[data-tafiti-billing-subnav="true"]');
      const host = existing ?? document.createElement('div');
      if (!existing) {
        host.dataset.tafitiBillingSubnav = 'true';
        feesLink.insertAdjacentElement('afterend', host);
      }
      mountedHost = host;
      setBillingHost(host);
      return true;
    };

    if (install()) return () => {
      mountedHost?.remove();
      setBillingHost(null);
    };

    const observer = new MutationObserver(() => {
      if (install()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      mountedHost?.remove();
      setBillingHost(null);
    };
  }, []);

  return (
    <>
      <ReferenceDashboardShellV3 />
      {billingHost && <BillingSidebarLinks host={billingHost} />}
    </>
  );
}
