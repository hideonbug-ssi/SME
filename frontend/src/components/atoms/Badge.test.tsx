
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge } from './Badge';

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge>Stage 1</Badge>);
    expect(screen.getByText('Stage 1')).toBeInTheDocument();
  });

  it('applies default variant class', () => {
    const { container } = render(<Badge>Default</Badge>);
    expect(container.firstChild).toHaveClass('bg-gray-100', 'text-gray-800');
  });

  it('applies success variant class', () => {
    const { container } = render(<Badge variant="success">OK</Badge>);
    expect(container.firstChild).toHaveClass('bg-green-100', 'text-green-800');
  });

  it('applies danger variant class', () => {
    const { container } = render(<Badge variant="danger">Error</Badge>);
    expect(container.firstChild).toHaveClass('bg-red-100', 'text-red-800');
  });

  it('applies warning variant class', () => {
    const { container } = render(<Badge variant="warning">Warning</Badge>);
    expect(container.firstChild).toHaveClass('bg-amber-100', 'text-amber-800');
  });

  it('applies info variant class', () => {
    const { container } = render(<Badge variant="info">Info</Badge>);
    expect(container.firstChild).toHaveClass('bg-blue-100', 'text-blue-800');
  });

  it('merges additional className', () => {
    const { container } = render(<Badge className="my-custom-class">Custom</Badge>);
    expect(container.firstChild).toHaveClass('my-custom-class');
  });

  it('renders as a span element', () => {
    render(<Badge>Span</Badge>);
    const el = screen.getByText('Span');
    expect(el.tagName).toBe('SPAN');
  });
});
