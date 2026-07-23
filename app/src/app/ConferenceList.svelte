<script lang="ts">
  import {
    CONFERENCE_CATALOG,
    conferenceStatus,
    type ConferenceStatus,
  } from "../shared/catalog";
  import type { Conference } from "../shared/program";
  import { dayLabel, todayInTimeZone } from "./format";
  import { HOME_TIME_ZONE } from "./tz.svelte";

  const today = todayInTimeZone(HOME_TIME_ZONE);
  const statuses: { id: ConferenceStatus; title: string }[] = [
    { id: "current", title: "Current" },
    { id: "upcoming", title: "Upcoming" },
    { id: "past", title: "Past" },
  ];
  const groups = Object.fromEntries(
    statuses.map(({ id }) => [
      id,
      CONFERENCE_CATALOG.filter(
        (conference) => conferenceStatus(conference, today) === id,
      ).sort((a, b) =>
        id === "past"
          ? b.starts_on.localeCompare(a.starts_on)
          : a.starts_on.localeCompare(b.starts_on),
      ),
    ]),
  ) as Record<ConferenceStatus, (typeof CONFERENCE_CATALOG)[number][]>;

  function dateRange(conference: Conference): string {
    const start = dayLabel(conference.starts_on);
    const end = dayLabel(conference.ends_on);
    return start === end ? start : `${start} – ${end}`;
  }
</script>

<main class="catalog">
  <h1>Conferences</h1>
  {#each statuses as status (status.id)}
    {#if groups[status.id].length}
      <section>
        <h2>{status.title}</h2>
        {#each groups[status.id] as conference (conference.id)}
          <a class="conference" href="/{conference.id}/">
            <strong>{conference.short_name}</strong>
            <span>{conference.name}</span>
            <small>{dateRange(conference)}</small>
          </a>
        {/each}
      </section>
    {/if}
  {/each}
</main>

<style>
  .catalog {
    max-width: 42rem;
    margin: 0 auto;
    padding: 1.5rem 1rem 3rem;
  }

  h1 {
    margin: 0 0 1.5rem;
  }

  h2 {
    margin: 1.5rem 0 0.5rem;
    color: var(--muted);
    font-size: 0.875rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .conference {
    display: grid;
    gap: 0.25rem;
    margin-bottom: 0.75rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    background: var(--surface);
    color: inherit;
    text-decoration: none;
  }

  .conference strong {
    color: var(--accent);
    font-size: 1.125rem;
  }

  .conference span {
    line-height: 1.35;
  }

  .conference small {
    color: var(--muted);
  }
</style>
