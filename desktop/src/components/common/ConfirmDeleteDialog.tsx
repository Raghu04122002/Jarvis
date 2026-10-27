import { useEffect, useId, useRef, useState } from "react";

interface Props {
  /** The name the user must type to confirm. */
  name: string;
  title: string;
  description: React.ReactNode;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

/** Modal that only enables Delete once the user has typed the exact name. */
export function ConfirmDeleteDialog({ name, title, description, onConfirm, onClose }: Props) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const matches = typed.trim() === name;

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!matches || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onMouseDown={() => !busy && onClose()}>
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onSubmit={submit}
        onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl"
      >
        <h2 id={titleId} className="text-base font-semibold text-gray-900">{title}</h2>
        <div className="mt-2 text-sm text-gray-600">{description}</div>
        <label className="mt-4 block text-sm text-gray-700">
          Type <strong className="font-mono">{name}</strong> to confirm
          <input
            ref={inputRef}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-1.5 font-mono text-sm focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-100"
          />
        </label>
        {error && <p role="alert" className="mt-2 text-sm text-red-600">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!matches || busy}
            className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Deleting…" : "Delete"}
          </button>
        </div>
      </form>
    </div>
  );
}
