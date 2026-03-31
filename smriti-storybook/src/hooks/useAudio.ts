import { useCallback, useEffect, useRef } from "react";
import { Howl, Howler } from "howler";
import { useProgressStore } from "../stores/progress";

type SoundKey = "ambient" | "whoosh" | "correct" | "wrong" | "unlock" | "fanfare";

interface SoundConfig {
  src: string;
  loop: boolean;
  volume: number;
}

const SOUND_CONFIG: Record<SoundKey, SoundConfig> = {
  ambient: { src: "/audio/ambient.mp3", loop: true, volume: 0.15 },
  whoosh: { src: "/audio/whoosh.mp3", loop: false, volume: 0.4 },
  correct: { src: "/audio/correct.mp3", loop: false, volume: 0.4 },
  wrong: { src: "/audio/wrong.mp3", loop: false, volume: 0.4 },
  unlock: { src: "/audio/unlock.mp3", loop: false, volume: 0.4 },
  fanfare: { src: "/audio/fanfare.mp3", loop: false, volume: 0.4 },
};

export function useAudio() {
  const howlsRef = useRef<Partial<Record<SoundKey, Howl>>>({});
  const muted = useProgressStore((s) => s.audioMuted);
  const toggleMute = useProgressStore((s) => s.toggleMute);

  // Sync global mute state with Howler
  useEffect(() => {
    Howler.mute(muted);
  }, [muted]);

  const getHowl = useCallback((key: SoundKey): Howl => {
    let howl = howlsRef.current[key];
    if (!howl) {
      const config = SOUND_CONFIG[key];
      howl = new Howl({
        src: [config.src],
        loop: config.loop,
        volume: config.volume,
      });
      howlsRef.current[key] = howl;
    }
    return howl;
  }, []);

  const play = useCallback(
    (key: SoundKey) => {
      const howl = getHowl(key);
      // Ambient should only play if not already playing
      if (key === "ambient" && howl.playing()) {
        return;
      }
      howl.play();
    },
    [getHowl]
  );

  const stopAmbient = useCallback(() => {
    const ambient = howlsRef.current.ambient;
    if (ambient) {
      ambient.stop();
    }
  }, []);

  return { play, stopAmbient, muted, toggleMute };
}
