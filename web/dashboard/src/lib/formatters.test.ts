/**
 * Formatter utility unit tests.
 */
import { describe, it, expect } from 'vitest';
import {
  formatCurrency,
  formatCurrencyFull,
  formatPercent,
  formatWape,
  formatBias,
  formatInteger,
  formatPeriodLabel,
} from './formatters';

describe('formatCurrency', () => {
  it('formats millions with compact suffix', () => {
    expect(formatCurrency(1_250_000)).toBe('$1.3M');
  });

  it('formats thousands with compact suffix', () => {
    expect(formatCurrency(45_000)).toBe('$45K');
  });

  it('formats sub-thousand values without suffix', () => {
    expect(formatCurrency(999)).toBe('$999');
  });
});

describe('formatCurrencyFull', () => {
  it('formats with thousands separator and no suffix', () => {
    expect(formatCurrencyFull(1_250_000)).toBe('$1,250,000');
  });
});

describe('formatPercent', () => {
  it('formats with one decimal by default', () => {
    expect(formatPercent(97.4)).toBe('97.4%');
  });

  it('formats 100 correctly', () => {
    expect(formatPercent(100)).toBe('100.0%');
  });
});

describe('formatWape', () => {
  it('always shows one decimal place', () => {
    expect(formatWape(8.2)).toBe('8.2%');
  });
});

describe('formatBias', () => {
  it('prefixes positive values with +', () => {
    expect(formatBias(2.1)).toBe('+2.1%');
  });

  it('prefixes negative values with -', () => {
    expect(formatBias(-3.4)).toBe('-3.4%');
  });
});

describe('formatInteger', () => {
  it('adds thousands separator', () => {
    expect(formatInteger(1234)).toBe('1,234');
  });
});

describe('formatPeriodLabel', () => {
  it('converts ISO month to short label', () => {
    expect(formatPeriodLabel('2024-01')).toBe('Jan 24');
  });
});
