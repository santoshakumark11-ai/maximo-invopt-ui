/**
 * KpiCard — single metric tile used in the KPI strip.
 *
 * Props:
 *   label       — metric name shown above the value
 *   value       — formatted string (e.g. "$1.3M")
 *   description — optional tooltip / sub-label
 *   accent      — left-border colour: 'teal' | 'navy' | 'gold' | 'red'
 *   loading     — shows Carbon skeleton when true
 *   error       — shows an error message instead of the value
 */
import { SkeletonText } from '@carbon/react';
import styles from './KpiCard.module.scss';
import clsx from 'clsx';

export type KpiAccent = 'teal' | 'navy' | 'gold' | 'red';

interface KpiCardProps {
  label: string;
  value?: string | undefined;
  description?: string | undefined;
  accent?: KpiAccent;
  loading?: boolean;
  error?: string | undefined;
}

export function KpiCard({
  label,
  value,
  description,
  accent = 'teal',
  loading = false,
  error,
}: KpiCardProps) {
  return (
    <div className={clsx(styles.card, styles[`accent-${accent}`])} data-testid="kpi-card">
      <p className={styles.label}>{label}</p>

      {loading ? (
        <SkeletonText className={styles.skeleton ?? ''} />
      ) : error ? (
        <p className={styles.error}>{error}</p>
      ) : (
        <p className={styles.value}>{value ?? '—'}</p>
      )}

      {description && !loading && !error && <p className={styles.description}>{description}</p>}
    </div>
  );
}
