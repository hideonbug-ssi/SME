
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { ScenarioSwitcher } from '../components/organisms/ScenarioSwitcher';

export function AppShell() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <Outlet />
        </div>
      </main>
      <ScenarioSwitcher />
    </div>
  );
}
