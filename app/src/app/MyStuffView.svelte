<script lang="ts">
  import type { SearchEntry } from './store.svelte';
  import { gotoSession, itemsById } from './store.svelte';
  import { currentUser, notes, rsvps } from './notebook.svelte';
  import { dayLabel, displayTitle, hhmm } from './format';

  interface PlanItem {
    entry: SearchEntry;
    startsAt: string;
  }

  /** My RSVPs resolved against the program, grouped by day, in time order. */
  const myDays = $derived.by(() => {
    const me = currentUser.email;
    const byDay = new Map<string, PlanItem[]>();
    if (!me) return byDay;
    for (const [itemId, authors] of rsvps) {
      if (!authors.includes(me)) continue;
      const entry = itemsById.get(itemId);
      if (!entry) continue;
      const startsAt = entry.talk?.starts_at ?? entry.session.starts_at ?? '';
      const day = entry.session.date;
      const list = byDay.get(day) ?? [];
      list.push({ entry, startsAt });
      byDay.set(day, list);
    }
    for (const list of byDay.values()) {
      list.sort((a, b) => a.startsAt.localeCompare(b.startsAt));
    }
    return new Map([...byDay].sort(([a], [b]) => a.localeCompare(b)));
  });

  const myNotes = $derived(
    [...notes.byId.values()]
      .filter((n) => currentUser.email && n.author === currentUser.email)
      .sort((a, b) => b.created_at.localeCompare(a.created_at)),
  );

  function itemTitle(entry: SearchEntry): string {
    return entry.talk?.title ?? displayTitle(entry.session);
  }

  function open(entry: SearchEntry): void {
    gotoSession(entry.session.id, entry.talk?.id);
  }
</script>

<main class="me">
  <h2>My schedule</h2>
  {#if myDays.size === 0}
    <p class="empty">
      Nothing yet — tap “I'll be there” on a session or talk to build your
      schedule.
    </p>
  {/if}
  {#each [...myDays] as [day, items] (day)}
    <h3>{dayLabel(day)}</h3>
    {#each items as { entry, startsAt } (entry.talk?.id ?? entry.session.id)}
      <button class="row" onclick={() => open(entry)}>
        <span class="time">{hhmm(startsAt) || '·'}</span>
        <span class="what">
          {itemTitle(entry)}
          {#if entry.talk}
            <span class="in">in {displayTitle(entry.session)}</span>
          {/if}
        </span>
      </button>
    {/each}
  {/each}

  <h2>My notes ({myNotes.length})</h2>
  {#if myNotes.length === 0}
    <p class="empty">No notes yet.</p>
  {/if}
  {#each myNotes as note (note.id)}
    {@const entry = itemsById.get(note.item_id)}
    <button class="row note-row" onclick={() => entry && open(entry)}>
      <span class="what">
        {#if entry}
          <span class="in">{itemTitle(entry)}</span>
        {/if}
        <span class="body">{note.body}</span>
      </span>
      <span class="time">{note.created_at.slice(5, 10)}</span>
    </button>
  {/each}
</main>

<style>
  .me {
    padding: 0.75rem;
    max-width: 44rem;
    margin: 0 auto;
  }

  h2 {
    margin: 1rem 0 0.5rem;
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

  .row {
    display: flex;
    gap: 0.625rem;
    width: 100%;
    text-align: left;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.375rem;
    cursor: pointer;
    font: inherit;
    color: var(--text);
  }

  .time {
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
    color: var(--muted);
    font-size: 0.875rem;
    padding-top: 0.0625rem;
  }

  .what {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    font-size: 0.9375rem;
    min-width: 0;
  }

  .in {
    font-size: 0.8125rem;
    color: var(--muted);
  }

  .note-row .body {
    white-space: pre-line;
  }

  .note-row .time {
    margin-left: auto;
  }
</style>
