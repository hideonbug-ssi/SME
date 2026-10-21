import { describe, it, expect } from 'vitest';
import { formatDate, formatDateTime, daysOverdue, isToday, relativeTime } from './dates';

describe('formatDate', () => {
  it('formats ISO date string to readable format', () => {
    expect(formatDate('2026-07-14')).toBe('14 Jul 2026');
  });

  it('handles month boundary correctly', () => {
    expect(formatDate('2026-01-01')).toBe('01 Jan 2026');
  });

  it('returns original string for invalid date', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });

  it('formats end of year date', () => {
    expect(formatDate('2026-12-31')).toBe('31 Dec 2026');
  });
});

describe('formatDateTime', () => {
  it('formats ISO datetime string', () => {
    const result = formatDateTime('2026-07-14T10:30:00Z');
    expect(result).toContain('2026');
    expect(result).toContain('Jul');
  });

  it('returns original string for invalid datetime', () => {
    expect(formatDateTime('invalid')).toBe('invalid');
  });
});

describe('daysOverdue', () => {
  it('returns 0 for invoices not yet due (future date)', () => {
    expect(daysOverdue('2026-07-20')).toBe(0);
  });

  it('returns 0 for invoices due today', () => {
    expect(daysOverdue('2026-07-14')).toBe(0);
  });

  it('calculates 5 days overdue for INV-001 scenario', () => {
    expect(daysOverdue('2026-07-09')).toBe(5);
  });

  it('calculates 45 days overdue for INV-004 scenario', () => {
    expect(daysOverdue('2026-05-30')).toBe(45);
  });

  it('calculates 95 days overdue for INV-005 scenario', () => {
    expect(daysOverdue('2026-04-10')).toBe(95);
  });

  it('returns 0 for invalid date', () => {
    expect(daysOverdue('invalid')).toBe(0);
  });
});

describe('isToday', () => {
  it('returns true for today (2026-07-14)', () => {
    expect(isToday('2026-07-14')).toBe(true);
  });

  it('returns false for a past date', () => {
    expect(isToday('2026-07-13')).toBe(false);
  });

  it('returns false for a future date', () => {
    expect(isToday('2026-07-15')).toBe(false);
  });

  it('returns false for empty string', () => {
    expect(isToday('')).toBe(false);
  });

  it('returns false for invalid string', () => {
    expect(isToday('not-a-date')).toBe(false);
  });
});

describe('relativeTime', () => {
  it('returns "just now" for very recent timestamps', () => {
    expect(relativeTime('2026-07-14T12:00:00Z')).toBe('just now');
  });

  it('returns minutes for timestamps within the hour', () => {
    expect(relativeTime('2026-07-14T11:30:00Z')).toBe('30 minutes ago');
  });

  it('returns hours for timestamps within the day', () => {
    expect(relativeTime('2026-07-14T06:00:00Z')).toBe('6 hours ago');
  });

  it('returns days for older timestamps', () => {
    expect(relativeTime('2026-07-11T12:00:00Z')).toBe('3 days ago');
  });

  it('uses singular for 1 minute', () => {
    expect(relativeTime('2026-07-14T11:59:00Z')).toBe('1 minute ago');
  });

  it('uses singular for 1 hour', () => {
    expect(relativeTime('2026-07-14T11:00:00Z')).toBe('1 hour ago');
  });

  it('uses singular for 1 day', () => {
    expect(relativeTime('2026-07-13T12:00:00Z')).toBe('1 day ago');
  });
});
