import type { ChapterConfig } from "./types";
import { ch00TheSpark } from "./ch00-the-spark";
import { ch01LayingTheFoundation } from "./ch01-laying-the-foundation";
import { ch02TeachingSmritiToRead } from "./ch02-teaching-smriti-to-read";
import { ch03ThreeWaysToRemember } from "./ch03-three-ways-to-remember";
import { ch04TheSearch } from "./ch04-the-search";
import { ch05TheSecretSauce } from "./ch05-the-secret-sauce";
import { ch06TheCitationWeb } from "./ch06-the-citation-web";
import { ch07TheResearchAgent } from "./ch07-the-research-agent";
import { ch08BuildingTheInterface } from "./ch08-building-the-interface";
import { ch09Hardening } from "./ch09-hardening";
import { ch10RoadAhead } from "./ch10-road-ahead";

export const chapterConfigs: Record<string, ChapterConfig> = {
  ch00: ch00TheSpark,
  ch01: ch01LayingTheFoundation,
  ch02: ch02TeachingSmritiToRead,
  ch03: ch03ThreeWaysToRemember,
  ch04: ch04TheSearch,
  ch05: ch05TheSecretSauce,
  ch06: ch06TheCitationWeb,
  ch07: ch07TheResearchAgent,
  ch08: ch08BuildingTheInterface,
  ch09: ch09Hardening,
  ch10: ch10RoadAhead,
};

export function getChapterConfig(id: string): ChapterConfig | undefined {
  return chapterConfigs[id];
}

export type { ChapterConfig, Section } from "./types";
