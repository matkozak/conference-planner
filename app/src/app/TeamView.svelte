<script lang="ts">
  import type { SearchEntry } from "./store.svelte";
  import { itemsById } from "./store.svelte";
  import { rsvps } from "./notebook.svelte";
  import { dayLabel } from "./format";
  import PlanRow from "./PlanRow.svelte";
  import TzNote from "./TzNote.svelte";

  interface TeamItem {
    entry: SearchEntry;
    startsAt: string;
    authors: string[];
  }

  /** Every RSVP'd item resolved against the program, grouped by day. */
  const teamDays = $derived.by(() => {
    const byDay = new Map<string, TeamItem[]>();
    for (const [itemId, authors] of rsvps) {
      const entry = itemsById.get(itemId);
      if (!entry) continue;
      const startsAt = entry.talk?.starts_at ?? entry.session.starts_at ?? "";
      const list = byDay.get(entry.session.date) ?? [];
      list.push({ entry, startsAt, authors });
      byDay.set(entry.session.date, list);
    }
    for (const list of byDay.values()) {
      list.sort((a, b) => a.startsAt.localeCompare(b.startsAt));
    }
    return new Map([...byDay].sort(([a], [b]) => a.localeCompare(b)));
  });
</script>

<main class="team">
  <TzNote />
  <h2>Team plans</h2>
  {#if teamDays.size === 0}
    <p class="empty">
      Nothing yet — everyone's “I'll be there” picks show up here.
    </p>
  {/if}
  {#each [...teamDays] as [day, items] (day)}
    <h3>{dayLabel(day)}</h3>
    {#each items as { entry, startsAt, authors } (entry.talk?.id ?? entry.session.id)}
      <PlanRow {entry} {startsAt} {authors} />
    {/each}
  {/each}
</main>

<style>
  .team {
    padding: 0.75rem;
    max-width: 44rem;
    margin: 0 auto;
  }

  h2 {
    margin: 0.25rem 0 0.5rem;
  }

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
