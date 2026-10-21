
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Spinner } from './Spinner';

describe('Spinner', () => {
  it('renders with default label', () => {
    render(<Spinner />);
    // The label appears twice: once as visible span, once as sr-only — use getAllByText
    const matches = screen.getAllByText('Loading...');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders with custom label', () => {
    render(<Spinner label="Extracting invoice fields..." />);
    const matches = screen.getAllByText('Extracting invoice fields...');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('has role="status" for accessibility', () => {
    render(<Spinner />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('applies sm size class', () => {
    const { container } = render(<Spinner size="sm" />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveClass('h-4', 'w-4');
  });

  it('applies lg size class', () => {
    const { container } = render(<Spinner size="lg" />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveClass('h-12', 'w-12');
  });

  it('has sr-only text for screen readers', () => {
    const { container } = render(<Spinner label="Custom" />);
    const srText = container.querySelector('.sr-only');
    expect(srText).toHaveTextContent('Custom');
  });
});
