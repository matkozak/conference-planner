<script lang="ts">
  import {
    gotoSession,
    posterSessionsByDay,
    search,
    searchState,
  } from "./store.svelte";
  import { dayLabel, posterTopic, timeRange } from "./format";
  import { tz } from "./tz.svelte";
  import SearchBox from "./SearchBox.svelte";
  import SearchResults from "./SearchResults.svelte";
  import TzNote from "./TzNote.svelte";

  const results = $derived(
    search(searchState.posters, { limit: 60, scope: "posters" }),
  );

  // Computed once at mount; the program (and these maps) never change.
  const posterCount = [...posterSessionsByDay.values()]
    .flat()
    .reduce((n, s) => n + s.presentations.length, 0);
</script>

<main>
  <SearchBox
    bind:value={searchState.posters}
    placeholder="Search {posterCount.toLocaleString('en')} posters…"
  />

  {#if searchState.posters.trim().length >= 2}
    <SearchResults
      entries={results.entries}
      exactCount={results.exactCount}
      emptyText="No matching posters."
    />
  {:else}
    <TzNote />
    {#each [...posterSessionsByDay] as [day, sessions] (day)}
      <h2 class="timeslot">{dayLabel(day)}</h2>
      {#each sessions as session (session.id)}
        <button class="card" onclick={() => gotoSession(session.id)}>
          <div class="title">{posterTopic(session)}</div>
          <div class="meta">
            <span class="time"
              >{timeRange(session.starts_at, session.ends_at, tz.zone)}</span
            >
            {#if session.location}<span>{session.location}</span>{/if}
            <span>{session.presentations.length} posters</span>
          </div>
        </button>
      {/each}
    {/each}
  {/if}
</main>
