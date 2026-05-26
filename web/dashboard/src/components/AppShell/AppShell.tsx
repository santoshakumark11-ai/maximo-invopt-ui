/**
 * AppShell — persistent layout wrapping all protected routes.
 *
 * Structure:
 *   Carbon Header (fixed, navy-dk bg + teal border)
 *     └─ Tab bar (navy bg, teal active underline)
 *   <main> content area
 */
import type { ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Header,
  HeaderName,
  HeaderGlobalBar,
  HeaderGlobalAction,
  Tabs,
  Tab,
  TabList,
} from '@carbon/react';
import { Logout } from '@carbon/icons-react';
import { useAuth } from '@/auth/AuthProvider';
import styles from './AppShell.module.scss';

interface Props {
  children: ReactNode;
}

interface TabDef {
  label: string;
  path: string;
  /** Match this prefix for "active" detection (handles sub-routes) */
  prefix?: string;
}

const TABS: TabDef[] = [
  { label: 'Executive Dashboard', path: '/', prefix: '/' },
  { label: 'Recommendations', path: '/recommendations', prefix: '/recommendations' },
];

export function AppShell({ children }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, user } = useAuth();

  // Determine the active tab index
  const activeIndex = (() => {
    // Find the most-specific match first
    const sorted = [...TABS]
      .map((t, i) => ({ ...t, i }))
      .sort((a, b) => (b.prefix ?? b.path).length - (a.prefix ?? a.path).length);
    for (const t of sorted) {
      const prefix = t.prefix ?? t.path;
      if (prefix === '/' ? location.pathname === '/' : location.pathname.startsWith(prefix)) {
        return t.i;
      }
    }
    return 0;
  })();

  return (
    <>
      {/* ── Fixed header ─────────────────────────────────────────────────── */}
      <Header aria-label="Inventory Optimisation Agent" className={styles.header ?? ''}>
        <HeaderName prefix="">
          <span className={styles.logoText}>Inventory Optimisation Agent</span>
        </HeaderName>

        <HeaderGlobalBar>
          <div className={styles.headerActions}>
            {user?.username && <span>{user.username}</span>}
            <HeaderGlobalAction aria-label="Sign out" tooltipAlignment="end" onClick={logout}>
              <Logout size={20} />
            </HeaderGlobalAction>
          </div>
        </HeaderGlobalBar>
      </Header>

      {/* ── Tab bar ───────────────────────────────────────────────────────── */}
      <div
        className={styles.tabBar}
        style={{ position: 'fixed', top: '3rem', left: 0, right: 0, zIndex: 7999 }}
      >
        <Tabs
          selectedIndex={activeIndex}
          onChange={({ selectedIndex }) => {
            const tab = TABS[selectedIndex];
            if (tab) navigate(tab.path);
          }}
        >
          <TabList aria-label="Main navigation" contained={false}>
            {TABS.map((t) => (
              <Tab key={t.path}>{t.label}</Tab>
            ))}
          </TabList>
        </Tabs>
      </div>

      {/* ── Page content ─────────────────────────────────────────────────── */}
      <main className={styles.shell}>{children}</main>
    </>
  );
}
