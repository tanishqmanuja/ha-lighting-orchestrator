import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

/**
 * Minimal shadcn-style primitives for the HALO panel.
 * Same API spirit as shadcn/ui (variants, focus rings, design tokens)
 * without the Tailwind dependency — HA panels must ship one self-
 * contained file that also works inside shadow DOM.
 */

type ButtonVariant =
  | "default"
  | "secondary"
  | "outline"
  | "ghost"
  | "destructive";
type ButtonSize = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function Button({
  variant = "outline",
  size = "md",
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      className={["btn", `btn-${variant}`, `btn-${size}`, className]
        .filter(Boolean)
        .join(" ")}
      {...props}
    />
  );
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean;
}

export function Input({ mono, className = "", ...props }: InputProps) {
  return (
    <input
      className={["input", mono ? "mono" : "", className]
        .filter(Boolean)
        .join(" ")}
      {...props}
    />
  );
}

export function Select({
  className = "",
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={["select", className].filter(Boolean).join(" ")} {...props}>
      {children}
    </select>
  );
}

export function Switch({
  checked,
  onCheckedChange,
  label,
}: {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={["switch", checked ? "on" : ""].join(" ")}
      onClick={() => onCheckedChange(!checked)}
    >
      <span className="thumb" />
    </button>
  );
}

export function Badge({
  tone = "neutral",
  dot = false,
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "drift";
  dot?: boolean;
  children: ReactNode;
}) {
  return (
    <span className={`badge tone-${tone}${dot ? " has-dot" : ""}`}>
      {children}
    </span>
  );
}

export function Card({
  className = "",
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <section className={["card", className].filter(Boolean).join(" ")}>{children}</section>;
}

export function CardHeader({ children }: { children: ReactNode }) {
  return <header className="card-head">{children}</header>;
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <h3 className="card-title">{children}</h3>;
}

export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={["field", className].filter(Boolean).join(" ")}>
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </div>
  );
}

export function Alert({
  tone,
  children,
}: {
  tone: "error" | "success" | "info";
  children: ReactNode;
}) {
  return <p className={`alert tone-${tone}`}>{children}</p>;
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => (
        <span key={i} />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <p className="empty-title">{title}</p>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}

export function Divider({ className = "" }: { className?: string }) {
  return <hr className={["divider", className].filter(Boolean).join(" ")} />;
}
