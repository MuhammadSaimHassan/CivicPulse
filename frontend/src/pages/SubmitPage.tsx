import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ApiError, api, type ComplaintCreated } from "../api/client";
import { CategoryTag, PriorityBadge } from "../components/Badges";
import { providerLabel } from "../labels";
import { LIMITS, validate, type FormErrors, type FormValues } from "../validation";

const EMPTY: FormValues = { text: "", location: "", reporter_contact: "" };

export function SubmitPage() {
  const [values, setValues] = useState<FormValues>(EMPTY);
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<ComplaintCreated | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const started = useRef<number>(0);

  // Honest loading state: an LLM call takes seconds, so show that time is
  // passing rather than a spinner that looks the same at 0.2 s and at 9 s.
  useEffect(() => {
    if (!submitting) return;
    started.current = Date.now();
    setElapsed(0);
    const id = window.setInterval(() => setElapsed(Math.floor((Date.now() - started.current) / 1000)), 250);
    return () => window.clearInterval(id);
  }, [submitting]);

  function update(field: keyof FormValues, value: string) {
    setValues((v) => ({ ...v, [field]: value }));
    if (errors[field]) setErrors((e) => ({ ...e, [field]: undefined }));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const clientErrors = validate(values);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length > 0) return;

    setSubmitting(true);
    setResult(null);
    try {
      const created = await api.createComplaint({
        text: values.text.trim(),
        location: values.location.trim(),
        reporter_contact: values.reporter_contact.trim() || null,
      });
      setResult(created);
      setValues(EMPTY);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.fieldErrors.length > 0) {
          const byField: FormErrors = {};
          for (const fe of err.fieldErrors) byField[fe.field as keyof FormValues] = fe.message;
          setErrors(byField);
        }
        setFormError(err.message);
      } else {
        setFormError("Unexpected error. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid-2">
      <section className="panel">
        <h2>Report a problem</h2>
        <p className="muted">Describe it in your own words — English, Urdu or both. We work out the category and urgency.</p>
        <form onSubmit={onSubmit} noValidate aria-busy={submitting}>
          <Field
            id="text"
            label="What is wrong?"
            error={errors.text}
            hint={`${values.text.trim().length} / ${LIMITS.text.maxLength ?? ""}`}
          >
            <textarea
              id="text"
              rows={6}
              value={values.text}
              onChange={(e) => update("text", e.target.value)}
              placeholder="e.g. Burst water main flooding Street 12 since fajr, water entering ground floors"
              aria-invalid={Boolean(errors.text)}
              aria-describedby={errors.text ? "text-error" : undefined}
              disabled={submitting}
            />
          </Field>
          <Field id="location" label="Where?" error={errors.location}>
            <input
              id="location"
              value={values.location}
              onChange={(e) => update("location", e.target.value)}
              placeholder="Street, sector, city"
              aria-invalid={Boolean(errors.location)}
              aria-describedby={errors.location ? "location-error" : undefined}
              disabled={submitting}
            />
          </Field>
          <Field id="reporter_contact" label="Contact (optional)" error={errors.reporter_contact}>
            <input
              id="reporter_contact"
              value={values.reporter_contact}
              onChange={(e) => update("reporter_contact", e.target.value)}
              placeholder="Phone or email, if you want a follow-up"
              aria-invalid={Boolean(errors.reporter_contact)}
              disabled={submitting}
            />
          </Field>
          {formError && (
            <p role="alert" className="alert">
              {formError}
            </p>
          )}
          <button className="btn btn--primary" type="submit" disabled={submitting}>
            {submitting ? "Submitting…" : "Submit complaint"}
          </button>
          {submitting && (
            <p className="loading" role="status" aria-live="polite">
              <span className="spinner" aria-hidden="true" /> Triaging your complaint… {elapsed}s
              {elapsed >= 3 && <span className="muted"> — the AI model can take up to ~10 seconds.</span>}
            </p>
          )}
        </form>
      </section>

      <section className="panel" aria-live="polite">
        <h2>Triage result</h2>
        {!result && <p className="muted">Submit a complaint to see how it was triaged.</p>}
        {result && <TriageResultCard complaint={result} />}
      </section>
    </div>
  );
}

function Field(props: { id: string; label: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <div className={`field ${props.error ? "field--error" : ""}`}>
      <div className="field__head">
        <label htmlFor={props.id}>{props.label}</label>
        {props.hint && <span className="muted small">{props.hint}</span>}
      </div>
      {props.children}
      {props.error && (
        <p id={`${props.id}-error`} className="field__error">
          {props.error}
        </p>
      )}
    </div>
  );
}

function TriageResultCard({ complaint }: { complaint: ComplaintCreated }) {
  const t = complaint.triage;
  return (
    <div className="result" data-testid="triage-result">
      <div className="result__row">
        <CategoryTag value={complaint.category} />
        <PriorityBadge value={complaint.priority} />
      </div>
      <p className="result__summary">{complaint.ai_summary}</p>
      <dl className="kv">
        <dt>Triaged by</dt>
        <dd data-testid="provider">
          {providerLabel(t.provider)}
          {t.fallback && <span className="badge badge--warn">fallback</span>}
          {t.cache_hit && <span className="badge badge--info">cached</span>}
        </dd>
        <dt>Confidence</dt>
        <dd>{Math.round(t.confidence * 100)}%</dd>
        <dt>Triage time</dt>
        <dd>{complaint.triage_latency_ms} ms</dd>
        {t.guardrail_applied && (
          <>
            <dt>Guardrail</dt>
            <dd>Priority raised to high: the text describes a hazard.</dd>
          </>
        )}
        <dt>Reference</dt>
        <dd>
          <code>{complaint.id}</code>
        </dd>
      </dl>
    </div>
  );
}
