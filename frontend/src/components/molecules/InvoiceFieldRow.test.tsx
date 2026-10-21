
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InvoiceFieldRow } from './InvoiceFieldRow';

describe('InvoiceFieldRow', () => {
  it('renders label and value', () => {
    render(
      <InvoiceFieldRow label="Invoice No." value="INV-001" fieldKey="invoice_no" />,
    );
    expect(screen.getByText('Invoice No.')).toBeInTheDocument();
    expect(screen.getByText('INV-001')).toBeInTheDocument();
  });

  it('shows "—" when value is empty string', () => {
    render(<InvoiceFieldRow label="Email" value="" fieldKey="email" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('does NOT show low-confidence warning for high confidence', () => {
    render(
      <InvoiceFieldRow
        label="Amount"
        value="฿50,000"
        fieldKey="amount_thb"
        confidence={0.92}
      />,
    );
    expect(screen.queryByText('Low confidence')).not.toBeInTheDocument();
  });

  it('shows low-confidence warning for confidence below threshold', () => {
    render(
      <InvoiceFieldRow
        label="Amount"
        value="฿50,000"
        fieldKey="amount_thb"
        confidence={0.70}
      />,
    );
    expect(screen.getByText('Low confidence')).toBeInTheDocument();
  });

  it('shows editable input for low-confidence + editable prop', () => {
    const onChange = vi.fn();
    render(
      <InvoiceFieldRow
        label="Amount"
        value="฿50,000"
        fieldKey="amount_thb"
        confidence={0.70}
        editable
        onChange={onChange}
      />,
    );
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('shows static text for high-confidence even when editable', () => {
    render(
      <InvoiceFieldRow
        label="Amount"
        value="฿50,000"
        fieldKey="amount_thb"
        confidence={0.95}
        editable
      />,
    );
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.getByText('฿50,000')).toBeInTheDocument();
  });

  it('calls onChange with field key and new value on input change', async () => {
    const onChange = vi.fn();
    render(
      <InvoiceFieldRow
        label="Amount"
        value="Old"
        fieldKey="amount_thb"
        confidence={0.50}
        editable
        onChange={onChange}
      />,
    );
    const input = screen.getByRole('textbox');
    await userEvent.clear(input);
    await userEvent.type(input, 'New Value');
    // onChange called with the field key and current value
    expect(onChange).toHaveBeenCalledWith('amount_thb', expect.any(String));
  });

  it('shows confidence percentage when provided', () => {
    render(
      <InvoiceFieldRow
        label="Name"
        value="ACME"
        fieldKey="name"
        confidence={0.75}
      />,
    );
    expect(screen.getByText('75%')).toBeInTheDocument();
  });
});
