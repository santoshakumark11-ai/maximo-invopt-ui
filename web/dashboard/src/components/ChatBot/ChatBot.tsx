/**
 * ChatBot — floating "Ask the planner" assistant.
 *
 * Mounted in AppShell so it persists across route changes.  Rendered
 * collapsed by default as a FAB at the bottom-left of the viewport;
 * expands to a chat panel on click.
 *
 * Context awareness:
 *   - When the user is on /recommendations/:recId, the URL recId is sent
 *     with each chat call so the LLM has full per-recommendation context.
 *   - On any other route, recId is omitted and the backend gives the LLM
 *     a queue summary so it can answer general questions.
 *
 * Future hook: Maximo MCP.  The backend chat service has a comment marking
 * the tool-calling seam where MCP tool descriptors will plug in.  Once
 * that's wired, the chat bot here doesn't need any changes — it stays a
 * thin transport over the same /v1/chat endpoint.
 */
import { useState, useRef, useEffect } from 'react';
import { useMatch } from 'react-router-dom';
import {
  Button,
  TextArea,
  InlineLoading,
  InlineNotification,
  Tag,
  IconButton,
} from '@carbon/react';
import { Chat, Send, Close, Subtract } from '@carbon/icons-react';
import { apiClient } from '@/api/client';
import styles from './ChatBot.module.scss';

interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatResponse {
  reply: string;
  recId: string | null;
}

const SUGGESTED_GENERAL = [
  'How many open recommendations do I have?',
  'Which items have the largest working-capital release?',
  'Summarise the queue by criticality.',
];

const SUGGESTED_REC_CONTEXT = [
  'Why is the ROP this number?',
  'Show me the 12-month consumption.',
  'What if I set β to 0.95?',
  'Are there substitutes I should consider?',
];

export function ChatBot() {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Route-aware context — extract recId from /recommendations/:recId.
  const detailMatch = useMatch('/recommendations/:recId');
  const recId = detailMatch?.params.recId ?? null;

  const transcriptRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new turn.
  useEffect(() => {
    transcriptRef.current?.scrollTo({
      top: transcriptRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [history, loading]);

  async function send(message: string) {
    if (!message.trim()) return;
    const userTurn: ChatTurn = { role: 'user', content: message };
    setHistory((prev) => [...prev, userTurn]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const resp = await apiClient.post<ChatResponse>('/chat', {
        message,
        rec_id: recId,
        history: history.map((t) => ({ role: t.role, content: t.content })),
      });
      setHistory((prev) => [...prev, { role: 'assistant', content: resp.reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chat failed');
    } finally {
      setLoading(false);
    }
  }

  function resetConversation() {
    setHistory([]);
    setError(null);
    setInput('');
  }

  const suggestions = recId ? SUGGESTED_REC_CONTEXT : SUGGESTED_GENERAL;
  const contextBadge = recId ? `Discussing ${recId}` : 'General assistant';

  // ── Collapsed FAB ────────────────────────────────────────────────────
  if (!open) {
    return (
      <button
        className={styles.fab}
        onClick={() => setOpen(true)}
        aria-label="Open Ask the planner"
        title="Ask the planner"
      >
        <Chat size={20} />
        <span className={styles.fabLabel}>Ask the planner</span>
      </button>
    );
  }

  // ── Expanded panel ───────────────────────────────────────────────────
  return (
    <section className={styles.panel} role="dialog" aria-label="Ask the planner assistant">
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <Chat size={18} />
          <span className={styles.title}>Ask the planner</span>
          <Tag type="teal" size="sm">
            AI
          </Tag>
        </div>
        <div className={styles.headerActions}>
          <IconButton label="Reset conversation" kind="ghost" size="sm" onClick={resetConversation}>
            <Subtract />
          </IconButton>
          <IconButton label="Close" kind="ghost" size="sm" onClick={() => setOpen(false)}>
            <Close />
          </IconButton>
        </div>
      </header>

      <div className={styles.contextRow}>
        <Tag type={recId ? 'cyan' : 'cool-gray'} size="sm">
          {contextBadge}
        </Tag>
      </div>

      <div className={styles.transcript} ref={transcriptRef} aria-live="polite">
        {history.length === 0 && (
          <div className={styles.empty}>
            <p className={styles.emptyHeading}>
              {recId
                ? `Ask anything about recommendation ${recId}.`
                : 'Ask anything about your inventory queue.'}
            </p>
            <div className={styles.suggestions}>
              {suggestions.map((s) => (
                <button key={s} type="button" className={styles.suggestion} onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {history.map((turn, idx) => (
          <div key={idx} className={turn.role === 'user' ? styles.userTurn : styles.assistantTurn}>
            <span className={styles.roleLabel}>{turn.role === 'user' ? 'You' : 'Assistant'}</span>
            <div className={styles.bubble}>{turn.content}</div>
          </div>
        ))}

        {loading && (
          <div className={styles.loadingRow}>
            <InlineLoading description="Thinking..." status="active" />
          </div>
        )}
        {error && (
          <InlineNotification
            kind="error"
            title="Chat failed"
            subtitle={error}
            lowContrast
            hideCloseButton
          />
        )}
      </div>

      <form
        className={styles.composer}
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <TextArea
          labelText=""
          hideLabel
          placeholder={recId ? `Ask about ${recId}...` : 'Ask about your recommendations...'}
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void send(input);
            }
          }}
          disabled={loading}
        />
        <Button
          kind="primary"
          size="md"
          renderIcon={Send}
          iconDescription="Send"
          hasIconOnly
          type="submit"
          disabled={loading || !input.trim()}
        />
      </form>
    </section>
  );
}
