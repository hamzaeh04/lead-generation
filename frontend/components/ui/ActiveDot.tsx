/** A small pulsing red dot — shown to the left of an action button while
 * its background sweep (scoring / email enrichment / phone enrichment) is
 * genuinely still running server-side. Renders nothing when inactive,
 * rather than a dimmed/gray dot, so it never reads as "something is
 * subtly happening" when nothing is. */
export function ActiveDot({ active, label }: { active: boolean; label: string }) {
  if (!active) return null;
  return (
    <span className="relative flex h-2 w-2 shrink-0" title={label} aria-label={label} role="status">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-danger opacity-75" />
      <span className="relative inline-flex h-2 w-2 rounded-full bg-danger" />
    </span>
  );
}
