import { API_URL, api, speakBrowser } from "./api";

export type Card = {
  id: number; label: string; label_native: string | null; language: string;
  emoji: string; category: string; phrase: string; favorite: boolean;
};

export const CARD_CATEGORIES = ["needs", "requests", "feelings", "questions", "emergency", "personal"] as const;

export function groupCards(cards: Card[]): { key: string; title: string; cards: Card[] }[] {
  const favs = cards.filter((c) => c.favorite);
  const groups: { key: string; title: string; cards: Card[] }[] = CARD_CATEGORIES.map((cat) => ({
    key: cat,
    title: cat[0].toUpperCase() + cat.slice(1),
    cards: cards.filter((c) => c.category === cat && !c.favorite),
  })).filter((g) => g.cards.length > 0);
  const rest = cards.filter((c) => !(CARD_CATEGORIES as readonly string[]).includes(c.category) && !c.favorite);
  if (rest.length) groups.push({ key: "other", title: "Other", cards: rest });
  if (!favs.length) return groups;
  return [{ key: "favorites", title: "Favorites", cards: favs }, ...groups];
}

export function resolveAudioUrl(audio_url: string): string {
  return audio_url.startsWith("http") ? audio_url : `${API_URL}${audio_url}`;
}

/** Tap-to-speak through the audited server path. Returns the audio URL to
 *  play; falls back to device speech only for already-confirmed card text. */
export async function tapToSpeak(
  card: Card,
  play: (url: string) => void,
): Promise<{ phrase: string; fallback: boolean }> {
  const r = (await api.speakCard(card.id)) as { audio_url: string; fallback: boolean };
  if (r.fallback || !r.audio_url) {
    speakBrowser(card.phrase);
    return { phrase: card.phrase, fallback: true };
  }
  play(resolveAudioUrl(r.audio_url));
  return { phrase: card.phrase, fallback: false };
}
