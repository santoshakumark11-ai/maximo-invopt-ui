/**
 * Locale-aware formatting helpers for Phase 1.
 * All formatters are pure functions — safe to use in tests without a DOM.
 */

const DEFAULT_LOCALE = 'en-US';

// ─── Currency ────────────────────────────────────────────────────────────────

/**
 * Format a USD value with compact suffix for large numbers.
 * e.g. 1_250_000 → "$1.3M"   |   45_000 → "$45K"   |   999 → "$999"
 */
export function formatCurrency(value: number, locale: string = DEFAULT_LOCALE): string {
  if (Math.abs(value) >= 1_000_000) {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  }
  if (Math.abs(value) >= 1_000) {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 0,
    }).format(value);
  }
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Full currency, no compaction — for detail rows where precision matters.
 * e.g. 1_250_000 → "$1,250,000"
 */
export function formatCurrencyFull(value: number, locale: string = DEFAULT_LOCALE): string {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}

// ─── Percentage ──────────────────────────────────────────────────────────────

/**
 * Format a 0-100 percentage value.
 * e.g. 97.5 → "97.5%"   |   100 → "100%"
 */
export function formatPercent(
  value: number,
  fractionDigits = 1,
  locale: string = DEFAULT_LOCALE
): string {
  return (
    new Intl.NumberFormat(locale, {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }).format(value) + '%'
  );
}

/**
 * Format WAPE (0-100) — always 1 decimal place.
 * Positive bias gets a "+" prefix so sign is visible at a glance.
 */
export function formatWape(value: number, locale: string = DEFAULT_LOCALE): string {
  return formatPercent(value, 1, locale);
}

export function formatBias(value: number, locale: string = DEFAULT_LOCALE): string {
  const abs = formatPercent(Math.abs(value), 1, locale);
  return value >= 0 ? `+${abs}` : `-${abs}`;
}

// ─── Numbers ─────────────────────────────────────────────────────────────────

/**
 * Integer with thousands separator.
 * e.g. 1234 → "1,234"
 */
export function formatInteger(value: number, locale: string = DEFAULT_LOCALE): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value);
}

// ─── Dates ───────────────────────────────────────────────────────────────────

/**
 * Short month+year label for chart axes.
 * e.g. "2024-01" → "Jan 24"
 */
export function formatPeriodLabel(isoMonth: string, locale: string = DEFAULT_LOCALE): string {
  const [year, month] = isoMonth.split('-').map(Number);
  const date = new Date(year, month - 1, 1);
  return new Intl.DateTimeFormat(locale, { month: 'short', year: '2-digit' }).format(date);
}

/**
 * Full date string for tooltips.
 * e.g. new Date("2024-01-15") → "Jan 15, 2024"
 */
export function formatDate(date: Date | string, locale: string = DEFAULT_LOCALE): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat(locale, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(d);
}
