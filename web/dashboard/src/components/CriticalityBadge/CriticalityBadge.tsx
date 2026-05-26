import type { Criticality } from '@/types';
import styles from './CriticalityBadge.module.scss';

const LABELS: Record<Criticality, string> = {
  HIGH: 'High',
  MED: 'Med',
  LOW: 'Low',
};

interface Props {
  criticality: Criticality;
}

export function CriticalityBadge({ criticality }: Props) {
  return (
    <span className={`${styles.badge} ${styles[criticality]}`}>
      {LABELS[criticality] ?? criticality}
    </span>
  );
}
