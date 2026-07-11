<script lang="ts">
  import type { Note } from "../shared/notebook";
  import { displayTitle } from "./format";
  import NoteCard from "./NoteCard.svelte";
  import type { SearchEntry } from "./store.svelte";
  import { gotoSession, itemsById } from "./store.svelte";

  /** Newest-first note feed with tappable session-context links. */
  let { notes, empty }: { notes: Note[]; empty: string } = $props();

  function itemTitle(entry: SearchEntry): string {
    return entry.talk?.title ?? displayTitle(entry.session);
  }

  function open(entry: SearchEntry): void {
    gotoSession(entry.session.id, entry.talk?.id);
  }
</script>

{#if notes.length === 0}
  <p class="empty">{empty}</p>
{/if}
{#each notes as note (note.id)}
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

<style>
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
