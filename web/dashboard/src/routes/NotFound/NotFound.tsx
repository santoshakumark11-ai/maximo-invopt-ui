import { Link } from 'react-router-dom';
import { Button } from '@carbon/react';
import styles from './NotFound.module.scss';

export function NotFound() {
  return (
    <div className={styles.wrapper} data-testid="not-found">
      <h1 className={styles.code}>404</h1>
      <p className={styles.title}>Page not found</p>
      <p className={styles.description}>The page you are looking for does not exist.</p>
      <Button as={Link} to="/" kind="primary">
        Go to dashboard
      </Button>
    </div>
  );
}
