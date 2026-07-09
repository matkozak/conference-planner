<script lang="ts">
  import type { SearchEntry } from "./store.svelte";
  import { gotoSession, itemsById } from "./store.svelte";
  import { currentUser, notes, rsvps } from "./notebook.svelte";
  import { dayLabel, displayTitle } from "./format";
  import NoteCard from "./NoteCard.svelte";
  import PlanRow from "./PlanRow.svelte";
  import TzNote from "./TzNote.svelte";

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
      const startsAt = entry.talk?.starts_at ?? entry.session.starts_at ?? "";
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
  <TzNote />
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
      <PlanRow {entry} {startsAt} />
    {/each}
  {/each}

  <h2>My notes ({myNotes.length})</h2>
  {#if myNotes.length === 0}
    <p class="empty">No notes yet.</p>
  {/if}
  {#each myNotes as note (note.id)}
    {@const entry = itemsById.get(note.item_id)}
    <div class="note-block">
      {#if entry}
        <button class="note-context" onclick={() => open(entry)}>
          {itemTitle(entry)} →
        </button>
      {/if}
      <NoteCard {note} />
    </div>
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

  .note-block {
    margin-bottom: 0.75rem;
  }

  .note-context {
    display: block;
    width: 100%;
    text-align: left;
    font-size: 0.8125rem;
    color: var(--muted);
    padding: 0 0.125rem 0.25rem;
    cursor: pointer;
  }
</style>
