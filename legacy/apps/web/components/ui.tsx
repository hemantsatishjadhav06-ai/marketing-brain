import clsx from "clsx";
import { ReactNode } from "react";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx("rounded-xl glass", className)}>{children}</div>;
}

export function Button({
  children, onClick, type = "button", variant = "primary", disabled, className, size = "md",
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "ghost" | "outline" | "danger";
  disabled?: boolean;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition disabled:opacity-50 disabled:cursor-not-allowed focus-ring select-none";
  const sizes = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-5 py-3 text-base",
  }[size];
  const variants = {
    primary: "accent-bg hover:opacity-90 shadow-glow",
    ghost: "bg-transparent text-ink hover:bg-panel2",
    outline: "border hairline-2 text-ink hover:bg-panel2",
    danger: "bg-danger/15 text-danger hover:bg-danger/25",
  }[variant];
  return (
    <button type={type} disabled={disabled} onClick={onClick} className={clsx(base, sizes, variants, className)}>
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={clsx(
        "w-full rounded-xl border hairline bg-panel2 px-3.5 py-2 text-ink placeholder-mute outline-none focus-ring transition",
        props.className,
      )}
    />
  );
}

export function PageHeader({
  title, description, action,
}: { title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3 mb-7 fade-up">
      <div>
        <h1 className="display text-3xl md:text-4xl">{title}</h1>
        {description && <div className="text-ink2 text-sm mt-1.5 max-w-2xl">{description}</div>}
      </div>
      {action && <div className="flex flex-wrap gap-2">{action}</div>}
    </div>
  );
}

export function EmptyState({ title, hint, cta }: { title: string; hint?: string; cta?: ReactNode }) {
  return (
    <Card className="p-12 text-center fade-up">
      <div className="mx-auto size-12 rounded-full grid place-items-center accent-bg mb-4 opacity-80">●</div>
      <div className="display text-2xl">{title}</div>
      {hint && <div className="text-mute text-sm mt-2 max-w-md mx-auto">{hint}</div>}
      {cta && <div className="mt-5">{cta}</div>}
    </Card>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton", className)} />;
}

export function StatusPill({ status }: { status: string }) {
  const tone: Record<string, string> = {
    queued: "bg-panel2 text-mute",
    running: "accent-bg !text-accentInk",
    done: "bg-good/15 text-good",
    completed: "bg-good/15 text-good",
    failed: "bg-danger/15 text-danger",
    cancelled: "bg-panel2 text-mute",
    idea: "bg-panel2 text-mute",
    planned: "bg-panel2 text-mute",
    locked: "bg-warn/15 text-warn",
    drafting: "bg-warn/15 text-warn",
    drafted: "bg-sky-500/15 text-sky-300",
    under_review: "bg-warn/15 text-warn",
    approved: "bg-good/15 text-good",
    scheduled: "bg-violet-500/15 text-violet-300",
    published: "accent-bg !text-accentInk",
    exported: "bg-sky-500/15 text-sky-300",
    skipped: "bg-panel2 text-mute",
  };
  return (
    <span className={clsx("inline-flex rounded-full px-2 py-0.5 text-[11px] font-mono", tone[status] || "bg-panel2 text-mute")}>
      {status}
    </span>
  );
}

export function Tabs({
  tabs, value, onChange,
}: {
  tabs: { label: string; value: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="inline-flex rounded-xl border hairline bg-panel p-1">
      {tabs.map((t) => (
        <button
          key={t.value}
          onClick={() => onChange(t.value)}
          className={clsx(
            "px-3 py-1.5 text-sm rounded-lg transition",
            t.value === value ? "bg-panel2 text-ink" : "text-mute hover:text-ink",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
