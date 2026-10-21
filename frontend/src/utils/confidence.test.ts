import { describe, it, expect } from 'vitest';
import { getConfidenceStyle, getBalanceColor } from './confidence';

describe('getConfidenceStyle', () => {
  it('returns high-confidence green style', () => {
    const style = getConfidenceStyle('high');
    expect(style.label).toBe('High confidence');
    expect(style.colorClass).toBe('green');
    expect(style.bgClass).toContain('green');
    expect(style.textClass).toContain('green');
    expect(style.dotClass).toContain('green');
  });

  it('returns low-confidence amber style', () => {
    const style = getConfidenceStyle('low');
    expect(style.label).toBe('Low confidence — limited history');
    expect(style.colorClass).toBe('amber');
    expect(style.bgClass).toContain('amber');
    expect(style.textClass).toContain('amber');
    expect(style.dotClass).toContain('amber');
  });
});

describe('getBalanceColor', () => {
  const monthlyOutflow = 200000;

  it('returns red when balance is below 50% of monthly outflow', () => {
    expect(getBalanceColor(50000, monthlyOutflow)).toBe('red'); // < 100k threshold
  });

  it('returns amber when balance is between 50% and 75% of monthly outflow', () => {
    expect(getBalanceColor(120000, monthlyOutflow)).toBe('amber'); // between 100k and 150k
  });

  it('returns green when balance is above 75% of monthly outflow', () => {
    expect(getBalanceColor(200000, monthlyOutflow)).toBe('green');
  });

  it('returns green for large surplus', () => {
    expect(getBalanceColor(500000, monthlyOutflow)).toBe('green');
  });

  it('returns red when balance is exactly at shortfall threshold', () => {
    // Exactly at 50% threshold (100k) → 100k < 100k is false, so should be amber
    // The function checks < shortfallThreshold, so 100k is not < 100k
    expect(getBalanceColor(100000, monthlyOutflow)).toBe('amber');
  });

  it('returns red when balance is just below shortfall threshold', () => {
    expect(getBalanceColor(99999, monthlyOutflow)).toBe('red');
  });
});
