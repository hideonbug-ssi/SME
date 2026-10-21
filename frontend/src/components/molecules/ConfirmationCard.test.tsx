
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfirmationCard } from './ConfirmationCard';
import type { PendingAction } from '../../types/shortfall';

const mockAction: PendingAction = {
  id: 'pa-001',
  action_type: 'tax_setaside',
  amount: 23000,
  source_account: 'KTB Deposit XXXX-1234',
  dest_account: 'Tax Reserve Sub-Account',
  memo: 'Income Tax Set-Aside FY2025',
  status: 'pending',
  created_at: '2026-07-14T08:00:00Z',
};

describe('ConfirmationCard', () => {
  it('renders the amount in Thai Baht format', () => {
    render(
      <ConfirmationCard
        action={mockAction}
        onConfirm={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByText('฿23,000')).toBeInTheDocument();
  });

  it('renders source account', () => {
    render(
      <ConfirmationCard
        action={mockAction}
        onConfirm={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByText('KTB Deposit XXXX-1234')).toBeInTheDocument();
  });

  it('renders destination account', () => {
    render(
      <ConfirmationCard
        action={mockAction}
        onConfirm={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByText('Tax Reserve Sub-Account')).toBeInTheDocument();
  });

  it('renders memo/purpose', () => {
    render(
      <ConfirmationCard
        action={mockAction}
        onConfirm={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByText('Income Tax Set-Aside FY2025')).toBeInTheDocument();
  });

  it('calls onConfirm with action id when Confirm is clicked', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <ConfirmationCard
        action={mockAction}
        onConfirm={onConfirm}
        onDismiss={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith('pa-001'));
  });

  it('calls onDismiss with action id when Dismiss is clicked', async () => {
    const onDismiss = vi.fn().mockResolvedValue(undefined);
    render(
      <ConfirmationCard
        action={mockAction}
        onConfirm={vi.fn()}
        onDismiss={onDismiss}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    await waitFor(() => expect(onDismiss).toHaveBeenCalledWith('pa-001'));
  });

  it('shows "Awaiting Your Confirmation" header text', () => {
    render(
      <ConfirmationCard
        action={mockAction}
        onConfirm={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByText('Awaiting Your Confirmation')).toBeInTheDocument();
  });
});
