<script lang="ts">
  import type { Session } from '../shared/types';
  import { gotoSession } from './store.svelte';
  import { displayTitle, timeRange } from './format';

  let { session }: { session: Session } = $props();
</script>

<button class="card" onclick={() => gotoSession(session.id)}>
  <div class="meta">
    <span class="time">{timeRange(session.starts_at, session.ends_at)}</span>
    {#if session.location}<span>{session.location}</span>{/if}
  </div>
  <div class="title">{displayTitle(session)}</div>
  <div class="meta">
    {#if session.category}<span class="chip">{session.category}</span>{/if}
    {#if session.presentations.length}
      <span>{session.presentations.length} talks</span>
    {/if}
  </div>
</button>
