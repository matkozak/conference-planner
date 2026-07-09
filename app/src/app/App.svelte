<script lang="ts">
  import { tick } from "svelte";
  import {
    goBack,
    gotoDay,
    gotoMe,
    gotoPosters,
    gotoSearch,
    init,
    isPosterSession,
    savedScroll,
    sessionsById,
    ui,
  } from "./store.svelte";
  import { connectNotebook } from "./notebook.svelte";
  import { dayTab } from "./format";
  import DayView from "./DayView.svelte";
  import MyStuffView from "./MyStuffView.svelte";
  import PostersView from "./PostersView.svelte";
  import SearchView from "./SearchView.svelte";
  import SessionDetail from "./SessionDetail.svelte";

  void init().then(() => connectNotebook());

  // The session being viewed (if any) — its day tab lights up for orientation.
  const viewedSession = $derived(
    ui.route?.view === "session" ? sessionsById.get(ui.route.id) : undefined,
  );
  const activeDay = $derived(
    ui.route?.view === "day"
      ? ui.route.day
      : viewedSession && !isPosterSession(viewedSession)
        ? viewedSession.date
        : undefined,
  );
  const postersActive = $derived(
    ui.route?.view === "posters" ||
      (viewedSession !== undefined && isPosterSession(viewedSession)),
  );

  // After each route change: restore the scroll position for revisited pages
  // (browser back, "up" navigation) and keep the active tab in view.
  $effect(() => {
    void ui.route;
    void tick().then(() => {
      window.scrollTo(0, savedScroll(location.hash));
      document
        .querySelector(".day-tab.active")
        ?.scrollIntoView({ inline: "nearest", block: "nearest" });
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
      class:ghost={ui.route.view !== "session"}
      disabled={ui.route.view !== "session"}
      onclick={goBack}
      aria-label="Back">←</button
    >
    <nav class="days">
      {#each ui.program.days as day (day)}
        {@const [wd, num] = dayTab(day).split(" ")}
        <button
          class="day-tab"
          class:active={activeDay === day}
          aria-label={dayTab(day)}
          onclick={() => gotoDay(day)}
        >
          <span class="tab-wd">{wd}</span>{num}
        </button>
      {/each}
      <button
        class="day-tab section-start"
        class:active={postersActive}
        aria-label="Posters"
        onclick={gotoPosters}
      >
        <svg
          class="tab-icon"
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
        <span class="tab-text">Posters</span>
      </button>
      <button
        class="day-tab search-tab"
        class:active={ui.route.view === "search"}
        aria-label="Search"
        onclick={gotoSearch}
      >
        <svg
          class="tab-icon"
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
        >
          <circle cx="11" cy="11" r="7" />
          <line x1="16.5" y1="16.5" x2="21" y2="21" />
        </svg>
        <span class="tab-text">Search</span>
      </button>
      <button
        class="day-tab"
        class:active={ui.route.view === "me"}
        aria-label="My stuff"
        onclick={gotoMe}
      >
        <svg
          class="tab-icon"
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21c0-4.5 3.5-7 8-7s8 2.5 8 7" />
        </svg>
        <span class="tab-text">Me</span>
      </button>
    </nav>
  </header>
  {#if ui.route.view === "day"}
    <DayView day={ui.route.day} />
  {:else if ui.route.view === "posters"}
    <PostersView />
  {:else if ui.route.view === "search"}
    <SearchView />
  {:else if ui.route.view === "me"}
    <MyStuffView />
  {:else}
    <SessionDetail id={ui.route.id} talk={ui.route.talk} />
  {/if}
{/if}
