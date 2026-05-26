// src/features/executive/KpiCard.test.tsx
import { render, screen } from '@testing-library/react';
import { KpiCard } from '@components/KpiCard';

test('renders label, value, and delta', () => {
  render(
    <KpiCard
      accent="teal"
      label="Working Capital"
      value="$1.42M"
      delta={{ direction: 'up', text: '+$310K vs prior 30d' }}
    />
  );
  expect(screen.getByText('Working Capital')).toBeInTheDocument();
  expect(screen.getByText('$1.42M')).toBeInTheDocument();
  expect(screen.getByLabelText(/working capital/i)).toBeInTheDocument();
});
