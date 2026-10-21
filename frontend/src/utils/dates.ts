/**
 * Formats an ISO date string as a human-readable date.
 * Example: formatDate("2026-07-14") → "14 Jul 2026"
 */
export function formatDate(isoDate: string): string {
  const date = new Date(isoDate);
  if (isNaN(date.getTime())) return isoDate;
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Formats an ISO datetime string as a human-readable datetime.
 * Example: formatDateTime("2026-07-14T10:30:00Z") → "14 Jul 2026, 10:30"
 */
export function formatDateTime(isoDatetime: string): string {
  const date = new Date(isoDatetime);
  if (isNaN(date.getTime())) return isoDatetime;
  return date.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Calculates the number of days overdue from a due date string.
 * Uses 2026-07-14 as the demo "today".
 */
export function daysOverdue(dueDateStr: string): number {
  const today = new Date('2026-07-14');
  const dueDate = new Date(dueDateStr);
  if (isNaN(dueDate.getTime())) return 0;
  const diffMs = today.getTime() - dueDate.getTime();
  return Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
}

/**
 * Checks if a date string is today (2026-07-14 for demo).
 */
export function isToday(dateStr: string): boolean {
  if (!dateStr) return false;
  const date = new Date(dateStr);
  const today = new Date('2026-07-14');
  return (
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate()
  );
}

/**
 * Returns a relative time string for a timestamp.
 * Example: "2 hours ago", "3 days ago"
 */
export function relativeTime(isoDatetime: string): string {
  const date = new Date(isoDatetime);
  const now = new Date('2026-07-14T12:00:00Z');
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMinutes < 1) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
}
