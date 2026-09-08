<script lang="ts">
  import type { SearchEntry } from "./store.svelte";
  import { gotoSession } from "./store.svelte";
  import { currentUser } from "./notebook.svelte";
  import { hhmm, initials } from "./format";
  import { selectedTimeZone } from "./tz.svelte";

  /** One schedule row (Me & Team views): time, what/where, optional chips. */
  let {
    entry,
    startsAt,
    continuing,
    authors = [],
  }: {
    entry: SearchEntry;
    startsAt: string;
    continuing: boolean;
    authors?: string[];
  } = $props();

  const loc = $derived(entry.talk?.location ?? entry.session.location);
</script>

<button
  class="row"
  onclick={() => gotoSession(entry.session.id, entry.talk?.id)}
>
  <span class="time"
    >{continuing
      ? "Continues"
      : hhmm(startsAt, selectedTimeZone()) || "·"}</span
  >
  <span class="what">
    {entry.talk?.title ?? entry.session.title}
    {#if entry.talk}
      <span class="in">in {entry.session.title}</span>
    {/if}
    {#if loc}
      <span class="loc">📍 {loc}</span>
    {/if}
  </span>
  {#if authors.length}
    <span class="who">
      {#each authors as author (author)}
        <span
          class="rsvp-chip"
          class:me={author === currentUser.email}
          title={author}>{initials(author)}</span
        >
      {/each}
    </span>
  {/if}
</button>

<style>
  .row {
    display: flex;
    gap: 0.625rem;
    width: 100%;
    text-align: left;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.375rem;
    cursor: pointer;
    font: inherit;
    color: var(--text);
  }

  .time {
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
    color: var(--muted);
    font-size: 0.875rem;
    padding-top: 0.0625rem;
  }

  .what {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    font-size: 0.9375rem;
    min-width: 0;
    flex: 1;
  }

  .in {
    font-size: 0.8125rem;
    color: var(--muted);
  }

  .loc {
    font-size: 0.8125rem;
    color: var(--accent);
    font-weight: 600;
  }

  .who {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.25rem;
    flex-shrink: 0;
    max-width: 6rem;
    align-self: center;
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

  .rsvp-chip.me {
    background: var(--accent);
    color: var(--surface);
  }
</style>
