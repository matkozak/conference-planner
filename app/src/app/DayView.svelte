<script lang="ts">
  import type { Session } from '../shared/types';
  import { search, searchState, sessionsByDay } from './store.svelte';
  import { hhmm } from './format';
  import SessionCard from './SessionCard.svelte';
  import SearchResults from './SearchResults.svelte';

  let { day }: { day: string } = $props();

  /** Sessions are pre-sorted by start time; group consecutive equal times. */
  const groups = $derived.by(() => {
    const out: { time: string; sessions: Session[] }[] = [];
    for (const s of sessionsByDay.get(day) ?? []) {
      const time = hhmm(s.starts_at) || '—';
      const last = out[out.length - 1];
      if (last && last.time === time) last.sessions.push(s);
      else out.push({ time, sessions: [s] });
    }
    return out;
  });

  const searching = $derived(searchState.query.trim().length >= 2);
  /** Global results, but matches on the viewed day surface first. */
  const results = $derived(
    searching ? search(searchState.query, 40, 'all', day) : [],
  );
</script>

<main>
  <input
    class="search-input posters-search"
    type="search"
    placeholder="Search talks, posters, speakers, rooms…"
    bind:value={searchState.query}
  />
  {#if searching}
    <SearchResults {results} />
  {:else}
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
