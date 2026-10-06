"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { Icon } from "@/components/dashboard/icon";
import { guideSteps, roleAdvice, type GuideStep } from "@/lib/workspace-guide";
import { readable } from "@/lib/dashboard";
import type { User } from "@/types/auth";

type Mode = "welcome" | "help" | "tour" | null;
const storageKey = (id: string) => `academic-workspace-guide-v1:${id}`;
const GuideContext = createContext<{
  user: User | null;
  registerUser: (user: User | null) => void;
  openHelp: () => void;
} | null>(null);

export function GuideProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<Mode>(null);
  const [index, setIndex] = useState(0);
  const prompted = useRef(new Set<string>());
  const pathname = usePathname();
  const router = useRouter();
  const registerUser = useCallback((value: User | null) => {
    if (value) setUser(value);
  }, []);
  const openHelp = useCallback(() => setMode("help"), []);
  const inWorkspace = pathname !== "/" && pathname !== "/login";

  useEffect(() => {
    if (!inWorkspace) {
      setMode(null);
      setUser(null);
    }
  }, [inWorkspace]);
  useEffect(() => {
    if (!user || !inWorkspace || prompted.current.has(user.id)) return;
    prompted.current.add(user.id);
    let seen = false;
    try {
      seen = !!localStorage.getItem(storageKey(user.id));
    } catch {
      /* Session fallback. */
    }
    if (!seen) setMode("welcome");
  }, [user, inWorkspace]);

  function dismiss(completed = false) {
    if (user) {
      try {
        const key = storageKey(user.id);
        if (completed || localStorage.getItem(key) !== "completed")
          localStorage.setItem(key, completed ? "completed" : "dismissed");
      } catch {
        /* Guide can still be reopened. */
      }
    }
    setMode(null);
  }
  const steps = guideSteps(user?.role ?? "SYSTEM_ADMIN");
  function visit(next: number) {
    setIndex(next);
    setMode("tour");
    router.push(steps[next].href, { scroll: true });
  }
  return (
    <GuideContext.Provider value={{ user, registerUser, openHelp }}>
      {children}
      {mode && user && inWorkspace && (
        <GuideDialog
          mode={mode}
          user={user}
          steps={steps}
          index={index}
          pathname={pathname}
          onDismiss={() => dismiss()}
          onFinish={() => dismiss(true)}
          onVisit={visit}
        />
      )}
    </GuideContext.Provider>
  );
}

function GuideDialog({
  mode,
  user,
  steps,
  index,
  pathname,
  onDismiss,
  onFinish,
  onVisit,
}: {
  mode: Exclude<Mode, null>;
  user: User;
  steps: GuideStep[];
  index: number;
  pathname: string;
  onDismiss: () => void;
  onFinish: () => void;
  onVisit: (index: number) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const step = steps[index] ?? steps[0];
  const currentIndex = steps.findIndex((s) => pathname.startsWith(s.href));
  useEffect(() => {
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement;
    const previousOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    dialog?.showModal();
    return () => {
      dialog?.close();
      document.documentElement.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected)
        previousFocus.focus();
    };
  }, []);
  useEffect(() => {
    headingRef.current?.focus();
  }, [mode, index]);
  return (
    <dialog
      ref={dialogRef}
      className={`workspace-guide guide-${mode}`}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onCancel={(e) => {
        e.preventDefault();
        onDismiss();
      }}
      onClick={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        if (
          e.target === e.currentTarget &&
          (e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom)
        )
          onDismiss();
      }}
    >
      <div className="guide-topline">
        <span>
          <Icon name="book" /> Workspace guide
        </span>
        <button
          className="guide-icon-button"
          onClick={onDismiss}
          aria-label="Close workspace guide"
        >
          <Icon name="close" />
        </button>
      </div>
      {mode === "welcome" ? (
        <>
          <div className="guide-welcome-symbol">
            <Icon name="students" />
          </div>
          <p className="guide-eyebrow">
            Welcome, {user.full_name} · {readable(user.role)}
          </p>
          <h2 ref={headingRef} id={titleId} tabIndex={-1}>
            A clear path to
            <br />
            student support.
          </h2>
          <p id={descriptionId} className="guide-lead">
            Get to know your workspace, from understanding a student's record to
            recording the outcome of their support.
          </p>
          <div
            className="guide-workflow"
            aria-label="Academic support workflow"
          >
            {[
              { icon: "students" as const, label: "Understand" },
              { icon: "warning" as const, label: "Review" },
              { icon: "casework" as const, label: "Support" },
              { icon: "calendar" as const, label: "Follow through" },
            ].map((item, i) => (
              <div key={item.label}>
                <span>
                  <Icon name={item.icon} />
                </span>
                <strong>{item.label}</strong>
                {i < 3 && (
                  <span className="guide-flow-arrow">
                    <Icon name="chevron" />
                  </span>
                )}
              </div>
            ))}
          </div>
          <p className="guide-footnote">
            {steps.length} short steps · Skip at any time · Reopen from Help &
            tour
          </p>
          <div className="guide-actions">
            <button className="guide-button" onClick={onDismiss}>
              Explore on my own
            </button>
            <button
              className="guide-button guide-primary"
              onClick={() => onVisit(0)}
            >
              Take the guided tour <Icon name="arrow" />
            </button>
          </div>
        </>
      ) : mode === "help" ? (
        <>
          <p className="guide-eyebrow">A little help, when you need it</p>
          <h2 ref={headingRef} id={titleId} tabIndex={-1}>
            How can we help?
          </h2>
          <p id={descriptionId} className="guide-lead">
            Choose a workspace below for a short walkthrough, or start with the
            complete tour.
          </p>
          {currentIndex >= 0 && (
            <button
              className="guide-context"
              onClick={() => onVisit(currentIndex)}
            >
              <Icon name={steps[currentIndex].icon} />
              <span>
                <small>You are here</small>
                <strong>
                  How to use {steps[currentIndex].label.toLowerCase()}
                </strong>
              </span>
              <Icon name="arrow" />
            </button>
          )}
          <div className="guide-topic-list">
            {steps.map((s, i) => (
              <button key={s.id} onClick={() => onVisit(i)}>
                <span className="guide-topic-icon">
                  <Icon name={s.icon} />
                </span>
                <span>
                  <strong>{s.label}</strong>
                  <small>{s.title}</small>
                </span>
                <Icon name="chevron" />
              </button>
            ))}
          </div>
          <div className="guide-actions">
            <button className="guide-button" onClick={onDismiss}>
              Back to workspace
            </button>
            <button
              className="guide-button guide-primary"
              onClick={() => onVisit(0)}
            >
              Start the full tour <Icon name="arrow" />
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="guide-step-meta">
            <span>
              Step {index + 1} of {steps.length}
            </span>
            <span>{step.label}</span>
          </div>
          <div
            className="guide-progress"
            aria-label={`Tour progress: step ${index + 1} of ${steps.length}`}
          >
            {steps.map((s, i) => (
              <button
                key={s.id}
                onClick={() => onVisit(i)}
                aria-label={`Go to step ${i + 1}: ${s.label}`}
                aria-current={i === index ? "step" : undefined}
                className={i <= index ? "is-reached" : ""}
              />
            ))}
          </div>
          <div className="guide-tour-title">
            <span className="guide-topic-icon">
              <Icon name={step.icon} />
            </span>
            <h2 ref={headingRef} id={titleId} tabIndex={-1}>
              {step.title}
            </h2>
          </div>
          <p id={descriptionId} className="guide-lead">
            {step.intro}
          </p>
          <ol className="guide-tasks">
            {step.tasks.map((task, i) => (
              <li key={task}>
                <span>{i + 1}</span>
                <p>{task}</p>
              </li>
            ))}
          </ol>
          <aside className="guide-tip">
            <Icon name="help" />
            <p>{step.tip}</p>
          </aside>
          <p className="guide-role">
            <strong>{readable(user.role)}</strong>
            {roleAdvice(user.role, step)}
          </p>
          <div className="guide-actions">
            <button
              className="guide-button"
              disabled={index === 0}
              onClick={() => onVisit(index - 1)}
            >
              <Icon name="back" /> Back
            </button>
            <button className="guide-text-button" onClick={onDismiss}>
              Explore this screen
            </button>
            {index === steps.length - 1 ? (
              <button className="guide-button guide-primary" onClick={onFinish}>
                Finish tour <Icon name="check" />
              </button>
            ) : (
              <button
                className="guide-button guide-primary"
                onClick={() => onVisit(index + 1)}
              >
                Next <Icon name="arrow" />
              </button>
            )}
          </div>
        </>
      )}
    </dialog>
  );
}

export function useGuide() {
  const context = useContext(GuideContext);
  if (!context) throw new Error("Workspace guide requires GuideProvider.");
  return context;
}
