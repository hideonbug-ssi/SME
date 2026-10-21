
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AlertBanner } from './AlertBanner';

describe('AlertBanner', () => {
  it('renders message text', () => {
    render(<AlertBanner variant="info" message="This is an info message" />);
    expect(screen.getByText('This is an info message')).toBeInTheDocument();
  });

  it('renders optional title', () => {
    render(<AlertBanner variant="warning" title="Attention" message="Something happened" />);
    expect(screen.getByText('Attention')).toBeInTheDocument();
  });

  it('does not render title element when not provided', () => {
    render(<AlertBanner variant="danger" message="Error!" />);
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
  });

  it('has role="alert" for accessibility', () => {
    render(<AlertBanner variant="success" message="Done!" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('applies warning color classes for warning variant', () => {
    const { container } = render(<AlertBanner variant="warning" message="Warn" />);
    expect(container.firstChild).toHaveClass('bg-amber-50', 'border-amber-200');
  });

  it('applies danger color classes for danger variant', () => {
    const { container } = render(<AlertBanner variant="danger" message="Danger" />);
    expect(container.firstChild).toHaveClass('bg-red-50', 'border-red-200');
  });

  it('applies success color classes for success variant', () => {
    const { container } = render(<AlertBanner variant="success" message="Great" />);
    expect(container.firstChild).toHaveClass('bg-green-50', 'border-green-200');
  });

  it('applies info color classes for info variant', () => {
    const { container } = render(<AlertBanner variant="info" message="Note" />);
    expect(container.firstChild).toHaveClass('bg-blue-50', 'border-blue-200');
  });
});
