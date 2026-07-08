<script lang="ts">
  let {
    value = $bindable(),
    placeholder = '',
    focusOnMount = false,
  }: { value: string; placeholder?: string; focusOnMount?: boolean } = $props();

  let input = $state<HTMLInputElement | null>(null);

  $effect(() => {
    if (focusOnMount) input?.focus();
  });

  function clear(): void {
    value = '';
    input?.focus();
  }
</script>

<div class="search-box">
  <input
    bind:this={input}
    class="search-input"
    type="search"
    {placeholder}
    bind:value
  />
  {#if value}
    <button class="clear" aria-label="Clear search" onclick={clear}>×</button>
  {/if}
</div>

<style>
  .search-box {
    position: relative;
    margin-bottom: 0.75rem;
  }

  .search-box .search-input {
    display: block;
    width: 100%;
    padding-right: 2.5rem;
  }

  .clear {
    position: absolute;
    right: 0.4375rem;
    top: 50%;
    transform: translateY(-50%);
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 1.0625rem;
    line-height: 1;
    padding: 0;
  }
</style>
