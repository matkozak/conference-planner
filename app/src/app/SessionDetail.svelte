<script lang="ts">
  import { goBack, sessionsById, speakerNames } from './store.svelte';
  import { dayLabel, displayTitle, hhmm, timeRange } from './format';
  import NoteList from './NoteList.svelte';

  let { id }: { id: string } = $props();

  const session = $derived(sessionsById.get(id));
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
      <p class="desc">{session.description}</p>
    {/if}

    {#if session.presentations.length}
      <h2>{session.presentations.length} talks</h2>
      {#each session.presentations as talk (talk.id)}
        <details class="talk">
          <summary>
            <span class="time">{hhmm(talk.starts_at) || '·'}</span>
            <span>{talk.title}</span>
          </summary>
          {#if talk.location && talk.location !== session.location}
            <p class="meta">{talk.location}</p>
          {/if}
          {#if speakerNames(talk).length}
            <p class="speakers">{speakerNames(talk).join(' · ')}</p>
          {/if}
          {#if talk.description}
            <p class="desc">{talk.description}</p>
          {/if}
          <NoteList itemId={talk.id} />
        </details>
      {/each}
    {/if}

    <NoteList itemId={session.id} />
  </main>
{/if}
