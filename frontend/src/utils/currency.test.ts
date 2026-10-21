import { describe, it, expect } from 'vitest';
import { formatTHB, formatTHBDecimal } from './currency';

describe('formatTHB', () => {
  it('formats whole number amounts with ฿ prefix and comma separators', () => {
    expect(formatTHB(280000)).toBe('฿280,000');
  });

  it('formats zero', () => {
    expect(formatTHB(0)).toBe('฿0');
  });

  it('formats small amounts', () => {
    expect(formatTHB(100)).toBe('฿100');
  });

  it('formats millions', () => {
    expect(formatTHB(1500000)).toBe('฿1,500,000');
  });

  it('rounds decimals when formatting', () => {
    expect(formatTHB(280000.75)).toBe('฿280,001');
  });

  it('handles negative amounts with a minus sign before ฿', () => {
    expect(formatTHB(-50000)).toBe('-฿50,000');
  });

  it('formats three-digit amounts without comma', () => {
    expect(formatTHB(999)).toBe('฿999');
  });

  it('formats exactly one million', () => {
    expect(formatTHB(1000000)).toBe('฿1,000,000');
  });

  it('formats large forecast amount used in demo scenario A', () => {
    expect(formatTHB(350000)).toBe('฿350,000');
  });

  it('formats shortfall amount used in demo scenario B', () => {
    expect(formatTHB(180000)).toBe('฿180,000');
  });
});

describe('formatTHBDecimal', () => {
  it('formats with 2 decimal places by default', () => {
    expect(formatTHBDecimal(280000.5)).toBe('฿280,000.50');
  });

  it('formats with 0 decimal places when specified', () => {
    expect(formatTHBDecimal(280000, 0)).toBe('฿280,000');
  });

  it('handles negative values', () => {
    expect(formatTHBDecimal(-1234.5)).toBe('-฿1,234.50');
  });

  it('formats zero with decimals', () => {
    expect(formatTHBDecimal(0)).toBe('฿0.00');
  });
});
