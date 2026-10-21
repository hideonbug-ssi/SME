
import type { ComponentType } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, FileText, Calculator, Terminal } from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  Icon: ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard', Icon: LayoutDashboard },
  { to: '/invoices', label: 'Invoices', Icon: FileText },
  { to: '/tax', label: 'Tax', Icon: Calculator },
  { to: '/console', label: 'Console', Icon: Terminal },
];

export function Sidebar() {
  return (
    <aside className="w-60 bg-gray-900 text-white flex flex-col min-h-screen">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-blue-500 flex items-center justify-center text-white font-bold text-sm">
            ฿
          </div>
          <div>
            <p className="text-sm font-bold leading-tight">Virtual CFO</p>
            <p className="text-xs text-gray-400 leading-tight">SME Agent</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-4 space-y-1" aria-label="Main navigation">
        {navItems.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-800">
        <p className="text-xs text-gray-500">KTB SME PoC Demo</p>
        <p className="text-xs text-gray-600">v0.1.0</p>
      </div>
    </aside>
  );
}
