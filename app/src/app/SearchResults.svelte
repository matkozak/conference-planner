<script lang="ts">
  import type { SearchEntry } from './store.svelte';
  import { entryKind, gotoSession } from './store.svelte';
  import { boardNo, dayLabel, displayTitle, hhmm, timeRange } from './format';

  let { results, emptyText = 'No matches.' }: { results: SearchEntry[]; emptyText?: string } = $props();

  const KIND_LABEL = {
    session: 'Session',
    posters: 'Posters',
    talk: 'Talk',
    poster: 'Poster',
  } as const;
</script>

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
  <p class="empty">{emptyText}</p>
{/each}
