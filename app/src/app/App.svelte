<script lang="ts">
  import { gotoDay, gotoSearch, init, ui } from './store.svelte';
  import { connectNotebook } from './notebook.svelte';
  import { dayLabel } from './format';
  import DayView from './DayView.svelte';
  import SessionDetail from './SessionDetail.svelte';
  import SearchView from './SearchView.svelte';

  void init().then(() => connectNotebook());
</script>

{#if ui.error}
  <main class="center"><p>{ui.error}</p></main>
{:else if !ui.program || !ui.route}
  <main class="center"><p>Loading the program…</p></main>
{:else if ui.route.view === 'day'}
  <header class="topbar">
    <nav class="days">
      {#each ui.program.days as day (day)}
        <button
          class="day-tab"
          class:active={ui.route.day === day}
          onclick={() => gotoDay(day)}
        >
          {dayLabel(day)}
        </button>
      {/each}
    </nav>
    <button class="icon-btn" onclick={gotoSearch} aria-label="Search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="11" cy="11" r="7" />
        <line x1="16.5" y1="16.5" x2="21" y2="21" />
      </svg>
    </button>
  </header>
  <DayView day={ui.route.day} />
{:else if ui.route.view === 'session'}
  <SessionDetail id={ui.route.id} />
{:else}
  <SearchView />
{/if}
