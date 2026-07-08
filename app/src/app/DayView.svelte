<script lang="ts">
  import type { Session } from '../shared/types';
  import { sessionsByDay } from './store.svelte';
  import { hhmm } from './format';
  import SessionCard from './SessionCard.svelte';

  let { day }: { day: string } = $props();

  /** Sessions are pre-sorted by start time; group consecutive equal times. */
  const groups = $derived.by(() => {
    const out: { time: string; sessions: Session[] }[] = [];
    for (const s of sessionsByDay.get(day) ?? []) {
      const time = hhmm(s.starts_at) || '—';
      const last = out[out.length - 1];
      if (last && last.time === time) last.sessions.push(s);
      else out.push({ time, sessions: [s] });
    }
    return out;
  });
</script>

<main>
  {#each groups as group (group.time)}
    <section>
      <h2 class="timeslot">{group.time}</h2>
      {#each group.sessions as session (session.id)}
        <SessionCard {session} />
      {/each}
    </section>
  {:else}
    <p class="empty">No sessions on this day.</p>
  {/each}
</main>
