import { TypewriterText } from "@/components/chapters/TypewriterText";
import { ProseBlock } from "@/components/chapters/ProseBlock";
import { ComparisonSlide } from "@/components/chapters/ComparisonSlide";
import { TimelineDraw } from "@/components/chapters/TimelineDraw";
import { CardCascade } from "@/components/chapters/CardCascade";
import { CodeReveal } from "@/components/chapters/CodeReveal";
import { CounterAnimation } from "@/components/chapters/CounterAnimation";
import { StatBlock } from "@/components/chapters/StatBlock";
import { HighlightBox } from "@/components/chapters/HighlightBox";
import { FlowDiagram } from "@/components/chapters/FlowDiagram";
import type { Section } from "./types";

export function renderSection(section: Section): React.ReactNode {
  switch (section.type) {
    case "typewriter":
      return (
        <TypewriterText
          text={section.text}
          className={section.className}
          speed={section.speed}
        />
      );
    case "prose":
      return <ProseBlock>{section.content}</ProseBlock>;
    case "comparison":
      return <ComparisonSlide left={section.left} right={section.right} />;
    case "timeline":
      return <TimelineDraw milestones={section.milestones} />;
    case "cards":
      return <CardCascade cards={section.cards} columns={section.columns} />;
    case "code":
      return <CodeReveal code={section.code} language={section.language} />;
    case "counter":
      return (
        <div className="text-center py-8">
          <CounterAnimation
            from={section.from}
            to={section.to}
            prefix={section.prefix}
            suffix={section.suffix}
            className="text-5xl font-heading text-[#C5A880]"
          />
          <p className="text-sm text-[#666] mt-2">{section.label}</p>
        </div>
      );
    case "heading":
      return section.level === 3 ? (
        <h3 className="text-xl font-heading text-[#E0E0E0] mb-4">
          {section.text}
        </h3>
      ) : (
        <h2 className="text-2xl font-heading text-[#E0E0E0] mb-4">
          {section.text}
        </h2>
      );
    case "quote":
      return (
        <blockquote className="border-l-2 border-[#C5A880]/40 pl-6 py-2 italic text-[#999]">
          <p className="text-lg">{section.text}</p>
          {section.attribution && (
            <cite className="text-sm text-[#666] mt-2 block not-italic">
              — {section.attribution}
            </cite>
          )}
        </blockquote>
      );
    case "spacer":
      return <div style={{ height: section.height || "4rem" }} />;
    case "stats":
      return <StatBlock items={section.items} />;
    case "highlight-box":
      return <HighlightBox icon={section.icon} title={section.title} description={section.description} accent={section.accent} />;
    case "flow":
      return <FlowDiagram steps={section.steps} />;
    default:
      return null;
  }
}
