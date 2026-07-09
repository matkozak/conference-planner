<script lang="ts">
  import { ZONE_LABEL } from "./format";
  import { toggleZone, tz } from "./tz.svelte";

  const other = $derived(tz.zone === "london" ? "zurich" : "london");
</script>

<!-- The annotation IS the toggle: one tappable line, no prefs page needed. -->
<button class="tz-note" onclick={toggleZone}>
  All times {ZONE_LABEL[tz.zone]}
  {tz.zone === "london" ? "(venue)" : "(Zurich)"}
  · <span class="switch">switch to {ZONE_LABEL[other]}</span>
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
