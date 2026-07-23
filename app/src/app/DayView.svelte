<script lang="ts">
  import type { Session } from "../shared/program";
  import {
    gotoSearch,
    search,
    searchState,
    sessionsByDay,
  } from "./store.svelte";
  import { dayTab, hhmm } from "./format";
  import { tz } from "./tz.svelte";
  import SearchBox from "./SearchBox.svelte";
  import SessionCard from "./SessionCard.svelte";
  import SearchResults from "./SearchResults.svelte";
  import TzNote from "./TzNote.svelte";

  let { day }: { day: string } = $props();

  /** Sessions are pre-sorted by start time; group consecutive equal times. */
  const groups = $derived.by(() => {
    const out: { time: string; sessions: Session[] }[] = [];
    for (const s of sessionsByDay.get(day) ?? []) {
      const time = hhmm(s.starts_at, tz.zone) || "—";
      const last = out[out.length - 1];
      if (last && last.time === time) last.sessions.push(s);
      else out.push({ time, sessions: [s] });
    }
    return out;
  });

  const searching = $derived(searchState.query.trim().length >= 2);
  /** Scoped to this day only; the Search tab is the global corpus. */
  const results = $derived(
    searching
      ? search(searchState.query, { day })
      : { entries: [], exactCount: 0 },
  );
</script>

<main>
  <SearchBox
    bind:value={searchState.query}
    placeholder="Search {dayTab(day)} only…"
  />
  {#if searching}
    <SearchResults
      entries={results.entries}
      exactCount={results.exactCount}
      emptyText="No matches on {dayTab(day)}."
    />
    <button class="all-days" onclick={gotoSearch}>Search all days →</button>
  {:else}
    <TzNote />
    {#each groups as group (group.time)}
      <section>
        <h2 class="timeslot">{group.time}</h2>
        {#each group.sessions as session (session.id)}
          <SessionCard {session} />
        {/each}
      </section>
    {:else}
      <p class="empty">No sessions on this day.</p>
    {/each}
  {/if}
</main>

<style>
  .all-days {
    display: block;
    margin: 0.25rem auto 1rem;
    padding: 0.375rem 1rem;
    border-radius: 999px;
    color: var(--accent);
    background: var(--accent-soft);
    font-size: 0.875rem;
    font-weight: 600;
  }
</style>
