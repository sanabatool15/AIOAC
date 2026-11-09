"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, FileSpreadsheet, Mic, Paperclip, Square, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FieldShell } from "@/components/ui/input";
import { cn } from "@/lib/utils";

// Identical on every chat screen: attach (only when the screen supports it), mic, send.
interface ComposerProps {
  onSend: (text: string) => void;
  onAttach?: () => void;
  onPickFile?: (file: File) => void; // the clip opens the file picker and the file shows under the text, like other chat apps
  attachment?: File | null;
  onRemoveAttachment?: () => void;
  onSendWithFile?: (text: string) => void; // Send while a file is attached
  streaming?: boolean;
  onStop?: () => void;
  busy?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

// Minimal typing for the browser speech API (not in lib.dom).
interface SpeechRec {
  continuous: boolean;
  interimResults: boolean;
  onresult:
    | ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void)
    | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}
type SpeechCtor = new () => SpeechRec;

export function Composer({
  onSend,
  onAttach,
  onPickFile,
  attachment = null,
  onRemoveAttachment,
  onSendWithFile,
  streaming = false,
  onStop,
  busy = false,
  disabled = false,
  placeholder = "Message AIOAC...",
}: ComposerProps) {
  const [value, setValue] = useState("");
  const [recording, setRecording] = useState(false);
  const recRef = useRef<SpeechRec | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLTextAreaElement>(null);
  const canSend = (value.trim().length > 0 || !!attachment) && !busy && !disabled;

  // The box grows with the text, up to its maximum height, then scrolls.
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 192)}px`;
  }, [value]);

  function send() {
    if (!canSend) return;
    if (attachment && onSendWithFile) {
      onSendWithFile(value.trim());
      setValue("");
      return;
    }
    onSend(value.trim());
    setValue("");
  }

  function toggleMic() {
    if (recording) {
      recRef.current?.stop();
      return;
    }
    const w = window as unknown as {
      SpeechRecognition?: SpeechCtor;
      webkitSpeechRecognition?: SpeechCtor;
    };
    const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!Ctor) return;
    const rec = new Ctor();
    rec.continuous = false;
    rec.interimResults = false;
    rec.onresult = (e) => {
      const text = Array.from(e.results)
        .map((r) => r[0].transcript)
        .join(" ");
      setValue((v) => (v ? `${v} ${text}` : text));
    };
    rec.onend = () => setRecording(false);
    rec.onerror = () => setRecording(false);
    recRef.current = rec;
    setRecording(true);
    rec.start();
  }

  const micSupported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  return (
    <FieldShell className="flex w-full flex-col gap-2 p-3 shadow-card">
      <textarea
        ref={boxRef}
        rows={1}
        value={value}
        disabled={disabled}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        placeholder={placeholder}
        aria-label="Message AIOAC"
        className="max-h-48 w-full resize-none overflow-y-auto bg-transparent text-body text-ink outline-none placeholder:text-muted"
      />
      {attachment && (
        <div className="flex w-fit max-w-full items-center gap-2 rounded-md border border-border bg-surface py-1 pl-2 pr-1">
          <FileSpreadsheet aria-hidden className="size-4 shrink-0 text-brand" />
          <span className="min-w-0 truncate text-small font-medium text-ink">{attachment.name}</span>
          <span className="shrink-0 text-micro text-muted">{(attachment.size / 1024).toFixed(attachment.size < 10240 ? 1 : 0)} KB</span>
          <Button variant="ghost" size="icon" aria-label="Remove file" onClick={onRemoveAttachment} className="size-6">
            <X />
          </Button>
        </div>
      )}
      <div className="flex items-center gap-1">
        {(onPickFile || onAttach) && (
          <>
            <Button variant="ghost" size="icon" aria-label="Attach data" onClick={() => (onPickFile ? fileRef.current?.click() : onAttach?.())}>
              <Paperclip />
            </Button>
            {onPickFile && (
              <input
                ref={fileRef}
                type="file"
                accept=".csv,text/csv"
                aria-label="CSV file"
                tabIndex={-1}
                className="sr-only"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onPickFile(f);
                  e.target.value = "";
                }}
              />
            )}
          </>
        )}
        <div className="flex-1" />
        <Button
          variant="ghost"
          size="icon"
          aria-label={recording ? "Stop recording" : "Dictate message"}
          aria-pressed={recording}
          disabled={!micSupported}
          onClick={toggleMic}
          className={cn(recording && "bg-brand-tint text-brand-ink")}
        >
          <Mic className={cn(recording && "motion-safe:animate-pulse")} />
        </Button>
        {streaming ? (
          <Button size="icon" aria-label="Stop" onClick={onStop}>
            <Square />
          </Button>
        ) : (
          <Button
            size="icon"
            aria-label="Send message"
            disabled={!canSend}
            onClick={send}
          >
            <ArrowUp />
          </Button>
        )}
      </div>
    </FieldShell>
  );
}
