"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { getAudioStatus, generateAudioDigest, getAudioUrl } from "@/lib/api";
import type { AudioDigestStatus } from "@/lib/types";
import { Play, Pause, Download, Loader2, Volume2 } from "lucide-react";

interface AudioPlayerProps {
    caseId: string;
}

const LANGUAGE_LABELS: Record<string, string> = {
    en: "English",
    hi: "Hindi",
    ta: "Tamil",
    te: "Telugu",
    kn: "Kannada",
    ml: "Malayalam",
    bn: "Bengali",
    mr: "Marathi",
    gu: "Gujarati",
    pa: "Punjabi",
};

function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export default function AudioPlayer({ caseId }: AudioPlayerProps) {
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const [status, setStatus] = useState<AudioDigestStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [selectedLanguage, setSelectedLanguage] = useState("en");
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [playbackRate, setPlaybackRate] = useState("1");
    const [generating, setGenerating] = useState(false);

    const fetchStatus = useCallback(async () => {
        try {
            const s = await getAudioStatus(caseId);
            setStatus(s);
            return s;
        } catch {
            // Audio status endpoint may not exist yet
            setStatus({ case_id: caseId, available: [], generating: [], digests: [] });
            return null;
        }
    }, [caseId]);

    // Initial load
    useEffect(() => {
        let cancelled = false;
        async function load() {
            setLoading(true);
            const s = await fetchStatus();
            if (cancelled) return;
            // If something is generating, start polling
            if (s && s.generating.length > 0) {
                setGenerating(true);
                startPolling();
            }
            setLoading(false);
        }
        load();
        return () => {
            cancelled = true;
            stopPolling();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [caseId]);

    const startPolling = useCallback(() => {
        stopPolling();
        pollRef.current = setInterval(async () => {
            const s = await fetchStatus();
            if (s && s.generating.length === 0) {
                setGenerating(false);
                stopPolling();
            }
        }, 5000);
    }, [fetchStatus]);

    function stopPolling() {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopPolling();
        };
    }, []);

    // Audio event handlers
    const handleTimeUpdate = () => {
        if (audioRef.current) {
            setCurrentTime(audioRef.current.currentTime);
        }
    };

    const handleLoadedMetadata = () => {
        if (audioRef.current) {
            setDuration(audioRef.current.duration);
        }
    };

    const handleEnded = () => {
        setIsPlaying(false);
    };

    const togglePlay = () => {
        if (!audioRef.current) return;
        if (isPlaying) {
            audioRef.current.pause();
            setIsPlaying(false);
        } else {
            audioRef.current.play();
            setIsPlaying(true);
        }
    };

    const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
        const time = Number(e.target.value);
        if (audioRef.current) {
            audioRef.current.currentTime = time;
            setCurrentTime(time);
        }
    };

    const handlePlaybackRateChange = (rate: string) => {
        setPlaybackRate(rate);
        if (audioRef.current) {
            audioRef.current.playbackRate = Number(rate);
        }
    };

    const handleGenerate = async () => {
        try {
            setGenerating(true);
            await generateAudioDigest(caseId, selectedLanguage);
            startPolling();
        } catch {
            setGenerating(false);
        }
    };

    const handleLanguageChange = (lang: string) => {
        setSelectedLanguage(lang);
        setIsPlaying(false);
        setCurrentTime(0);
        setDuration(0);
    };

    if (loading) {
        return (
            <Card className="p-4 rounded-md">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading audio status...
                </div>
            </Card>
        );
    }

    if (!status) return null;

    const isAvailable = status.available.includes(selectedLanguage);
    const isGenerating = generating || status.generating.includes(selectedLanguage);

    // Generating state
    if (isGenerating) {
        return (
            <Card className="p-4 rounded-md">
                <div className="flex items-center gap-2">
                    <Volume2 className="h-4 w-4 text-muted-foreground" />
                    <h4 className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground">
                        Audio Digest
                    </h4>
                </div>
                <div className="flex items-center gap-2 mt-3 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating audio digest...
                </div>
            </Card>
        );
    }

    // Not available - show generate button
    if (!isAvailable) {
        return (
            <Card className="p-4 rounded-md">
                <div className="flex items-center gap-2">
                    <Volume2 className="h-4 w-4 text-muted-foreground" />
                    <h4 className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground">
                        Audio Digest
                    </h4>
                </div>
                <div className="mt-3 flex items-center gap-2">
                    <Select value={selectedLanguage} onValueChange={setSelectedLanguage}>
                        <SelectTrigger className="w-[140px] h-8 text-xs">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {Object.entries(LANGUAGE_LABELS).map(([code, label]) => (
                                <SelectItem key={code} value={code} className="text-xs">
                                    {label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button
                        size="sm"
                        variant="outline"
                        className="text-xs h-8"
                        onClick={handleGenerate}
                    >
                        Generate Audio
                    </Button>
                </div>
            </Card>
        );
    }

    // Available - show player
    const audioUrl = getAudioUrl(caseId, selectedLanguage);

    return (
        <Card className="p-4 rounded-md">
            <div className="flex items-center gap-2 mb-3">
                <Volume2 className="h-4 w-4 text-muted-foreground" />
                <h4 className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground">
                    Audio Digest
                </h4>
            </div>

            <audio
                ref={audioRef}
                src={audioUrl}
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleLoadedMetadata}
                onEnded={handleEnded}
                className="hidden"
            />

            <div className="space-y-3">
                {/* Controls row */}
                <div className="flex items-center gap-3">
                    <Button
                        size="sm"
                        variant="outline"
                        className="h-8 w-8 p-0"
                        onClick={togglePlay}
                        aria-label={isPlaying ? "Pause" : "Play"}
                    >
                        {isPlaying ? (
                            <Pause className="h-3.5 w-3.5" />
                        ) : (
                            <Play className="h-3.5 w-3.5" />
                        )}
                    </Button>

                    {/* Progress bar */}
                    <div className="flex-1 flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground font-mono w-10 text-right">
                            {formatTime(currentTime)}
                        </span>
                        <input
                            type="range"
                            min={0}
                            max={duration || 0}
                            value={currentTime}
                            onChange={handleSeek}
                            className="flex-1 h-1 accent-primary cursor-pointer"
                            aria-label="Audio progress"
                        />
                        <span className="text-[10px] text-muted-foreground font-mono w-10">
                            {formatTime(duration)}
                        </span>
                    </div>
                </div>

                {/* Options row */}
                <div className="flex items-center gap-2 flex-wrap">
                    {/* Playback speed */}
                    <Select value={playbackRate} onValueChange={handlePlaybackRateChange}>
                        <SelectTrigger className="w-[80px] h-7 text-[10px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="0.5" className="text-xs">0.5x</SelectItem>
                            <SelectItem value="1" className="text-xs">1x</SelectItem>
                            <SelectItem value="1.5" className="text-xs">1.5x</SelectItem>
                            <SelectItem value="2" className="text-xs">2x</SelectItem>
                        </SelectContent>
                    </Select>

                    {/* Language selector */}
                    {status.available.length > 1 && (
                        <Select value={selectedLanguage} onValueChange={handleLanguageChange}>
                            <SelectTrigger className="w-[120px] h-7 text-[10px]">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {status.available.map((lang) => (
                                    <SelectItem key={lang} value={lang} className="text-xs">
                                        {LANGUAGE_LABELS[lang] || lang}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    )}

                    {/* Download */}
                    <a
                        href={audioUrl}
                        download
                        className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground ml-auto"
                    >
                        <Download className="h-3 w-3" />
                        Download
                    </a>
                </div>
            </div>
        </Card>
    );
}
