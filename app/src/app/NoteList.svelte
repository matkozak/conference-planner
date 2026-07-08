<script lang="ts">
  import { createNote, currentUser, deleteNote, notes, notesFor, updateNote } from './notebook.svelte';
  import { noteStamp } from './format';

  let { itemId }: { itemId: string } = $props();

  const itemNotes = $derived(notesFor(itemId));

  let newBody = $state('');
  let editingId = $state<number | null>(null);
  let editBody = $state('');
  let confirmingId = $state<number | null>(null);
  let confirmTimer: ReturnType<typeof setTimeout> | null = null;

  /** Two-tap delete: first tap arms the button for 3 s, second tap deletes. */
  function askDelete(id: number): void {
    if (confirmTimer) clearTimeout(confirmTimer);
    if (confirmingId === id) {
      deleteNote(id);
      confirmingId = null;
    } else {
      confirmingId = id;
      confirmTimer = setTimeout(() => (confirmingId = null), 3000);
    }
  }

  function submit(): void {
    const trimmed = newBody.trim();
    if (!trimmed) return;
    createNote(itemId, trimmed);
    newBody = '';
  }

  function startEdit(id: number, body: string): void {
    editingId = id;
    editBody = body;
  }

  function saveEdit(): void {
    if (editingId !== null && editBody.trim()) {
      updateNote(editingId, editBody);
    }
    editingId = null;
    editBody = '';
  }

  function cancelEdit(): void {
    editingId = null;
    editBody = '';
  }

  /** Short display name: first part of email before @. */
  function shortName(email: string): string {
    const [local] = email.split('@');
    return local ?? email;
  }
</script>

<section class="notes">
  <h2>
    Notes ({itemNotes.length})
    {#if !notes.connected}<span class="offline">· reconnecting…</span>{/if}
  </h2>

  {#each itemNotes as note (note.id)}
    <div class="note">
      {#if editingId === note.id}
        <textarea
          class="note-edit"
          bind:value={editBody}
          onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); saveEdit(); } if (e.key === 'Escape') cancelEdit(); }}
        ></textarea>
        <div class="note-actions">
          <button class="note-btn save" onclick={saveEdit}>Save</button>
          <button class="note-btn" onclick={cancelEdit}>Cancel</button>
        </div>
      {:else}
        <div class="note-meta">
          <span class="note-author">{shortName(note.author)}</span>
          <span class="note-time">{noteStamp(note.created_at)}</span>
        </div>
        <p class="note-body">{note.body}</p>
        {#if note.author === currentUser.email}
          <div class="note-actions">
            <button class="note-btn" onclick={() => startEdit(note.id, note.body)}>Edit</button>
            <button class="note-btn danger" class:armed={confirmingId === note.id} onclick={() => askDelete(note.id)}>
              {confirmingId === note.id ? 'Really delete?' : 'Delete'}
            </button>
          </div>
        {/if}
      {/if}
    </div>
  {/each}

  <form class="note-form" onsubmit={(e) => { e.preventDefault(); submit(); }}>
    <textarea
      class="note-input"
      placeholder="Add a note…"
      bind:value={newBody}
      onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }}
    ></textarea>
    <button class="note-submit" type="submit" disabled={!newBody.trim()}>Post</button>
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

  .note {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.5rem;
  }

  .note-meta {
    display: flex;
    gap: 0.5rem;
    font-size: 0.8125rem;
    color: var(--muted);
  }

  .note-author {
    font-weight: 600;
    color: var(--accent);
  }

  .note-body {
    margin: 0.25rem 0;
    white-space: pre-line;
    font-size: 0.9375rem;
  }

  .note-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  .note-btn {
    font-size: 0.75rem;
    padding: 0.125rem 0.5rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    cursor: pointer;
  }

  .note-btn.save {
    background: var(--accent);
    color: var(--surface);
    border-color: var(--accent);
  }

  .note-btn.danger {
    color: #c44;
    border-color: #c44;
  }

  .note-btn.danger.armed {
    background: #c44;
    color: #fff;
    font-weight: 600;
  }

  .note-edit, .note-input {
    width: 100%;
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

  .note-form {
    display: flex;
    gap: 0.5rem;
    align-items: flex-end;
    margin-top: 0.5rem;
  }

  .note-input {
    flex: 1;
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
