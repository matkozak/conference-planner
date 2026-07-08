<script lang="ts">
  import { entryKind, goBack, gotoSession, search, searchState } from './store.svelte';
  import { boardNo, dayLabel, displayTitle, hhmm, timeRange } from './format';

  const results = $derived(search(searchState.query));

  const KIND_LABEL = {
    session: 'Session',
    posters: 'Posters',
    talk: 'Talk',
    poster: 'Poster',
  } as const;

  function focus(node: HTMLElement): void {
    node.focus();
  }
</script>

<header class="topbar">
  <button class="back" onclick={goBack} aria-label="Back">←</button>
  <input
    class="search-input"
    type="search"
    placeholder="Talks, posters, sessions, speakers, rooms…"
    bind:value={searchState.query}
    use:focus
  />
</header>

<main>
  {#each results as result (result.talk?.id ?? result.session.id)}
    {@const kind = entryKind(result)}
    <button class="result" onclick={() => gotoSession(result.session.id, result.talk?.id)}>
      <div class="title">
        {result.talk ? result.talk.title : displayTitle(result.session)}
      </div>
      <div class="meta">
        <span class="kind">{KIND_LABEL[kind]}</span>
        <span>{dayLabel(result.session.date)}</span>
        {#if kind === 'poster'}
          {#if result.talk?.location}<span>{boardNo(result.talk.location)}</span>{/if}
        {:else}
          <span class="time">
            {result.talk
              ? hhmm(result.talk.starts_at)
              : timeRange(result.session.starts_at, result.session.ends_at)}
          </span>
          {#if result.talk?.location ?? result.session.location}
            <span>{result.talk?.location ?? result.session.location}</span>
          {/if}
        {/if}
      </div>
    </button>
  {:else}
    {#if searchState.query.trim().length >= 2}
      <p class="empty">No matches.</p>
    {:else}
      <p class="empty">Type at least two characters.</p>
    {/if}
  {/each}
</main>
