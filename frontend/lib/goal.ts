// Project goals can be long. Headings and breadcrumbs show a short form; the full text stays in the page body.

/** Cut a goal to at most `max` characters, on a word boundary when one is near, with an ellipsis. */
export function truncateGoal(goal: string, max = 48): string {
  const text = goal.replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const space = cut.lastIndexOf(" ");
  const head = space > max * 0.6 ? cut.slice(0, space) : cut;
  return `${head.replace(/[\s.,;:!?-]+$/, "")}…`;
}

/** Input type for a password field with a show/hide toggle. */
export function passwordInputType(visible: boolean): "text" | "password" {
  return visible ? "text" : "password";
}
