<script lang="ts">
  import { notes } from "./notebook.svelte";
  import NoteFeed from "./NoteFeed.svelte";
  import PlanList from "./PlanList.svelte";
  import { planCount, planDays } from "./plans";
  import PlanTabs from "./PlanTabs.svelte";
  import { gotoTeam, ui } from "./store.svelte";
  import TzNote from "./TzNote.svelte";

  const tab = $derived(ui.route?.view === "team" ? ui.route.tab : "talks");

  /** Everyone's RSVPs resolved against the program, talks vs posters. */
  const teamPlans = $derived(planDays());

  const teamNotes = $derived(
    [...notes.byId.values()].sort((a, b) =>
      b.created_at.localeCompare(a.created_at),
    ),
  );
</script>

<main class="team">
  <TzNote />
  <PlanTabs
    active={tab}
    posterCount={planCount(teamPlans.posters)}
    noteCount={teamNotes.length}
    onSelect={gotoTeam}
  />
  {#if tab === "talks"}
    <PlanList
      days={teamPlans.talks}
      empty="Nothing yet — everyone's “I'll be there” picks show up here."
      showAuthors
    />
  {:else if tab === "posters"}
    <PlanList
      days={teamPlans.posters}
      empty="No poster plans from the team yet."
      showAuthors
    />
  {:else}
    <NoteFeed notes={teamNotes} empty="No notes from the team yet." />
  {/if}
</main>

<style>
  .team {
    padding: 0.75rem;
    max-width: 44rem;
    margin: 0 auto;
  }
</style>
