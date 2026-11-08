"use client";
import { useRef, useState } from "react";
import { ArrowUp, Mic, Paperclip, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FieldShell } from "@/components/ui/input";
import { cn } from "@/lib/utils";

// Identical on every chat screen: attach (only when the screen supports it), mic, send.
interface ComposerProps {
  onSend: (text: string) => void;
  onAttach?: () => void;
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
  streaming = false,
  onStop,
  busy = false,
  disabled = false,
  placeholder = "Message AIOAC...",
}: ComposerProps) {
  const [value, setValue] = useState("");
  const [recording, setRecording] = useState(false);
  const recRef = useRef<SpeechRec | null>(null);
  const canSend = value.trim().length > 0 && !busy && !disabled;

  function send() {
    if (!canSend) return;
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
        className="w-full resize-none bg-transparent text-body text-ink outline-none placeholder:text-muted"
      />
      <div className="flex items-center gap-1">
        {onAttach && (
          <Button variant="ghost" size="icon" aria-label="Attach data" onClick={onAttach}>
            <Paperclip />
          </Button>
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
