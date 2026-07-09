<script lang="ts">
  import { search, searchState } from "./store.svelte";
  import SearchBox from "./SearchBox.svelte";
  import SearchResults from "./SearchResults.svelte";

  const results = $derived(
    search(searchState.query, {
      limit: 60,
      abstracts: searchState.inAbstracts,
    }),
  );
</script>

<main>
  <SearchBox
    bind:value={searchState.query}
    placeholder="Search everything — all days, talks, posters, people…"
    focusOnMount
  />
  <label class="abstracts-toggle">
    <input type="checkbox" bind:checked={searchState.inAbstracts} />
    also search abstracts (includes all co-authors and affiliations — noisier)
  </label>

  {#if searchState.query.trim().length >= 2}
    <SearchResults entries={results.entries} exactCount={results.exactCount} />
  {:else}
    <p class="empty">Type at least two characters.</p>
  {/if}
</main>

<style>
  .abstracts-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8125rem;
    color: var(--muted);
    margin: -0.25rem 0 0.75rem 0.25rem;
    cursor: pointer;
  }

  .abstracts-toggle input {
    accent-color: var(--accent);
  }
</style>
