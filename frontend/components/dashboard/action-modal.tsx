import { useEffect, useId, useRef, type ReactNode } from "react";
import { Icon } from "./icon";

export function ActionModal({
  title,
  busy,
  onClose,
  children,
  className = "",
}: {
  title: string;
  busy: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    const previousFocus = document.activeElement;
    dialog?.showModal();
    dialog
      ?.querySelector<HTMLElement>("textarea, input:not([type=radio])")
      ?.focus();
    return () => {
      dialog?.close();
      if (previousFocus instanceof HTMLElement) previousFocus.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`dash-modal ${className}`}
      aria-labelledby={titleId}
      aria-busy={busy}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <div className="dash-modal-heading">
        <div>
          <p className="dash-eyebrow">Academic support workflow</p>
          <h2 id={titleId}>{title}</h2>
        </div>
        <button
          className="dash-icon-button"
          aria-label="Close dialog"
          disabled={busy}
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
