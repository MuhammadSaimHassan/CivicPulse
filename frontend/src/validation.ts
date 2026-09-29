/**
 * Client-side validation that MIRRORS the server's rules without replacing
 * them. The limits are read from the backend's OpenAPI schema at build time,
 * so there is one source of truth: change a max_length in app/schemas.py,
 * regenerate openapi.json, and the form follows. The server still validates
 * everything; this only saves the citizen a round trip.
 */
import openapi from "../openapi.json";

interface StringRule {
  minLength?: number;
  maxLength?: number;
}

type ComplaintCreateSchema = { properties: Record<string, StringRule & { anyOf?: StringRule[] }> };

const props = (openapi.components.schemas.ComplaintCreate as unknown as ComplaintCreateSchema).properties;

function rule(name: string): StringRule {
  const p = props[name];
  if (!p) return {};
  // Optional fields are `anyOf: [{type: string, maxLength}, {type: null}]`.
  return p.anyOf ? (p.anyOf.find((a) => a.maxLength !== undefined) ?? {}) : p;
}

export const LIMITS = {
  text: rule("text"),
  location: rule("location"),
  reporter_contact: rule("reporter_contact"),
} as const;

export interface FormValues {
  text: string;
  location: string;
  reporter_contact: string;
}

export type FormErrors = Partial<Record<keyof FormValues, string>>;

function checkLength(label: string, value: string, r: StringRule): string | undefined {
  const len = value.trim().length;
  if (r.minLength !== undefined && len < r.minLength) return `${label} must be at least ${r.minLength} characters.`;
  if (r.maxLength !== undefined && len > r.maxLength) return `${label} must be at most ${r.maxLength} characters.`;
  return undefined;
}

export function validate(values: FormValues): FormErrors {
  const errors: FormErrors = {};
  const text = checkLength("Complaint", values.text, LIMITS.text);
  const location = checkLength("Location", values.location, LIMITS.location);
  const contact = values.reporter_contact.trim()
    ? checkLength("Contact", values.reporter_contact, LIMITS.reporter_contact)
    : undefined;
  if (text) errors.text = text;
  if (location) errors.location = location;
  if (contact) errors.reporter_contact = contact;
  return errors;
}
