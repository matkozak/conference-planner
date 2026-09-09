<script lang="ts">
  import type { Session } from "../shared/program";
  import { gotoSession, isPosterSession, speakerNames } from "./store.svelte";
  import TalkList from "./TalkList.svelte";
  import RsvpBar from "./RsvpBar.svelte";
  import NoteList from "./NoteList.svelte";
  import { rsvpAuthors } from "./notebook.svelte";
  import { initials, timeRange } from "./format";
  import { selectedTimeZone } from "./tz.svelte";

  let {
    session,
    open,
    ontoggle,
  }: {
    session: Session;
    open: boolean;
    ontoggle: (header: HTMLButtonElement) => void;
  } = $props();

  /** Everyone going to this session or any talk in it. */
  const attendees = $derived.by(() => {
    const all = new Set(rsvpAuthors(session.id));
    for (const t of session.presentations) {
      for (const a of rsvpAuthors(t.id)) all.add(a);
    }
    return [...all].sort();
  });
</script>

<article class="card" class:expanded={open}>
  <button
    class="session-header"
    aria-expanded={open}
    aria-controls={`session-${session.id}`}
    onclick={(event) => ontoggle(event.currentTarget)}
  >
    <div class="meta">
      <span class="time"
        >{timeRange(
          session.starts_at,
          session.ends_at,
          selectedTimeZone(),
        )}</span
      >
      {#if session.location}<span>{session.location}</span>{/if}
    </div>
    <div class="title">{session.title}</div>
    <div class="meta">
      {#if session.category}<span class="chip">{session.category}</span>{/if}
      {#if session.presentations.length}
        <span>
          {session.presentations.length}
          {isPosterSession(session) ? "posters" : "talks"}
        </span>
      {/if}
      {#if attendees.length}
        <span class="attendees">
          {#each attendees.slice(0, 5) as author (author)}
            <span class="rsvp-chip" title={author}>{initials(author)}</span>
          {/each}
          {#if attendees.length > 5}<span>+{attendees.length - 5}</span>{/if}
        </span>
      {/if}
    </div>
  </button>
  <div id={`session-${session.id}`} hidden={!open}>
    {#if open}
      <div class="session-body">
        {#if speakerNames(session).length}
          <p class="speakers">{speakerNames(session).join(" · ")}</p>
        {/if}
        <div class="session-actions">
          <RsvpBar itemId={session.id} />
          <button class="open-session" onclick={() => gotoSession(session.id)}
            >Open session →</button
          >
        </div>
        {#if session.description_html}<div class="desc">
            {@html session.description_html}
          </div>{/if}
        <NoteList itemId={session.id} />
        {#if session.presentations.length}
          <h2 class="talk-list-title">
            {session.presentations.length}
            {isPosterSession(session) ? "poster" : "talk"}{session.presentations
              .length === 1
              ? ""
              : "s"}
          </h2>
          <TalkList {session} inline />
        {/if}
      </div>
    {/if}
  </div>
</article>

<style>
  .card {
    padding: 0;
    overflow: hidden;
  }
  .card:active {
    background: var(--surface);
  }
  .card.expanded {
    border-color: var(--accent);
  }
  .session-header {
    display: block;
    width: 100%;
    text-align: left;
    padding: 0.625rem 0.75rem;
  }
  .session-header:active,
  .expanded .session-header {
    background: var(--accent-soft);
  }
  .session-header:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -3px;
  }
  .title {
    overflow-wrap: anywhere;
  }
  .session-body {
    padding: 0 0.75rem 0.75rem;
    overflow-wrap: anywhere;
  }
  .session-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0 0.75rem;
  }
  .open-session {
    margin-left: auto;
    min-height: 2.75rem;
    color: var(--accent);
    font-size: 0.8125rem;
  }
  .talk-list-title {
    margin: 1.25rem 0 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
    color: var(--accent);
    font-size: 1rem;
  }
  .attendees {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    margin-left: auto;
  }

  .rsvp-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    border-radius: 50%;
    background: var(--surface);
    border: 1px solid var(--accent);
    color: var(--accent);
    font-size: 0.5625rem;
    font-weight: 700;
  }
</style>
