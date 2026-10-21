import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock import.meta.env for tests
Object.defineProperty(import.meta, 'env', {
  value: {
    VITE_API_BASE_URL: 'http://localhost:8000',
  },
  writable: true,
});

// Silence console errors from React in tests
vi.spyOn(console, 'error').mockImplementation(() => {});
