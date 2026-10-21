/**
 * Formats a numeric amount as Thai Baht with symbol prefix.
 * Example: formatTHB(280000) → "฿280,000"
 */
export function formatTHB(amount: number): string {
  const rounded = Math.round(amount);
  const formatted = Math.abs(rounded).toLocaleString('en-US');
  const sign = rounded < 0 ? '-' : '';
  return `${sign}฿${formatted}`;
}

/**
 * Formats a numeric amount as Thai Baht with decimal places.
 * Example: formatTHBDecimal(280000.5) → "฿280,000.50"
 */
export function formatTHBDecimal(amount: number, decimals = 2): string {
  const formatted = Math.abs(amount).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  const sign = amount < 0 ? '-' : '';
  return `${sign}฿${formatted}`;
}
