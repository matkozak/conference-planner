<script lang="ts">
  import type { SearchEntry } from "./store.svelte";
  import { entryKind, gotoSession, ui } from "./store.svelte";
  import { visibleDays } from "./schedule";
  import { dayLabel, hhmm, timeRange } from "./format";
  import { selectedTimeZone } from "./tz.svelte";

  let {
    entries,
    exactCount = Infinity,
    emptyText = "No matches.",
  }: {
    entries: SearchEntry[];
    exactCount?: number;
    emptyText?: string;
  } = $props();

  const KIND_LABEL = {
    session: "Session",
    posters: "Posters",
    talk: "Talk",
    poster: "Poster",
  } as const;
</script>

{#each entries as result, i (result.talk?.id ?? result.session.id)}
  {@const kind = entryKind(result)}
  {@const days = visibleDays(
    result.session,
    ui.program!.conference.timezone,
    result.talk,
  )}
  {#if i === exactCount}
    <p class="fuzzy-divider">
      {exactCount === 0
        ? "No exact matches — close matches:"
        : "Close matches:"}
    </p>
  {/if}
  <button
    class="result"
    onclick={() => gotoSession(result.session.id, result.talk?.id)}
  >
    <div class="title">
      {result.talk ? result.talk.title : result.session.title}
    </div>
    <div class="meta">
      <span class="kind">{KIND_LABEL[kind]}</span>
      <span
        >{dayLabel(days[0]!)}{#if days.length > 1}–{dayLabel(
            days[days.length - 1]!,
          )}{/if}</span
      >
      {#if kind === "poster"}
        {#if result.talk?.location}<span>{result.talk.location}</span>{/if}
      {:else}
        <span class="time">
          {result.talk
            ? hhmm(result.talk.starts_at, selectedTimeZone())
            : timeRange(
                result.session.starts_at,
                result.session.ends_at,
                selectedTimeZone(),
              )}
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

<style>
  .fuzzy-divider {
    font-size: 0.8125rem;
    font-style: italic;
    color: var(--muted);
    margin: 0.75rem 0 0.375rem;
  }
</style>
