
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ConfidencePill } from './ConfidencePill';

describe('ConfidencePill', () => {
  it('renders "High confidence" for high level', () => {
    render(<ConfidencePill level="high" />);
    expect(screen.getByText('High confidence')).toBeInTheDocument();
  });

  it('renders low confidence label for low level', () => {
    render(<ConfidencePill level="low" />);
    expect(screen.getByText('Low confidence — limited history')).toBeInTheDocument();
  });

  it('applies green classes for high level', () => {
    const { container } = render(<ConfidencePill level="high" />);
    expect(container.firstChild).toHaveClass('bg-green-100', 'text-green-800');
  });

  it('applies amber classes for low level', () => {
    const { container } = render(<ConfidencePill level="low" />);
    expect(container.firstChild).toHaveClass('bg-amber-100', 'text-amber-800');
  });

  it('merges additional className', () => {
    const { container } = render(<ConfidencePill level="high" className="extra" />);
    expect(container.firstChild).toHaveClass('extra');
  });
});
