<script lang="ts">
  import { goBack, isPosterSession, sessionsById, speakerNames } from './store.svelte';
  import { boardNo, dayLabel, displayTitle, hhmm, timeRange } from './format';
  import NoteList from './NoteList.svelte';

  let { id, talk }: { id: string; talk?: string } = $props();

  const session = $derived(sessionsById.get(id));
  const poster = $derived(session ? isPosterSession(session) : false);

  /** Which talks are expanded; bodies (abstract + notes) render lazily. */
  let expanded = $state<Record<string, boolean>>({});

  // Deep link (#/s/S584/P8616): expand the talk and scroll to it.
  $effect(() => {
    if (!talk) return;
    expanded[talk] = true;
    requestAnimationFrame(() => {
      document.getElementById(`talk-${talk}`)?.scrollIntoView({ block: 'start' });
    });
  });
</script>

<header class="topbar">
  <button class="back" onclick={goBack} aria-label="Back">←</button>
  <h1 class="bar-title">{session ? displayTitle(session) : 'Session not found'}</h1>
</header>

{#if session}
  <main class="detail">
    <p class="when">
      {dayLabel(session.date)} · {timeRange(session.starts_at, session.ends_at)}
      {#if session.location}&nbsp;· {session.location}{/if}
    </p>
    <p class="meta">
      {#if session.category}<span class="chip">{session.category}</span>{/if}
      {#if session.session_number}<span>{session.session_number}</span>{/if}
    </p>
    {#if speakerNames(session).length}
      <p class="speakers">{speakerNames(session).join(' · ')}</p>
    {/if}
    {#if session.description}
      <p class="desc">{@html session.description}</p>
    {/if}

    {#if session.presentations.length}
      <h2>{session.presentations.length} {poster ? 'posters' : 'talks'}</h2>
      {#each session.presentations as item (item.id)}
        <details
          class="talk"
          id={`talk-${item.id}`}
          open={expanded[item.id] ?? false}
          ontoggle={(e) => (expanded[item.id] = e.currentTarget.open)}
        >
          <summary>
            <span class="time">
              {(poster ? boardNo(item.location) : hhmm(item.starts_at)) || '·'}
            </span>
            <span>{item.title}</span>
          </summary>
          {#if expanded[item.id]}
            {#if !poster && item.location && item.location !== session.location}
              <p class="meta">{item.location}</p>
            {/if}
            {#if speakerNames(item).length}
              <p class="speakers">{speakerNames(item).join(' · ')}</p>
            {/if}
            {#if item.description}
              <p class="desc">{@html item.description}</p>
            {/if}
            <NoteList itemId={item.id} />
          {/if}
        </details>
      {/each}
    {/if}

    <NoteList itemId={session.id} />
  </main>
{/if}
