"use client";
import { useId, useRef } from "react";
import { cn } from "@/lib/utils";
import { nextTabId, type TabItem } from "./tabs-logic";

export type { TabItem };

export interface TabsProps {
  tabs: TabItem[];
  value: string;
  onValueChange: (id: string) => void;
  /** Accessible name of the tab list. */
  label: string;
  /**
   * Panels by tab id. All are rendered and the inactive ones hidden, so every
   * tab's aria-controls points at a real element. Use `children` instead when
   * panels fetch data and should mount only when opened.
   */
  panels?: Record<string, React.ReactNode>;
  /** Content of the active tab only (used when `panels` is not given). */
  children?: React.ReactNode;
  className?: string;
}

export function Tabs({ tabs, value, onValueChange, label, panels, children, className }: TabsProps) {
  const base = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const tabId = (id: string) => `${base}-tab-${id}`;
  const panelId = (id: string) => `${base}-panel-${id}`;

  function onKeyDown(e: React.KeyboardEvent) {
    const next = nextTabId(tabs, value, e.key);
    if (!next) return;
    e.preventDefault();
    onValueChange(next);
    refs.current[next]?.focus();
  }

  return (
    <div className={className}>
      <div role="tablist" aria-label={label} onKeyDown={onKeyDown} className="flex gap-1 overflow-x-auto border-b border-border">
        {tabs.map((t) => {
          const active = t.id === value;
          return (
            <button
              key={t.id}
              ref={(el) => {
                refs.current[t.id] = el;
              }}
              type="button"
              role="tab"
              id={tabId(t.id)}
              aria-selected={active}
              aria-controls={panels || active ? panelId(t.id) : undefined}
              tabIndex={active ? 0 : -1}
              disabled={t.disabled}
              onClick={() => onValueChange(t.id)}
              className={cn(
                "-mb-px shrink-0 border-b-2 px-3 py-2 text-body font-medium transition-colors disabled:opacity-50",
                active ? "border-brand text-brand-ink" : "border-transparent text-muted hover:text-ink",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      {panels
        ? tabs.map((t) => (
            <div key={t.id} role="tabpanel" id={panelId(t.id)} aria-labelledby={tabId(t.id)} hidden={t.id !== value} tabIndex={0} className="pt-4">
              {panels[t.id]}
            </div>
          ))
        : (
            <div role="tabpanel" id={panelId(value)} aria-labelledby={tabId(value)} tabIndex={0} className="pt-4">
              {children}
            </div>
          )}
    </div>
  );
}
