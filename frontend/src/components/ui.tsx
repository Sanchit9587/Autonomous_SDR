import type { CSSProperties, ReactNode } from "react";
import { statusColors, theme } from "../theme";

export function StatusBadge({ status }: { status: string }) {
  const c = statusColors[status.toLowerCase()] ?? statusColors.draft;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "4px 10px",
        borderRadius: 12,
        fontSize: 10,
        fontWeight: 600,
        background: c.bg,
        color: c.color,
        border: `1px solid ${c.border}`,
        textTransform: "capitalize",
      }}
    >
      ● {status}
    </span>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      style={{
        background: theme.cardSolid,
        border: `1px solid ${theme.border}`,
        borderRadius: 10,
        padding: 18,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

interface BtnProps {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
  style?: CSSProperties;
}

export function Button({ children, onClick, variant = "ghost", disabled, type = "button", style }: BtnProps) {
  const variants: Record<string, CSSProperties> = {
    primary: { background: theme.purple, color: "#fff", border: "none" },
    ghost: {
      background: "rgba(255,255,255,0.06)",
      color: theme.textDim,
      border: `1px solid ${theme.borderStrong}`,
    },
    danger: {
      background: "rgba(220,60,80,0.15)",
      color: theme.red,
      border: "1px solid rgba(220,60,80,0.4)",
    },
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{
        borderRadius: 6,
        padding: "8px 16px",
        fontSize: 11,
        fontWeight: 600,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        fontFamily: theme.font,
        ...variants[variant],
        ...style,
      }}
    >
      {children}
    </button>
  );
}

export function Input({
  value,
  onChange,
  placeholder,
  type = "text",
  style,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  style?: CSSProperties;
}) {
  return (
    <input
      type={type}
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      style={{
        width: "100%",
        padding: "9px 10px",
        borderRadius: 6,
        background: "rgba(255,255,255,0.05)",
        border: `1px solid ${theme.borderStrong}`,
        color: theme.text,
        fontSize: 12,
        fontFamily: theme.font,
        boxSizing: "border-box",
        ...style,
      }}
    />
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div style={{ color: theme.textMuted, fontSize: 9, marginBottom: 6 }}>{label}</div>
      {children}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div style={{ color: theme.textMuted, fontSize: 12, padding: 24 }}>{label}</div>;
}

export function ErrorText({ children }: { children: ReactNode }) {
  return <div style={{ color: theme.red, fontSize: 12, padding: "8px 0" }}>{children}</div>;
}