/**
 * PageHeader — top-of-page title + optional subtitle bar.
 * Wraps Carbon's <Header> pattern with minimal custom styling.
 */
import { Header, HeaderName } from '@carbon/react';
import styles from './PageHeader.module.scss';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
}

export function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <div className={styles.wrapper}>
      <Header aria-label={title}>
        <HeaderName prefix="">{title}</HeaderName>
      </Header>
      {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
    </div>
  );
}
