/**
 * KpiCard unit tests.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { KpiCard } from './KpiCard';

describe('KpiCard', () => {
  it('renders label and value', () => {
    render(<KpiCard label="Inventory Value" value="$4.8M" />);
    expect(screen.getByText('Inventory Value')).toBeInTheDocument();
    expect(screen.getByText('$4.8M')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(<KpiCard label="Service Level" value="97.4%" description="Demand met from stock" />);
    expect(screen.getByText('Demand met from stock')).toBeInTheDocument();
  });

  it('shows skeleton when loading', () => {
    const { container } = render(<KpiCard label="Working Capital" loading />);
    // Carbon SkeletonText renders a span with bx--skeleton__text class
    expect(container.querySelector('[class*="skeleton"]')).toBeTruthy();
    // Value should NOT appear
    expect(screen.queryByText('—')).toBeNull();
  });

  it('shows error message when error is set', () => {
    render(<KpiCard label="Open Recommendations" error="Unable to load" />);
    expect(screen.getByText('Unable to load')).toBeInTheDocument();
  });

  it('renders fallback dash when value is undefined', () => {
    render(<KpiCard label="KPI" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('applies the correct accent class', () => {
    const { getByTestId } = render(<KpiCard label="KPI" value="42" accent="gold" />);
    const card = getByTestId('kpi-card');
    expect(card.className).toMatch(/accent-gold/);
  });
});
