<script lang="ts">
  import { isPosterSession, sessionsById, speakerNames } from "./store.svelte";
  import { dayLabel, timeRange } from "./format";
  import { selectedTimeZone } from "./tz.svelte";
  import TalkList from "./TalkList.svelte";
  import NoteList from "./NoteList.svelte";
  import RsvpBar from "./RsvpBar.svelte";

  let { id, talk }: { id: string; talk?: string } = $props();

  const session = $derived(sessionsById.get(id));
  const poster = $derived(session ? isPosterSession(session) : false);
</script>

{#if session}
  <main class="detail">
    <h1 class="detail-title">{session.title}</h1>
    <p class="when">
      {#if !session.starts_at || !session.ends_at}{dayLabel(session.date)} ·
      {/if}{timeRange(
        session.starts_at,
        session.ends_at,
        selectedTimeZone(),
        true,
      )}
      {#if session.location}&nbsp;· {session.location}{/if}
    </p>
    <p class="meta">
      {#if session.category}<span class="chip">{session.category}</span>{/if}
      {#if session.session_number}<span>{session.session_number}</span>{/if}
    </p>
    {#if speakerNames(session).length}
      <p class="speakers">{speakerNames(session).join(" · ")}</p>
    {/if}
    <RsvpBar itemId={session.id} />
    {#if session.description_html}
      <p class="desc">{@html session.description_html}</p>
    {/if}

    {#if session.presentations.length}
      <h2>
        {session.presentations.length}
        {poster ? "poster" : "talk"}{session.presentations.length == 1
          ? ""
          : "s"}
      </h2>
      {#key session.id}
        <TalkList {session} {talk} />
      {/key}
    {/if}

    <NoteList itemId={session.id} />
  </main>
{:else}
  <main class="center"><p>Session not found.</p></main>
{/if}
