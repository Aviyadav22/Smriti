import type { ChapterConfig } from "./types";

export const ch06TheCitationWeb: ChapterConfig = {
  id: "06-the-citation-web",
  title: "The Citation Web",
  subtitle: "Mapping the invisible network connecting 35,000 cases",
  sections: [
    {
      type: "stats",
      items: [
        { icon: "🔵", value: "35,000", label: "case nodes" },
        { icon: "🔗", value: "200K+", label: "citation edges" },
        { icon: "📋", value: "16", label: "citation formats parsed" },
        { icon: "🏷️", value: "4", label: "relationship types" },
      ],
    },
    {
      type: "cards",
      cards: [
        {
          title: "BINDING",
          description:
            "Must be followed -- same court or higher court precedent, the strongest authority.",
          icon: "🔒",
        },
        {
          title: "PERSUASIVE",
          description:
            "Can be considered -- different court or older judgment, influential but not mandatory.",
          icon: "👍",
        },
        {
          title: "DISTINGUISHED",
          description:
            "Similar but different facts -- the court acknowledges but finds it inapplicable.",
          icon: "🔀",
        },
        {
          title: "OVERRULED",
          description:
            "No longer good law -- a later, larger bench has explicitly rejected this precedent.",
          icon: "❌",
        },
      ],
      columns: 2,
    },
    {
      type: "code",
      code: `// Neo4j: Find all cases that cited Bachan Singh
MATCH (landmark:Case {title: "Bachan Singh v. State of Punjab"})
  <-[:CITES]-(citing:Case)
RETURN citing.title, citing.year, citing.citation
ORDER BY citing.year DESC

// Result: The entire chain of death penalty jurisprudence
// from 1980 to present, showing how the law evolved`,
      language: "cypher",
    },
    {
      type: "highlight-box",
      icon: "🕸️",
      title: "The Graph Power",
      description:
        "Citation communities are clusters of heavily interconnected cases detected by graph algorithms -- they map to legal topics like 'Bail under NDPS Act' or 'Right to Privacy'.",
      accent: "#C5A880",
    },
    {
      type: "quote",
      text: "When you find a relevant case, Neo4j tells you every case that cited it, distinguished it, or overruled it. No other Indian legal AI does this.",
    },
  ],
};
