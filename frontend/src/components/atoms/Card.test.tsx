
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Card, CardHeader, CardTitle } from './Card';

describe('Card', () => {
  it('renders children', () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText('Card content')).toBeInTheDocument();
  });

  it('applies default medium padding', () => {
    const { container } = render(<Card>Content</Card>);
    expect(container.firstChild).toHaveClass('p-6');
  });

  it('applies small padding when specified', () => {
    const { container } = render(<Card padding="sm">Content</Card>);
    expect(container.firstChild).toHaveClass('p-4');
  });

  it('applies no padding when specified', () => {
    const { container } = render(<Card padding="none">Content</Card>);
    expect(container.firstChild).not.toHaveClass('p-6', 'p-4', 'p-8');
  });

  it('merges additional className', () => {
    const { container } = render(<Card className="extra">Content</Card>);
    expect(container.firstChild).toHaveClass('extra');
  });
});

describe('CardTitle', () => {
  it('renders title text in h3', () => {
    render(<CardTitle>My Title</CardTitle>);
    const el = screen.getByText('My Title');
    expect(el.tagName).toBe('H3');
  });
});

describe('CardHeader', () => {
  it('renders children in a flex row', () => {
    const { container } = render(
      <CardHeader>
        <span>Left</span>
        <span>Right</span>
      </CardHeader>,
    );
    expect(container.firstChild).toHaveClass('flex');
    expect(screen.getByText('Left')).toBeInTheDocument();
    expect(screen.getByText('Right')).toBeInTheDocument();
  });
});
