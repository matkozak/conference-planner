<script lang="ts">
  import type { PlanTab } from "./store.svelte";

  /** Segmented pill control for the Me/Team views: Talks | Posters | Notes. */
  let {
    active,
    posterCount,
    noteCount,
    onSelect,
  }: {
    active: PlanTab;
    posterCount: number;
    noteCount: number;
    onSelect: (tab: PlanTab) => void;
  } = $props();

  const tabs = $derived([
    { id: "talks", label: "Talks" },
    { id: "posters", label: `Posters (${posterCount})` },
    { id: "notes", label: `Notes (${noteCount})` },
  ] as const);
</script>

<div class="plan-tabs" role="tablist">
  {#each tabs as { id, label } (id)}
    <button
      role="tab"
      class="plan-tab"
      class:active={active === id}
      aria-selected={active === id}
      onclick={() => onSelect(id)}
    >
      {label}
    </button>
  {/each}
</div>

<style>
  .plan-tabs {
    display: flex;
    gap: 0.375rem;
    margin: 0.5rem 0 0.75rem;
  }

  /* Mirrors the topbar .day-tab pills; active changes colors only, never
     metrics, so the row cannot shift. */
  .plan-tab {
    padding: 0.375rem 0.75rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    font-size: 0.875rem;
    font-weight: 500;
    white-space: nowrap;
    cursor: pointer;
  }

  .plan-tab.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--surface);
  }
</style>
