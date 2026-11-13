<script lang="ts">
  import type { Session } from "../shared/program";
  import { isPosterSession, speakerLines, speakerNames } from "./store.svelte";
  import { hhmm } from "./format";
  import { selectedTimeZone } from "./tz.svelte";
  import NoteList from "./NoteList.svelte";
  import RsvpBar from "./RsvpBar.svelte";

  let {
    session,
    talk,
    inline = false,
  }: {
    session: Session;
    talk?: string;
    inline?: boolean;
  } = $props();
  const poster = $derived(isPosterSession(session));
  let expanded = $state<Record<string, boolean>>({});

  $effect(() => {
    if (!talk) return;
    expanded[talk] = true;
    const frame = requestAnimationFrame(() => {
      document
        .getElementById(`talk-${talk}`)
        ?.scrollIntoView({ block: "start" });
    });
    return () => cancelAnimationFrame(frame);
  });
</script>

{#each session.presentations as item (item.id)}
  {@const label = poster
    ? item.location
    : hhmm(item.starts_at, selectedTimeZone())}
  <details
    class="talk"
    class:inline
    id={`talk-${item.id}`}
    open={expanded[item.id] ?? false}
    ontoggle={(e) => (expanded[item.id] = e.currentTarget.open)}
  >
    <summary>
      <span class="chevron" aria-hidden="true">›</span>
      {#if label}<span class="time">{label}</span>{/if}
      <span class="heading">
        <span>{item.title}</span>
        {#if speakerNames(item).length}
          <span class="authors">{speakerNames(item).join(" · ")}</span>
        {/if}
      </span>
    </summary>
    {#if expanded[item.id]}
      {#if !poster && item.location && item.location !== session.location}
        <p class="meta">{item.location}</p>
      {/if}
      {#if speakerLines(item).length}
        <p class="speakers">{speakerLines(item).join(" · ")}</p>
      {/if}
      {#if item.description_html}
        <div class="desc">{@html item.description_html}</div>
      {/if}
      <RsvpBar itemId={item.id} />
      <NoteList itemId={item.id} />
    {/if}
  </details>
{/each}

<style>
  .talk {
    scroll-margin-top: 6.5rem;
  }
  .talk.inline {
    border: 0;
    border-top: 1px solid var(--border);
    border-radius: 0;
    margin: 0;
    padding: 0.5rem 0;
  }
  summary {
    min-height: 2.75rem;
    align-items: baseline;
  }
  .heading {
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .authors {
    display: block;
    color: var(--muted);
    font-size: 0.8125rem;
    font-weight: 400;
    margin-top: 0.25rem;
  }
  .chevron {
    flex-shrink: 0;
    color: var(--muted);
  }
  details[open] .chevron {
    transform: rotate(90deg);
  }
</style>
