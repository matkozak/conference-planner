<script lang="ts">
  import { createNote, notes, notesFor } from "./notebook.svelte";
  import NoteCard from "./NoteCard.svelte";

  let { itemId }: { itemId: string } = $props();

  const itemNotes = $derived(notesFor(itemId));

  let newBody = $state("");

  function submit(): void {
    const trimmed = newBody.trim();
    if (!trimmed) return;
    createNote(itemId, trimmed);
    newBody = "";
  }
</script>

<section class="notes">
  <h2>
    Notes ({itemNotes.length})
    {#if !notes.connected}<span class="offline">· reconnecting…</span>{/if}
  </h2>

  {#each itemNotes as note (note.id)}
    <NoteCard {note} />
  {/each}

  <form
    class="note-form"
    onsubmit={(e) => {
      e.preventDefault();
      submit();
    }}
  >
    <textarea
      class="note-input"
      placeholder="Add a note…"
      bind:value={newBody}
      onkeydown={(e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          submit();
        }
      }}></textarea>
    <button class="note-submit" type="submit" disabled={!newBody.trim()}
      >Post</button
    >
  </form>
</section>

<style>
  .notes {
    margin-top: 1rem;
  }

  .offline {
    font-size: 0.75rem;
    font-weight: 400;
    font-style: italic;
    color: var(--muted);
  }

  .note-form {
    display: flex;
    gap: 0.5rem;
    align-items: flex-end;
    margin-top: 0.5rem;
  }

  .note-input {
    flex: 1;
    min-height: 3rem;
    padding: 0.5rem;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--bg);
    color: var(--text);
    font: inherit;
    font-size: 0.9375rem;
    resize: vertical;
  }

  .note-submit {
    flex-shrink: 0;
    padding: 0.5rem 1rem;
    border-radius: 999px;
    background: var(--accent);
    color: var(--surface);
    font-weight: 600;
    cursor: pointer;
  }

  .note-submit:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
