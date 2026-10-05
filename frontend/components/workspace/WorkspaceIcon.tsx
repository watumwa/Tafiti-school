import {
  BadgeCheck,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  ChartNoAxesColumn,
  Contact,
  History,
  Landmark,
  LayoutDashboard,
  Library,
  MessagesSquare,
  School,
  Settings2,
  UserPlus,
  Users,
  WalletCards,
  type LucideIcon,
} from 'lucide-react';

const icons: Record<string, LucideIcon> = {
  'layout-dashboard': LayoutDashboard,
  users: Users,
  'badge-check': BadgeCheck,
  'user-plus': UserPlus,
  contact: Contact,
  school: School,
  'book-open': BookOpen,
  'chart-no-axes-column': ChartNoAxesColumn,
  'calendar-check': CalendarCheck,
  'calendar-days': CalendarDays,
  'wallet-cards': WalletCards,
  landmark: Landmark,
  library: Library,
  'messages-square': MessagesSquare,
  history: History,
  'settings-2': Settings2,
};

export function WorkspaceIcon({ name, size = 18, className = '' }: { name: string; size?: number; className?: string }) {
  const Icon = icons[name] ?? LayoutDashboard;
  return <Icon size={size} className={className} strokeWidth={1.9} aria-hidden="true" />;
}
