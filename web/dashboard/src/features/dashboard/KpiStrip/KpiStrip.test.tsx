/**
 * KpiStrip integration tests — renders against the MSW server fixture.
 */
import { type ReactElement } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { KpiStrip } from './KpiStrip';

function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('KpiStrip', () => {
  it('renders four KPI cards', async () => {
    renderWithQuery(<KpiStrip />);
    const cards = await screen.findAllByTestId('kpi-card');
    expect(cards).toHaveLength(4);
  });

  it('displays formatted inventory value from MSW fixture', async () => {
    renderWithQuery(<KpiStrip />);
    // Fixture value: 4_820_000 → "$4.8M"
    await waitFor(() => {
      expect(screen.getByText('$4.8M')).toBeInTheDocument();
    });
  });

  it('displays formatted service level from MSW fixture', async () => {
    renderWithQuery(<KpiStrip />);
    // Fixture: 97.4 → "97.4%"
    await waitFor(() => {
      expect(screen.getByText('97.4%')).toBeInTheDocument();
    });
  });

  it('displays open recommendations count', async () => {
    renderWithQuery(<KpiStrip />);
    // Fixture: 38
    await waitFor(() => {
      expect(screen.getByText('38')).toBeInTheDocument();
    });
  });
});
