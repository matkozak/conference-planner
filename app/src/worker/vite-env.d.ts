// Minimal stand-in for vite/client, which would pull all of Vite's ambient
// asset modules (*.css, *.svg, ?raw, …) into the worker typecheck. The worker
// only reads import.meta.env.DEV, and `env` is optional because non-Vite
// runtimes (plain wrangler) don't define it — auth must fail closed there.
interface ImportMeta {
  readonly env?: { readonly DEV: boolean };
}
