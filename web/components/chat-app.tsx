"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { createConversation, titleFromMessage } from "@/lib/conversations";
import {
  createOfflineReflection,
  createOfflineReflectionForTrait,
  evaluateOfflineSafety,
  searchOfflineTraits,
  TRAIT_TYPES,
} from "@/lib/offline-guidance";
import type {
  ChatApiResult,
  ChatMessage,
  Conversation,
  TraitExplanation,
  TraitReflection,
  TraitType,
} from "@/lib/types";
import { BookIcon, CloseIcon, LeafIcon, MenuIcon, PlusIcon, SendIcon, SparkIcon } from "@/components/icons";

type ApiError = { error?: { code?: string; message?: string; requestId?: string } };

class ChatRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
    readonly requestId?: string,
  ) {
    super(message);
  }
}

const OFFLINE_FALLBACK_CODES = new Set([
  "insufficient_evidence",
  "guidance_failed",
  "guidance_not_helpful",
  "generation_service_unavailable",
  "upstream_timeout",
  "upstream_unavailable",
  "invalid_upstream_response",
  "not_configured",
  "service_unavailable",
]);

const STARTERS = [
  "I am anxious about an outcome I cannot control.",
  "How can I act well when I feel angry?",
  "I feel lost about the path I should choose.",
];

const REQUEST_PROGRESS = [
  { afterMs: 0, label: "Understanding your situation…" },
  { afterMs: 2_000, label: "Finding relevant passages…" },
  { afterMs: 5_000, label: "Composing grounded guidance…" },
  { afterMs: 10_000, label: "Checking citations and safety…" },
] as const;

function readableDate(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) return "Today";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

function MessageContent({ content }: { content: string }) {
  return <>{content.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</>;
}

function typeLabel(type: TraitReflection["type"]): string {
  return type.charAt(0).toUpperCase() + type.slice(1);
}

function TraitReflectionCard({ reflection, citations }: { reflection: TraitReflection; citations?: string[] }) {
  const isLive = reflection.source === "live";
  return (
    <section className={`trait-card${isLive ? " trait-card--live" : ""}`} aria-label={`${isLive ? "Live" : "Offline"} reflection for ${reflection.label}`}>
      {!isLive ? (
        <header className="trait-card-header">
          <div>
            <p className="trait-card-kicker">Offline reflection</p>
            <h2>{reflection.label}</h2>
          </div>
          <span className="trait-type">{typeLabel(reflection.type)}</span>
        </header>
      ) : null}
      <div className="trait-section">
        <h3>What Krishna said</h3>
        <p>{reflection.krishnaSaid}</p>
      </div>
      <div className="trait-section trait-section--practice">
        <h3>How to overcome</h3>
        <p>{reflection.howToOvercome}</p>
      </div>
      <figure className="sloka-card">
        <blockquote lang="sa-Latn">{reflection.sloka}</blockquote>
        <figcaption>Bhagavad Gita {reflection.verse}</figcaption>
      </figure>
      {isLive && citations?.length ? (
        <div className="citations trait-card-citations" aria-label="Sources">
          <span>Sources</span>
          {citations.map((citation) => <span className="citation" key={citation}><BookIcon />{citation}</span>)}
        </div>
      ) : null}
      {!isLive ? (
        <p className="offline-disclosure">
          {reflection.reason === "chosen"
          ? "Curated offline reflection · no provider was contacted"
          : "Curated offline reflection · shown because live guidance was unavailable"}
        </p>
      ) : null}
    </section>
  );
}

export function ChatApp() {
  const userInitial = "G";
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState("");
  const [draft, setDraft] = useState("");
  const [ready, setReady] = useState(false);
  const [sending, setSending] = useState(false);
  const [progressStage, setProgressStage] = useState(0);
  const [error, setError] = useState("");
  const [failedMessage, setFailedMessage] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [offlineMode, setOfflineMode] = useState(false);
  const [offlinePickerOpen, setOfflinePickerOpen] = useState(false);
  const [offlineSearch, setOfflineSearch] = useState("");
  const [offlineType, setOfflineType] = useState<TraitType | "all">("all");
  const endRef = useRef<HTMLDivElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const offlineSearchRef = useRef<HTMLInputElement>(null);
  const offlineToggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const initial = [createConversation()];
    setConversations(initial);
    setActiveId(initial[0].id);
    setReady(true);
  }, []);

  const active = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) || conversations[0],
    [activeId, conversations],
  );
  const visibleOfflineTraits = useMemo(
    () => searchOfflineTraits(offlineSearch, offlineType),
    [offlineSearch, offlineType],
  );

  useEffect(() => {
    if (!offlinePickerOpen) return;
    const frame = requestAnimationFrame(() => offlineSearchRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [offlinePickerOpen]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [active?.messages.length, sending]);

  useEffect(() => {
    if (!sending) {
      setProgressStage(0);
      return;
    }
    setProgressStage(0);
    const timers = REQUEST_PROGRESS.slice(1).map((stage, index) => window.setTimeout(
      () => setProgressStage(index + 1),
      stage.afterMs,
    ));
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [sending]);

  function updateConversation(id: string, updater: (conversation: Conversation) => Conversation) {
    setConversations((current) => current
      .map((conversation) => conversation.id === id ? updater(conversation) : conversation)
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)));
  }

  function newChat() {
    const conversation = createConversation();
    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
    setDraft("");
    setError("");
    setSidebarOpen(false);
    requestAnimationFrame(() => textAreaRef.current?.focus());
  }

  function setOffline(enabled: boolean) {
    setOfflineMode(enabled);
    setOfflinePickerOpen(enabled);
    setError("");
    setFailedMessage("");
  }

  function closeOfflinePicker() {
    setOfflinePickerOpen(false);
    requestAnimationFrame(() => offlineToggleRef.current?.focus());
  }

  function chooseOfflineTrait(trait: TraitExplanation) {
    if (!active || sending) return;
    const reflection = createOfflineReflectionForTrait(trait.id, "chosen");
    if (!reflection) return;
    const createdAt = new Date().toISOString();
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: `Explore: ${trait.label}`,
      createdAt,
    };
    updateConversation(active.id, (conversation) => ({
      ...conversation,
      title: conversation.messages.length ? conversation.title : titleFromMessage(trait.label),
      updatedAt: reflection.createdAt,
      messages: [...conversation.messages, userMessage, reflection],
    }));
    setError("");
    setFailedMessage("");
    setOfflineSearch("");
    setOfflinePickerOpen(false);
    requestAnimationFrame(() => textAreaRef.current?.focus());
  }

  async function send(rawMessage: string) {
    const message = rawMessage.trim();
    if (!message || !active || sending) return;
    const target = active;
    const clientRequestId = crypto.randomUUID();
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: message,
      createdAt: new Date().toISOString(),
    };
    setDraft("");
    setError("");
    setFailedMessage("");
    updateConversation(target.id, (conversation) => ({
      ...conversation,
      title: conversation.messages.length ? conversation.title : titleFromMessage(message),
      updatedAt: userMessage.createdAt,
      messages: [...conversation.messages, userMessage],
    }));

    if (offlineMode) {
      const safety = evaluateOfflineSafety(message);
      if (safety.action !== "allow") {
        setError(safety.message);
        setFailedMessage(message);
        return;
      }
      const reflection = createOfflineReflection(message, "chosen");
      if (!reflection) {
        setError("The offline guide could not confidently match this message to a trait. Try naming the emotion or situation more directly, or switch to live guidance.");
        setFailedMessage(message);
        return;
      }
      updateConversation(target.id, (conversation) => ({
        ...conversation,
        updatedAt: reflection.createdAt,
        messages: [...conversation.messages, reflection],
      }));
      return;
    }

    setSending(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          conversationId: target.id,
          clientRequestId,
          guestContext: {
            summary: target.summary,
            recentTurns: target.recentTurns,
          },
        }),
      });
      const body = (await response.json().catch(() => null)) as ChatApiResult | ApiError | null;
      if (!response.ok || !body || !("message" in body)) {
        const detail = body && "error" in body ? body.error : undefined;
        const detailMessage = detail?.message || "Guidance could not be generated. Please try again.";
        throw new ChatRequestError(detailMessage, response.status, detail?.code, detail?.requestId);
      }
      updateConversation(target.id, (conversation) => ({
        ...conversation,
        updatedAt: body.message.createdAt,
        summary: body.memory.summary,
        recentTurns: body.memory.recentTurns,
        messages: [...conversation.messages, body.message],
      }));
    } catch (caught) {
      const canUseOfflineFallback =
        caught instanceof TypeError ||
        (caught instanceof ChatRequestError && Boolean(caught.code && OFFLINE_FALLBACK_CODES.has(caught.code)));
      const safety = canUseOfflineFallback ? evaluateOfflineSafety(message) : null;
      const reflection = safety?.action === "allow"
        ? createOfflineReflection(message, "service_fallback")
        : null;
      if (reflection) {
        updateConversation(target.id, (conversation) => ({
          ...conversation,
          updatedAt: reflection.createdAt,
          messages: [...conversation.messages, reflection],
        }));
      } else {
        const baseMessage = caught instanceof Error ? caught.message : "Something went wrong. Please try again.";
        const reference = caught instanceof ChatRequestError ? caught.requestId : undefined;
        setError(reference ? `${baseMessage} Reference: ${reference}` : baseMessage);
        setFailedMessage(message);
      }
    } finally {
      setSending(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send(draft);
    }
  }

  if (!ready || !active) return <main className="app-loading" aria-live="polite"><span className="loader" /><span>Preparing your space…</span></main>;

  return (
    <div className="chat-shell">
      {sidebarOpen ? <button className="sidebar-scrim" aria-label="Close reflection sessions" onClick={() => setSidebarOpen(false)} /> : null}
      <aside className={`sidebar ${sidebarOpen ? "sidebar--open" : ""}`} aria-label="Reflection sessions">
        <div className="sidebar-header">
          <a href="#chat-main" className="brand"><span className="brand-mark"><BookIcon /></span><span>Gita Guide</span></a>
          <button className="icon-button sidebar-close" type="button" onClick={() => setSidebarOpen(false)} aria-label="Close reflection sessions"><CloseIcon /></button>
        </div>
        <button className="new-chat-button" type="button" onClick={newChat}><PlusIcon />New reflection</button>
        <nav className="conversation-list" aria-label="Your reflections">
          <p className="sidebar-label">Recent</p>
          {conversations.map((conversation) => (
            <button key={conversation.id} type="button" className={`conversation-item ${conversation.id === active.id ? "conversation-item--active" : ""}`} aria-current={conversation.id === active.id ? "page" : undefined} onClick={() => { setActiveId(conversation.id); setSidebarOpen(false); setError(""); }}>
              <span>{conversation.title}</span><time dateTime={conversation.updatedAt}>{readableDate(conversation.updatedAt)}</time>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-summary"><span className="avatar">{userInitial}</span><span><strong>Guest session</strong><small>Cleared when this page refreshes</small></span></div>
        </div>
      </aside>

      <main className="chat-main" id="chat-main">
        <header className="mobile-header">
          <button className="icon-button" type="button" onClick={() => setSidebarOpen(true)} aria-label="Open reflection sessions" aria-expanded={sidebarOpen}><MenuIcon /></button>
          <span className="mobile-brand"><BookIcon />Gita Guide</span>
          <button className="icon-button" type="button" onClick={newChat} aria-label="Start a new reflection"><PlusIcon /></button>
        </header>

        <section className={`messages ${active.messages.length === 0 ? "messages--empty" : ""}`} aria-label="Conversation" aria-live="polite" aria-busy={sending}>
          {active.messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-symbol"><LeafIcon /></div>
              <p className="eyebrow">A grounded reflection</p>
              <h1>What is weighing on your mind?</h1>
              <p>Share a situation or emotion. Gita Guide will look for relevant passages and offer a practical reflection, with sources you can inspect.</p>
              <div className="starter-grid" aria-label="Suggested reflections">
                {STARTERS.map((starter) => <button key={starter} type="button" onClick={() => void send(starter)}><SparkIcon /><span>{starter}</span></button>)}
              </div>
            </div>
          ) : (
            <div className="message-list">
              {active.messages.map((message) => (
                <article key={message.id} className={`message message--${message.role}`}>
                  <div className="message-avatar" aria-hidden="true">{message.role === "assistant" ? <BookIcon /> : userInitial}</div>
                  <div className="message-body">
                    <p className="message-author">{message.role === "assistant" ? "Gita Guide" : "You"}</p>
                    {!message.reflection ? <div className="message-content"><MessageContent content={message.content} /></div> : null}
                    {message.reflection ? <TraitReflectionCard reflection={message.reflection} citations={message.citations} /> : null}
                    {!message.reflection && message.citations?.length ? <div className="citations" aria-label="Sources"><span>Sources</span>{message.citations.map((citation) => <span className="citation" key={citation}><BookIcon />{citation}</span>)}</div> : null}
                  </div>
                </article>
              ))}
              {sending ? <article className="message message--assistant"><div className="message-avatar" aria-hidden="true"><BookIcon /></div><div className="message-body"><p className="message-author">Gita Guide</p><div className="thinking" role="status" aria-live="polite" aria-atomic="true"><span aria-hidden="true" /><span aria-hidden="true" /><span aria-hidden="true" /><b>{REQUEST_PROGRESS[progressStage].label}</b></div></div></article> : null}
              <div ref={endRef} />
            </div>
          )}
        </section>

        <div className="composer-region">
          {offlinePickerOpen ? (
            <section className="offline-picker" id="offline-trait-picker" aria-labelledby="offline-picker-title">
              <header className="offline-picker-header">
                <div>
                  <p className="offline-picker-kicker">Curated library</p>
                  <h2 id="offline-picker-title">Explore offline guidance</h2>
                  <p>Choose a trait or search by what you are experiencing.</p>
                </div>
                <button className="icon-button offline-picker-close" type="button" onClick={closeOfflinePicker} aria-label="Close offline guidance browser">
                  <CloseIcon />
                </button>
              </header>

              <div className="offline-search-field">
                <label htmlFor="offline-trait-search">Search emotions, situations, or qualities</label>
                <input
                  ref={offlineSearchRef}
                  id="offline-trait-search"
                  type="search"
                  value={offlineSearch}
                  onChange={(event) => setOfflineSearch(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") closeOfflinePicker();
                  }}
                  placeholder="Try anger, focus, loss, patience…"
                  autoComplete="off"
                />
              </div>

              <div className="trait-type-filters" aria-label="Filter guidance by type">
                <button type="button" aria-pressed={offlineType === "all"} onClick={() => setOfflineType("all")}>All</button>
                {TRAIT_TYPES.map((type) => (
                  <button key={type.id} type="button" aria-pressed={offlineType === type.id} onClick={() => setOfflineType(type.id)}>
                    {type.label}
                  </button>
                ))}
              </div>

              <div className="offline-results-header" role="status" aria-live="polite">
                <span>{visibleOfflineTraits.length} {visibleOfflineTraits.length === 1 ? "reflection" : "reflections"}</span>
                {offlineType !== "all" || offlineSearch ? <button type="button" onClick={() => { setOfflineType("all"); setOfflineSearch(""); }}>Clear filters</button> : null}
              </div>

              {visibleOfflineTraits.length ? (
                <div className="offline-trait-grid" aria-label="Offline guidance traits">
                  {visibleOfflineTraits.map((trait) => (
                    <button key={trait.id} type="button" onClick={() => chooseOfflineTrait(trait)}>
                      <span>{trait.label}</span>
                      <small>{typeLabel(trait.type)}</small>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="offline-empty">
                  <strong>No matching reflection</strong>
                  <span>Try a broader word or clear the filters.</span>
                </div>
              )}
            </section>
          ) : null}
          {error ? <div className="chat-error" role="alert"><span>{error}</span>{failedMessage ? <button type="button" onClick={() => void send(failedMessage)} disabled={sending}>Try again</button> : null}</div> : null}
          <div className="guidance-mode" id="guidance-mode-help">
            <button
              ref={offlineToggleRef}
              className="offline-toggle"
              type="button"
              aria-pressed={offlineMode}
              aria-expanded={offlinePickerOpen}
              aria-controls={offlinePickerOpen ? "offline-trait-picker" : undefined}
              onClick={() => setOffline(!offlineMode)}
              disabled={sending}
            >
              <LeafIcon />
              <span>Offline guide</span>
              <span className="toggle-track" aria-hidden="true"><span /></span>
            </button>
            <span>{offlineMode ? "Curated reflections; no provider call" : "Live grounded guidance"}</span>
            {offlineMode && !offlinePickerOpen ? <button className="browse-traits-button" type="button" onClick={() => setOfflinePickerOpen(true)}>Browse traits</button> : null}
          </div>
          <form className="composer" onSubmit={submit}>
            <label htmlFor="message" className="sr-only">Your message</label>
            <textarea ref={textAreaRef} id="message" rows={1} maxLength={4000} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleKeyDown} disabled={sending} placeholder="Share what you are facing…" />
            <button className="send-button" type="submit" disabled={sending || !draft.trim()} aria-label="Send message"><SendIcon /></button>
          </form>
          <p className="composer-note">{offlineMode ? "Offline reflections are not saved and use local keyword matching. " : "This guest session is not saved and clears on refresh. "}Gita Guide can make mistakes; consider the cited verses and use your own judgment.</p>
        </div>
      </main>
    </div>
  );
}
