/**
 * ChatPanel — Q2.2 "Ask the planner" chat surface.
 *
 * Renders on the RecommendationDetail page.  The planner types a question,
 * the API gathers context (rec + forecast + substitutes), the LLM answers.
 *
 * No streaming for Q2 — request/response only.  Errors are surfaced inline.
 */
import { useState } from 'react';
import { Button, TextArea, InlineLoading, InlineNotification, Tag } from '@carbon/react';
import { Chat, Send } from '@carbon/icons-react';
import { apiClient } from '@/api/client';
import styles from './ChatPanel.module.scss';

interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatResponse {
  reply: string;
  recId: string;
}

interface Props {
  recId: string;
}

const SUGGESTED = [
  'Why is the ROP this number?',
  'Show me the 12-month consumption.',
  'What if I set β to 0.95?',
  'Are there any substitute items I should consider?',
];

export function ChatPanel({ recId }: Props) {
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(message: string) {
    if (!message.trim()) return;
    const userTurn: ChatTurn = { role: 'user', content: message };
    setHistory((prev) => [...prev, userTurn]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const resp = await apiClient.post<ChatResponse>(`/recommendations/${recId}/chat`, {
        message,
        history: history.map((t) => ({ role: t.role, content: t.content })),
      });
      setHistory((prev) => [...prev, { role: 'assistant', content: resp.reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chat failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={styles.panel} aria-label="Ask the planner">
      <header className={styles.header}>
        <Chat size={20} />
        <h3 className={styles.title}>Ask the planner</h3>
        <Tag type="teal" size="sm">
          AI
        </Tag>
      </header>

      <div className={styles.transcript} aria-live="polite">
        {history.length === 0 && (
          <div className={styles.empty}>
            <p>Ask anything about this recommendation. Try:</p>
            <div className={styles.suggestions}>
              {SUGGESTED.map((s) => (
                <button key={s} className={styles.suggestion} onClick={() => send(s)}>
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

        {loading && <InlineLoading description="Thinking..." status="active" />}
        {error && (
          <InlineNotification kind="error" title="Chat failed" subtitle={error} lowContrast />
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
          placeholder="Ask about this recommendation..."
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
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
          type="submit"
          disabled={loading || !input.trim()}
        >
          Send
        </Button>
      </form>
    </section>
  );
}
