<script lang="ts">
  import { tick } from 'svelte';
  import { goBack, gotoDay, gotoMe, gotoPosters, gotoSearch, init, isPosterSession, savedScroll, sessionsById, ui } from './store.svelte';
  import { connectNotebook } from './notebook.svelte';
  import { dayTab } from './format';
  import DayView from './DayView.svelte';
  import MyStuffView from './MyStuffView.svelte';
  import PostersView from './PostersView.svelte';
  import SearchView from './SearchView.svelte';
  import SessionDetail from './SessionDetail.svelte';

  void init().then(() => connectNotebook());

  // The session being viewed (if any) — its day tab lights up for orientation.
  const viewedSession = $derived(
    ui.route?.view === 'session' ? sessionsById.get(ui.route.id) : undefined,
  );
  const activeDay = $derived(
    ui.route?.view === 'day'
      ? ui.route.day
      : viewedSession && !isPosterSession(viewedSession)
        ? viewedSession.date
        : undefined,
  );
  const postersActive = $derived(
    ui.route?.view === 'posters' ||
      (viewedSession !== undefined && isPosterSession(viewedSession)),
  );

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
{:else}
  <header class="topbar">
    <!-- Always occupies its slot so the tabs never shift when it appears. -->
    <button
      class="back"
      class:ghost={ui.route.view !== 'session'}
      disabled={ui.route.view !== 'session'}
      onclick={goBack}
      aria-label="Back"
    >←</button>
    <nav class="days">
      {#each ui.program.days as day (day)}
        <button
          class="day-tab"
          class:active={activeDay === day}
          onclick={() => gotoDay(day)}
        >
          {dayTab(day)}
        </button>
      {/each}
      <button
        class="day-tab section-start"
        class:active={postersActive}
        onclick={gotoPosters}
      >
        Posters
      </button>
      <button
        class="day-tab"
        class:active={ui.route.view === 'search'}
        onclick={gotoSearch}
      >
        Search
      </button>
      <button
        class="day-tab"
        class:active={ui.route.view === 'me'}
        onclick={gotoMe}
      >
        Me
      </button>
    </nav>
  </header>
  {#if ui.route.view === 'day'}
    <DayView day={ui.route.day} />
  {:else if ui.route.view === 'posters'}
    <PostersView />
  {:else if ui.route.view === 'search'}
    <SearchView />
  {:else if ui.route.view === 'me'}
    <MyStuffView />
  {:else}
    <SessionDetail id={ui.route.id} talk={ui.route.talk} />
  {/if}
{/if}
