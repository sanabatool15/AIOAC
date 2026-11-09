// True when the project moved to a different step and it is not the first render: then the canvas is scrolled back to the
// top so the new card is not left out of view.
export function stepChanged(previous: string | null, next: string): boolean {
  return previous !== null && previous !== next;
}
