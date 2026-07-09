<script lang="ts">
  import type { Session } from "../shared/types";
  import { gotoSession, isPosterSession } from "./store.svelte";
  import { rsvpAuthors } from "./notebook.svelte";
  import { displayTitle, initials, timeRange } from "./format";
  import { tz } from "./tz.svelte";

  let { session }: { session: Session } = $props();

  /** Everyone going to this session or any talk in it. */
  const attendees = $derived.by(() => {
    const all = new Set(rsvpAuthors(session.id));
    for (const t of session.presentations) {
      for (const a of rsvpAuthors(t.id)) all.add(a);
    }
    return [...all].sort();
  });
</script>

<button class="card" onclick={() => gotoSession(session.id)}>
  <div class="meta">
    <span class="time"
      >{timeRange(session.starts_at, session.ends_at, tz.zone)}</span
    >
    {#if session.location}<span>{session.location}</span>{/if}
  </div>
  <div class="title">{displayTitle(session)}</div>
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

<style>
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
