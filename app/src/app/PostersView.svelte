<script lang="ts">
  import { gotoSession, posterSessionsByDay, search, searchState } from './store.svelte';
  import { boardNo, dayLabel, posterTopic, timeRange } from './format';

  const results = $derived(search(searchState.posters, 60, 'posters'));

  // Computed once at mount; the program (and these maps) never change.
  const posterCount = [...posterSessionsByDay.values()]
    .flat()
    .reduce((n, s) => n + s.presentations.length, 0);
</script>

<main>
  <input
    class="search-input posters-search"
    type="search"
    placeholder="Search {posterCount.toLocaleString('en')} posters…"
    bind:value={searchState.posters}
  />

  {#if searchState.posters.trim().length >= 2}
    {#each results as result (result.talk?.id ?? result.session.id)}
      <button class="result" onclick={() => gotoSession(result.session.id, result.talk?.id)}>
        <div class="title">{result.talk?.title}</div>
        <div class="meta">
          <span class="kind">Poster</span>
          <span>{dayLabel(result.session.date)}</span>
          {#if result.talk?.location}<span>{boardNo(result.talk.location)}</span>{/if}
        </div>
      </button>
    {:else}
      <p class="empty">No matching posters.</p>
    {/each}
  {:else}
    {#each [...posterSessionsByDay] as [day, sessions] (day)}
      <h2 class="timeslot">{dayLabel(day)}</h2>
      {#each sessions as session (session.id)}
        <button class="card" onclick={() => gotoSession(session.id)}>
          <div class="title">{posterTopic(session)}</div>
          <div class="meta">
            <span class="time">{timeRange(session.starts_at, session.ends_at)}</span>
            {#if session.location}<span>{session.location}</span>{/if}
            <span>{session.presentations.length} posters</span>
          </div>
        </button>
      {/each}
    {/each}
  {/if}
</main>
