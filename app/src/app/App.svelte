<script lang="ts">
  import { tick } from 'svelte';
  import { gotoDay, gotoPosters, gotoSearch, init, savedScroll, ui } from './store.svelte';
  import { connectNotebook } from './notebook.svelte';
  import { dayTab } from './format';
  import DayView from './DayView.svelte';
  import PostersView from './PostersView.svelte';
  import SessionDetail from './SessionDetail.svelte';
  import SearchView from './SearchView.svelte';

  void init().then(() => connectNotebook());

  // After each route change: restore the scroll position for revisited pages
  // (browser back, "up" navigation) and keep the active tab in view.
  $effect(() => {
    void ui.route;
    void tick().then(() => {
      window.scrollTo(0, savedScroll(location.hash));
      document
        .querySelector('.day-tab.active')
        ?.scrollIntoView({ inline: 'nearest', block: 'nearest' });
    });
  });
</script>

{#if ui.error}
  <main class="center"><p>{ui.error}</p></main>
{:else if !ui.program || !ui.route}
  <main class="center"><p>Loading the program…</p></main>
{:else if ui.route.view === 'day' || ui.route.view === 'posters'}
  <header class="topbar">
    <nav class="days">
      {#each ui.program.days as day (day)}
        <button
          class="day-tab"
          class:active={ui.route.view === 'day' && ui.route.day === day}
          onclick={() => gotoDay(day)}
        >
          {dayTab(day)}
        </button>
      {/each}
      <button
        class="day-tab posters-tab"
        class:active={ui.route.view === 'posters'}
        onclick={gotoPosters}
      >
        Posters
      </button>
    </nav>
    <button class="icon-btn" onclick={gotoSearch} aria-label="Search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="11" cy="11" r="7" />
        <line x1="16.5" y1="16.5" x2="21" y2="21" />
      </svg>
    </button>
  </header>
  {#if ui.route.view === 'day'}
    <DayView day={ui.route.day} />
  {:else}
    <PostersView />
  {/if}
{:else if ui.route.view === 'session'}
  <SessionDetail id={ui.route.id} talk={ui.route.talk} />
{:else}
  <SearchView />
{/if}
