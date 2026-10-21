
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TierBadge } from './TierBadge';

describe('TierBadge', () => {
  it('renders nothing for green tier (silent)', () => {
    const { container } = render(<TierBadge tier="green" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders "Potential Shortfall" for yellow tier', () => {
    render(<TierBadge tier="yellow" />);
    expect(screen.getByText('Potential Shortfall')).toBeInTheDocument();
  });

  it('renders "Cash Gap Detected" for red tier', () => {
    render(<TierBadge tier="red" />);
    expect(screen.getByText('Cash Gap Detected')).toBeInTheDocument();
  });

  it('has role="status" for accessibility', () => {
    render(<TierBadge tier="yellow" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('applies amber classes for yellow tier', () => {
    const { container } = render(<TierBadge tier="yellow" />);
    expect(container.firstChild).toHaveClass('bg-amber-100', 'text-amber-800');
  });

  it('applies red classes for red tier', () => {
    const { container } = render(<TierBadge tier="red" />);
    expect(container.firstChild).toHaveClass('bg-red-100', 'text-red-800');
  });
});
