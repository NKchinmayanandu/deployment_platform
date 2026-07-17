import { useState, useCallback } from 'react';
import { Plus, Trash2 } from 'lucide-react';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface EnvVar {
  id: string;          // stable React key (not sent to backend)
  key: string;
  value: string;
}

interface EnvVarsEditorProps {
  /** Controlled value — pass your useState array here */
  vars: EnvVar[];
  /** Setter forwarded from the parent's useState */
  onChange: (vars: EnvVar[]) => void;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Creates a blank row with a unique stable id */
function createRow(): EnvVar {
  return { id: crypto.randomUUID(), key: '', value: '' };
}

/**
 * Converts the editor state to a plain JSON object suitable for a POST body.
 *
 * @example
 *   const payload = toEnvObject(vars);
 *   // => { "PORT": "8080", "DEBUG": "true" }
 */
/**
 * Sanitises an env var key:
 *   - trims surrounding whitespace
 *   - strips any trailing `=` characters
 *     (guards against users typing "DATABASE_URL=" as if it were a .env line)
 */
function sanitiseKey(raw: string): string {
  return raw.trim().replace(/=+$/, '').toUpperCase();
}

export function toEnvObject(vars: EnvVar[]): Record<string, string> {
  return Object.fromEntries(
    vars
      .filter((v) => sanitiseKey(v.key) !== '')          // skip blank keys
      .map((v) => [sanitiseKey(v.key), v.value.trim()])
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

export function EnvVarsEditor({ vars, onChange }: EnvVarsEditorProps) {
  const addRow = useCallback(() => {
    onChange([...vars, createRow()]);
  }, [vars, onChange]);

  const removeRow = useCallback(
    (id: string) => {
      onChange(vars.filter((v) => v.id !== id));
    },
    [vars, onChange]
  );

  const updateField = useCallback(
    (id: string, field: 'key' | 'value', text: string) => {
      // Sanitise keys on input so trailing `=` is stripped live.
      // Values are kept verbatim (they may contain `=`, e.g. base64 tokens).
      const sanitised = field === 'key' ? sanitiseKey(text) : text;
      onChange(vars.map((v) => (v.id === id ? { ...v, [field]: sanitised } : v)));
    },
    [vars, onChange]
  );

  return (
    <div className="flex flex-col gap-3">
      {/* ── Section header ── */}
      <div className="flex items-center justify-between">
        <span className="section-label">Environment Variables</span>
        <button
          type="button"
          id="env-add-row"
          onClick={addRow}
          className="btn-ghost h-8 px-2.5 text-[12px] gap-1.5"
        >
          <Plus size={13} strokeWidth={2.2} />
          Add Row
        </button>
      </div>

      {/* ── Table ── */}
      {vars.length > 0 ? (
        <div className="rounded-lg border border-hairline overflow-hidden">
          {/* Column headers */}
          <div className="grid grid-cols-[1fr_1fr_36px] bg-surface-strong border-b border-hairline px-3 py-2">
            <span className="section-label">Key</span>
            <span className="section-label">Value</span>
            <span />
          </div>

          {/* Rows */}
          <div className="divide-y divide-hairline">
            {vars.map((v, index) => (
              <div
                key={v.id}
                className="grid grid-cols-[1fr_1fr_36px] items-center px-2 py-1.5 gap-2 bg-surface-card transition-colors hover:bg-canvas group"
              >
                {/* Key input */}
                <input
                  id={`env-key-${index}`}
                  type="text"
                  className="input h-9 font-mono text-[13px] uppercase tracking-wide px-3"
                  placeholder="API_KEY"
                  value={v.key}
                  onChange={(e) => updateField(v.id, 'key', e.target.value)}
                  aria-label={`Environment variable key ${index + 1}`}
                  spellCheck={false}
                  autoComplete="off"
                />

                {/* Value input */}
                <input
                  id={`env-value-${index}`}
                  type="text"
                  className="input h-9 font-mono text-[13px] px-3"
                  placeholder="your-secret-value"
                  value={v.value}
                  onChange={(e) => updateField(v.id, 'value', e.target.value)}
                  aria-label={`Environment variable value ${index + 1}`}
                  spellCheck={false}
                  autoComplete="off"
                />

                {/* Delete button */}
                <button
                  type="button"
                  id={`env-delete-${index}`}
                  onClick={() => removeRow(v.id)}
                  className="btn-ghost-danger w-9 h-9 p-0 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                  aria-label={`Remove row ${index + 1}`}
                >
                  <Trash2 size={14} strokeWidth={2} />
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* Empty state */
        <button
          type="button"
          id="env-empty-add"
          onClick={addRow}
          className="w-full rounded-lg border border-dashed border-hairline-strong py-5 flex flex-col items-center gap-1.5 text-muted hover:border-ink hover:text-ink hover:bg-surface-strong transition-colors duration-150"
        >
          <Plus size={18} strokeWidth={1.8} />
          <span className="text-body-sm font-medium">Add environment variable</span>
        </button>
      )}

      {/* Row count hint */}
      {vars.length > 0 && (
        <p className="text-[11px] text-muted leading-none">
          {vars.length} variable{vars.length !== 1 ? 's' : ''} · blank keys are ignored
        </p>
      )}
    </div>
  );
}

// ─── Standalone hook (optional) ──────────────────────────────────────────────

/**
 * Convenience hook when you need the full editor state + serialiser in one call.
 *
 * @example
 *   const { vars, setVars, toJSON } = useEnvVars();
 *   // pass vars + setVars to <EnvVarsEditor />, then call toJSON() in onSubmit
 */
export function useEnvVars(initial: EnvVar[] = []) {
  const [vars, setVars] = useState<EnvVar[]>(initial);
  const toJSON = useCallback(() => toEnvObject(vars), [vars]);
  return { vars, setVars, toJSON } as const;
}
