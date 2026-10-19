// Authentic Natural Paper Page Turn Audio Player
// Uses freesound community page-flip sound (/page-flip.mp3)

let cachedAudio: HTMLAudioElement | null = null;

export function playPaperTurnSound() {
  if (typeof window === "undefined") return;
  try {
    if (!cachedAudio) {
      cachedAudio = new Audio("/page-flip.mp3");
      cachedAudio.volume = 0.6;
    }
    cachedAudio.currentTime = 0;
    const playPromise = cachedAudio.play();
    if (playPromise !== undefined) {
      playPromise.catch(() => {
        try {
          const fallback = new Audio("/page-flip.mp3");
          fallback.volume = 0.6;
          fallback.play().catch(() => {});
        } catch {}
      });
    }
  } catch {}
}
