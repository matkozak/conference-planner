<script lang="ts">
  import { currentUser, notes } from "./notebook.svelte";
  import NoteFeed from "./NoteFeed.svelte";
  import PlanList from "./PlanList.svelte";
  import { planCount, planDays } from "./plans";
  import PlanTabs from "./PlanTabs.svelte";
  import { gotoMe, ui } from "./store.svelte";
  import TzNote from "./TzNote.svelte";

  const tab = $derived(ui.route?.view === "me" ? ui.route.tab : "talks");

  /** My RSVPs resolved against the program, split into talks vs posters. */
  const myPlans = $derived.by(() => {
    const me = currentUser.email;
    return planDays((authors) => me !== "" && authors.includes(me));
  });

  const myNotes = $derived(
    [...notes.byId.values()]
      .filter((n) => currentUser.email && n.author === currentUser.email)
      .sort((a, b) => b.created_at.localeCompare(a.created_at)),
  );
</script>

<main class="me">
  <TzNote />
  <PlanTabs
    active={tab}
    posterCount={planCount(myPlans.posters)}
    noteCount={myNotes.length}
    onSelect={gotoMe}
  />
  {#if tab === "talks"}
    <PlanList
      days={myPlans.talks}
      empty="Nothing yet — tap “I'll be there” on a session or talk to build your schedule."
    />
  {:else if tab === "posters"}
    <PlanList
      days={myPlans.posters}
      empty="No posters yet — RSVP from the Posters tab to plan your rounds."
    />
  {:else}
    <NoteFeed notes={myNotes} empty="No notes yet." />
  {/if}
</main>

<style>
  .me {
    padding: 0.75rem;
    max-width: 44rem;
    margin: 0 auto;
  }
</style>
