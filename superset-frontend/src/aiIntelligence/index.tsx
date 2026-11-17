/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements. See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership. The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License. You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import 'src/public-path';

import { logging } from '@apache-superset/core/utils';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import initPreamble from 'src/preamble';
import { makeUrl } from 'src/utils/pathUtils';
import './styles.css';

interface AppliedFilter {
  column: string;
  value: string;
}

interface ChartReference {
  id: number;
  name: string;
  url: string;
}

interface ChartSuggestion {
  id: number;
  name: string;
  dataset: string;
  description: string;
  viz_type: string;
  confidence: number;
  matched_terms: string[];
}

interface QueryResponse {
  needs_clarification?: boolean;
  message?: string;
  error?: string;
  chart?: ChartReference;
  filters?: AppliedFilter[];
  columns?: string[];
  rows?: Array<Record<string, unknown>>;
  suggestions?: ChartSuggestion[];
}

interface ProcessStep {
  id: string;
  label: string;
  status: 'active' | 'complete' | 'failed';
  detail?: string;
}

interface StreamEvent {
  type: 'progress' | 'result' | 'error';
  steps?: ProcessStep[];
  result?: QueryResponse;
  error?: string;
}

interface ConversationEntry {
  id: number;
  role: 'assistant' | 'user';
  text: string;
  originalQuestion?: string;
  result?: QueryResponse;
  steps?: ProcessStep[];
}

function displayCell(value: unknown): string {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  return JSON.stringify(value) ?? String(value);
}

function ResultTable({ result }: { result: QueryResponse }) {
  const columns = result.columns ?? [];
  const rows = result.rows ?? [];
  if (!columns.length || !rows.length) {
    return <p className="ai-empty-result">No rows matched those filters.</p>;
  }
  return (
    <div className="ai-table-scroll">
      <table className="ai-result-table">
        <thead>
          <tr>
            {columns.map(column => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map(column => (
                <td key={column}>{displayCell(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AssistantResponse({
  result,
  onSelectChart,
  busy,
}: {
  result: QueryResponse;
  onSelectChart: (suggestion: ChartSuggestion) => void;
  busy: boolean;
}) {
  if (result.error) {
    return <p className="ai-error">{result.error}</p>;
  }
  if (result.needs_clarification) {
    return (
      <div>
        <p>{result.message}</p>
        {result.suggestions?.length ? (
          <div>
            <p className="ai-suggestion-note">
              Match confidence is estimated from overlapping request and chart
              keywords; it is a ranking score, not a probability.
            </p>
            <ul className="ai-suggestions">
              {result.suggestions.map(suggestion => (
                <li key={suggestion.id}>
                  <button
                    type="button"
                    className="ai-suggestion-button"
                    disabled={busy}
                    onClick={() => onSelectChart(suggestion)}
                  >
                    <span className="ai-suggestion-heading">
                      <strong>{suggestion.name}</strong>
                      <span>{suggestion.confidence}% match</span>
                    </span>
                    <span className="ai-suggestion-detail">
                      Chart ID: {suggestion.id} · Dataset:{' '}
                      {suggestion.dataset || 'Not specified'}
                      {suggestion.viz_type
                        ? ` · Visualization: ${suggestion.viz_type}`
                        : ''}
                    </span>
                    {suggestion.description ? (
                      <span className="ai-suggestion-detail">
                        {suggestion.description}
                      </span>
                    ) : null}
                    {suggestion.matched_terms.length ? (
                      <span className="ai-suggestion-detail">
                        Matching terms: {suggestion.matched_terms.join(', ')}
                      </span>
                    ) : null}
                    <span className="ai-suggestion-action">Use this chart</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    );
  }
  if (!result.chart) {
    return <p className="ai-error">The response did not include a chart.</p>;
  }
  const appliedFilters = result.filters?.length
    ? ` Filters: ${result.filters
        .map(filter => `${filter.column} = ${filter.value}`)
        .join(', ')}.`
    : '';
  return (
    <div>
      <p className="ai-result-summary">
        Showing results from{' '}
        <a href={result.chart.url}>{result.chart.name}</a>.
        {appliedFilters}
      </p>
      <ResultTable result={result} />
    </div>
  );
}

function ProcessTimeline({ steps }: { steps: ProcessStep[] }) {
  if (!steps.length) {
    return null;
  }
  return (
    <ol className="ai-process" aria-label="Request process">
      {steps.map(step => (
        <li
          className={`ai-process-step ai-process-${step.status}`}
          key={step.id}
        >
          <span className="ai-process-indicator" aria-hidden="true">
            {step.status === 'complete'
              ? '✓'
              : step.status === 'failed'
                ? '!'
                : '…'}
          </span>
          <div>
            <span className="ai-process-label">{step.label}</span>
            {step.detail ? (
              <span className="ai-process-detail">{step.detail}</span>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

function App() {
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [entries, setEntries] = useState<ConversationEntry[]>([
    {
      id: 0,
      role: 'assistant',
      text: 'Ask a question about a saved chart. I will match it to a chart you can access and show the data with supported filters.',
    },
  ]);

  async function runQuery(
    submittedQuestion: string,
    selectedChart?: ChartSuggestion,
    userMessage = submittedQuestion,
  ) {
    if (!submittedQuestion || busy) {
      return;
    }

    setQuestion('');
    setBusy(true);
    const responseId = Date.now();
    setEntries(previous => [
      ...previous,
      { id: responseId - 1, role: 'user', text: userMessage },
      {
        id: responseId,
        role: 'assistant',
        text: '',
        originalQuestion: submittedQuestion,
        steps: [
          {
            id: 'request',
            label: 'Sending your request securely',
            status: 'active',
          },
        ],
      },
    ]);

    try {
      const csrfToken =
        document.querySelector<HTMLInputElement>('#csrf_token')?.value ?? '';
      const response = await fetch(
        makeUrl('/api/v1/moh/ai-intelligence/query'),
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({
            question: submittedQuestion,
            ...(selectedChart ? { selected_chart_id: selectedChart.id } : {}),
          }),
        },
      );
      if (!response.ok) {
        const errorBody = (await response.json().catch(() => ({}))) as {
          error?: string;
          message?: string;
        };
        throw new Error(
          errorBody.error ??
            errorBody.message ??
            `Request failed (${response.status}).`,
        );
      }

      const contentType = response.headers.get('content-type') ?? '';
      if (!contentType.includes('application/x-ndjson') || !response.body) {
        throw new Error('The server did not start the progress stream.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let receivedFinalEvent = false;
      const handleEvent = (line: string) => {
        if (!line.trim()) {
          return;
        }
        const event = JSON.parse(line) as StreamEvent;
        if (event.type === 'progress' && event.steps) {
          setEntries(previous =>
            previous.map(entry =>
              entry.id === responseId ? { ...entry, steps: event.steps } : entry,
            ),
          );
        } else if (event.type === 'result' && event.result) {
          receivedFinalEvent = true;
          setEntries(previous =>
            previous.map(entry =>
              entry.id === responseId
                ? {
                    ...entry,
                    text: '',
                    result: event.result,
                  }
                : entry,
            ),
          );
        } else if (event.type === 'error') {
          receivedFinalEvent = true;
          setEntries(previous =>
            previous.map(entry =>
              entry.id === responseId
                ? {
                    ...entry,
                    text: '',
                    result: {
                      error:
                        event.error ?? 'The request could not be completed.',
                    },
                  }
                : entry,
            ),
          );
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        lines.forEach(handleEvent);
        if (done) {
          if (buffer.trim()) {
            handleEvent(buffer);
          }
          break;
        }
      }
      if (!receivedFinalEvent) {
        throw new Error('The progress stream ended before returning a result.');
      }
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'The request could not be completed.';
      setEntries(previous =>
        previous.map(entry =>
          entry.id === responseId
            ? {
                ...entry,
                text: '',
                result: { error: message },
                steps: entry.steps?.map(step =>
                  step.status === 'active'
                    ? { ...step, status: 'failed', detail: message }
                    : step,
                ),
              }
            : entry,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runQuery(question.trim());
  }

  function selectChart(
    originalQuestion: string | undefined,
    suggestion: ChartSuggestion,
  ) {
    if (!originalQuestion) {
      return;
    }
    const dataset = suggestion.dataset ? ` (${suggestion.dataset})` : '';
    void runQuery(
      originalQuestion,
      suggestion,
      `Use chart: ${suggestion.name}${dataset}`,
    );
  }

  return (
    <section className="ai-shell" aria-label="AI Intelligence assistant">
      <div className="ai-heading">
        <h1>AI Intelligence</h1>
        <p>
          Ask in plain language. Results come from saved charts you are
          authorized to access.
        </p>
      </div>
      <div className="ai-conversation" aria-live="polite">
        {entries.map(entry => (
          <article
            className={`ai-message ai-message-${entry.role}`}
            key={entry.id}
          >
            <strong>{entry.role === 'user' ? 'You' : 'AI Intelligence'}</strong>
            {entry.text ? <p>{entry.text}</p> : null}
            {entry.steps ? <ProcessTimeline steps={entry.steps} /> : null}
            {entry.result ? (
              <AssistantResponse
                result={entry.result}
                busy={busy}
                onSelectChart={suggestion =>
                  selectChart(entry.originalQuestion, suggestion)
                }
              />
            ) : null}
          </article>
        ))}
        {busy ? (
          <p className="ai-loading">Finding a chart and querying data…</p>
        ) : null}
      </div>
      <form className="ai-composer" onSubmit={submitQuestion}>
        <label className="ai-visually-hidden" htmlFor="ai-question">
          Your question
        </label>
        <input
          id="ai-question"
          value={question}
          onChange={event => setQuestion(event.target.value)}
          placeholder="e.g. Show ANC coverage by region for 2024"
          maxLength={2000}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !question.trim()}>
          Ask
        </button>
      </form>
    </section>
  );
}

const mountPoint = document.getElementById('app');
if (mountPoint) {
  const root = createRoot(mountPoint);
  initPreamble()
    .catch(error => {
      logging.error('Failed to initialize AI Intelligence', error);
    })
    .finally(() => root.render(<App />));
}
