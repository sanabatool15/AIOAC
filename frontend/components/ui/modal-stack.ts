// Pure helpers for the Modal. No React, no real DOM needed, so they are unit tested.

const stack: string[] = [];

export function pushModal(id: string) {
  if (!stack.includes(id)) stack.push(id);
}
export function popModal(id: string) {
  const i = stack.indexOf(id);
  if (i >= 0) stack.splice(i, 1);
}
/** Only the top modal reacts to Esc. */
export function isTopModal(id: string) {
  return stack.length > 0 && stack[stack.length - 1] === id;
}
export function modalDepth() {
  return stack.length;
}

// Body scroll lock is counted so nested modals do not unlock the page early.
let locks = 0;
let saved = "";
export function lockScroll(body: { style: { overflow: string } }) {
  if (locks === 0) {
    saved = body.style.overflow;
    body.style.overflow = "hidden";
  }
  locks += 1;
}
export function unlockScroll(body: { style: { overflow: string } }) {
  if (locks === 0) return;
  locks -= 1;
  if (locks === 0) body.style.overflow = saved;
}

export const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Where Tab or Shift+Tab goes next inside a trapped dialog. Returns the new index. */
export function nextFocusIndex(current: number, count: number, backwards: boolean): number {
  if (count <= 0) return -1;
  if (current < 0) return backwards ? count - 1 : 0; // focus is outside the list
  if (backwards) return current === 0 ? count - 1 : current - 1;
  return current === count - 1 ? 0 : current + 1;
}
