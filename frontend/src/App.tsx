
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from './layout/AppShell';
import { Dashboard } from './pages/Dashboard';
import { InvoicesPage } from './pages/InvoicesPage';
import { TaxPage } from './pages/TaxPage';
import { ConsolePage } from './pages/ConsolePage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="invoices" element={<InvoicesPage />} />
            <Route path="tax" element={<TaxPage />} />
            <Route path="console" element={<ConsolePage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
