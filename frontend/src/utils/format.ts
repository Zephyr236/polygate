/**
 * Display formatting helpers for the dashboard.
 */

/** Format a ratio between 0 and 1 as a percent string. */
export function percent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** Format milliseconds into a compact latency string. */
export function latency(value: number): string {
  if (value <= 0) return "—";
  return value >= 1000 ? `${(value / 1000).toFixed(2)}s` : `${Math.round(value)}ms`;
}

/** Format a token count with thousands separators. */
export function tokens(value: number): string {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

/** Format a USD amount with six decimals for tiny costs. */
export function usd(value: number): string {
  if (value === 0) return "$0";
  return value < 0.01 ? `$${value.toFixed(6)}` : `$${value.toFixed(4)}`;
}

/** Format a UNIX timestamp as a local clock time. */
export function clockTime(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleTimeString();
}

/** Format a UNIX timestamp as a local date and time. */
export function calendarTime(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleString();
}
