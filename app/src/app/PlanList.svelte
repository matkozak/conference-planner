<script lang="ts">
  import { dayLabel } from "./format";
  import type { PlanItem } from "./plans";
  import PlanRow from "./PlanRow.svelte";

  /** Day-grouped schedule rows for one Me/Team segment. */
  let {
    days,
    empty,
    showAuthors = false,
  }: {
    days: Map<string, PlanItem[]>;
    empty: string;
    showAuthors?: boolean;
  } = $props();
</script>

{#if days.size === 0}
  <p class="empty">{empty}</p>
{/if}
{#each [...days] as [day, items] (day)}
  <h3>{dayLabel(day)}</h3>
  {#each items as { entry, startsAt, authors, continuing } (entry.talk?.id ?? entry.session.id)}
    <PlanRow
      {entry}
      {startsAt}
      {continuing}
      authors={showAuthors ? authors : []}
    />
  {/each}
{/each}

<style>
  h3 {
    margin: 0.75rem 0 0.375rem;
    font-size: 0.875rem;
    color: var(--muted);
  }

  .empty {
    color: var(--muted);
    font-size: 0.9375rem;
  }
</style>
