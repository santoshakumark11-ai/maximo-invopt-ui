/**
 * Thin wrapper around react-intl's IntlProvider.
 * Loads en-US messages by default; extend here when more locales are added.
 */
import { type ReactNode } from 'react';
import { IntlProvider as ReactIntlProvider } from 'react-intl';
import enUS from './messages/en-US.json';

interface Props {
  children: ReactNode;
  locale?: string;
}

const MESSAGES: Record<string, Record<string, string>> = {
  'en-US': enUS,
  en: enUS,
};

export function IntlProvider({ children, locale }: Props) {
  // Resolve locale: explicit prop → browser → fallback
  const resolvedLocale =
    locale ?? (typeof navigator !== 'undefined' ? navigator.language : 'en-US');

  const messages = MESSAGES[resolvedLocale] ?? MESSAGES['en-US'];

  return (
    <ReactIntlProvider locale={resolvedLocale} defaultLocale="en-US" messages={messages}>
      {children}
    </ReactIntlProvider>
  );
}
