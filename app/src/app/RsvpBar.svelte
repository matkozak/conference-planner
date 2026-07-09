<script lang="ts">
  import { myRsvp, rsvpAuthors, setRsvp } from "./notebook.svelte";
  import { initials } from "./format";

  let { itemId }: { itemId: string } = $props();

  const going = $derived(myRsvp(itemId));
  const others = $derived(rsvpAuthors(itemId));
</script>

<div class="rsvp">
  <button class="rsvp-btn" class:going onclick={() => setRsvp(itemId, !going)}>
    {going ? "✓ I'll be there" : "I'll be there"}
  </button>
  {#each others as author (author)}
    <span class="rsvp-chip" title={author}>{initials(author)}</span>
  {/each}
</div>

<style>
  .rsvp {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    flex-wrap: wrap;
    margin: 0.5rem 0;
  }

  .rsvp-btn {
    font-size: 0.8125rem;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    cursor: pointer;
  }

  .rsvp-btn.going {
    background: var(--accent);
    color: var(--surface);
    border-color: var(--accent);
    font-weight: 600;
  }

  .rsvp-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 50%;
    background: var(--surface);
    border: 1px solid var(--accent);
    color: var(--accent);
    font-size: 0.6875rem;
    font-weight: 700;
  }
</style>
