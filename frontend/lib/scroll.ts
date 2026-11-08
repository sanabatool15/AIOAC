// Rules for keeping the newest chat message in view without jumping a reader who scrolled up on purpose.

export const NEAR_BOTTOM_PX = 160;

export interface ScrollBox {
  scrollHeight: number;
  scrollTop: number;
  clientHeight: number;
}

// True when the reader is at (or close to) the end of the page.
export function isNearBottom(box: ScrollBox, slack: number = NEAR_BOTTOM_PX): boolean {
  return box.scrollHeight - box.scrollTop - box.clientHeight <= slack;
}

// Follow the newest message when the person just sent something, or was already reading the end. Never otherwise.
export function shouldFollow(nearBottom: boolean, lastIsUserMessage: boolean): boolean {
  return lastIsUserMessage || nearBottom;
}
