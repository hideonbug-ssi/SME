
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProductCard } from './ProductCard';
import type { ProductRecommendation } from '../../types/recommendation';

const mockRecommendation: ProductRecommendation = {
  product_id: 'ktb-term-deposit',
  product_name: 'KTB High-Yield Term Deposit',
  rationale:
    'Your cash surplus of ฿350,000 has been idle for 18 days. A 3-month term deposit at 2.8% would earn ฿2,450.',
  relevance_score: 0.82,
  signal_basis: 'Sustained surplus — 14+ days',
  repayability: 'not_applicable',
  disclosures: [
    'Returns are not guaranteed.',
    'Subject to KTB terms and conditions.',
  ],
};

const lendingRecommendation: ProductRecommendation = {
  ...mockRecommendation,
  product_id: 'ktb-credit-line',
  product_name: 'KTB SME Revolving Credit Line',
  repayability: 'passed',
  disclosures: ['Interest applies. Subject to credit approval.'],
};

describe('ProductCard', () => {
  it('renders product name', () => {
    render(<ProductCard recommendation={mockRecommendation} />);
    expect(screen.getByText('KTB High-Yield Term Deposit')).toBeInTheDocument();
  });

  it('renders rationale text', () => {
    render(<ProductCard recommendation={mockRecommendation} />);
    expect(screen.getByText(/idle for 18 days/)).toBeInTheDocument();
  });

  it('shows relevance score as percentage', () => {
    render(<ProductCard recommendation={mockRecommendation} />);
    expect(screen.getByText('82%')).toBeInTheDocument();
  });

  it('shows signal basis badge', () => {
    render(<ProductCard recommendation={mockRecommendation} />);
    expect(screen.getByText(/Sustained surplus/)).toBeInTheDocument();
  });

  it('does NOT show repayability confirmed for not_applicable products', () => {
    render(<ProductCard recommendation={mockRecommendation} />);
    expect(screen.queryByText('Repayability confirmed')).not.toBeInTheDocument();
  });

  it('shows repayability confirmed for lending products with passed status', () => {
    render(<ProductCard recommendation={lendingRecommendation} />);
    expect(screen.getByText('Repayability confirmed')).toBeInTheDocument();
  });

  it('expands disclosures when disclosure button is clicked', async () => {
    render(<ProductCard recommendation={mockRecommendation} />);
    const toggleBtn = screen.getByRole('button', { name: /disclosures/i });
    await userEvent.click(toggleBtn);
    expect(screen.getByText('Returns are not guaranteed.')).toBeInTheDocument();
  });

  it('renders Learn More button', () => {
    render(<ProductCard recommendation={mockRecommendation} />);
    expect(screen.getByRole('button', { name: /learn more/i })).toBeInTheDocument();
  });

  it('renders "Recommended for You" header', () => {
    render(<ProductCard recommendation={mockRecommendation} />);
    expect(screen.getByText('Recommended for You')).toBeInTheDocument();
  });

  it('shows progress bar with correct aria attributes', () => {
    render(<ProductCard recommendation={mockRecommendation} />);
    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '82');
    expect(bar).toHaveAttribute('aria-valuemin', '0');
    expect(bar).toHaveAttribute('aria-valuemax', '100');
  });
});
