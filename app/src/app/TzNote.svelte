<script lang="ts">
  import {
    timeModeLabel,
    toggleTimeMode,
    tz,
    type TimeMode,
  } from "./tz.svelte";

  const otherMode = $derived<TimeMode>(tz.mode === "venue" ? "home" : "venue");
</script>

<!-- The annotation IS the toggle: one tappable line, no prefs page needed. -->
<button class="tz-note" onclick={toggleTimeMode}>
  All times in {timeModeLabel(tz.mode)} ·
  <span class="switch">switch to {timeModeLabel(otherMode)}</span>
</button>

<style>
  .tz-note {
    display: block;
    width: 100%;
    text-align: right;
    font-size: 0.75rem;
    color: var(--muted);
    padding: 0.125rem 0.25rem 0.375rem;
    cursor: pointer;
  }

  .switch {
    color: var(--accent);
    font-weight: 600;
  }
</style>
