<script lang="ts">
  import type { Note } from "../shared/notebook";
  import { currentUser, deleteNote, updateNote } from "./notebook.svelte";
  import { noteStamp } from "./format";
  import { selectedTimeZone } from "./tz.svelte";

  let { note }: { note: Note } = $props();

  let editing = $state(false);
  let editBody = $state("");
  let confirming = $state(false);
  let confirmTimer: ReturnType<typeof setTimeout> | null = null;

  /** Two-tap delete: first tap arms the button for 3 s, second tap deletes. */
  function askDelete(): void {
    if (confirmTimer) clearTimeout(confirmTimer);
    if (confirming) {
      deleteNote(note.id);
      confirming = false;
    } else {
      confirming = true;
      confirmTimer = setTimeout(() => (confirming = false), 3000);
    }
  }

  function startEdit(): void {
    editing = true;
    editBody = note.body;
  }

  function saveEdit(): void {
    if (editBody.trim()) updateNote(note.id, editBody);
    editing = false;
    editBody = "";
  }

  function cancelEdit(): void {
    editing = false;
    editBody = "";
  }

  /** Short display name: first part of email before @. */
  function shortName(email: string): string {
    const [local] = email.split("@");
    return local ?? email;
  }
</script>

<div class="note">
  {#if editing}
    <textarea
      class="note-edit"
      bind:value={editBody}
      onkeydown={(e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          saveEdit();
        }
        if (e.key === "Escape") cancelEdit();
      }}></textarea>
    <div class="note-actions">
      <button class="note-btn save" onclick={saveEdit}>Save</button>
      <button class="note-btn" onclick={cancelEdit}>Cancel</button>
    </div>
  {:else}
    <div class="note-meta">
      <span class="note-author">{shortName(note.author)}</span>
      <span class="note-time"
        >{noteStamp(note.created_at, selectedTimeZone())}</span
      >
    </div>
    <p class="note-body">{note.body}</p>
    {#if note.author === currentUser.email}
      <div class="note-actions">
        <button class="note-btn" onclick={startEdit}>Edit</button>
        <button
          class="note-btn danger"
          class:armed={confirming}
          onclick={askDelete}
        >
          {confirming ? "Really delete?" : "Delete"}
        </button>
      </div>
    {/if}
  {/if}
</div>

<style>
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

  .note-edit {
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
</style>
