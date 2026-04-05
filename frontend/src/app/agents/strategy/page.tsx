"use client";

import { AgentWorkspace } from "@/components/agents/AgentWorkspace";
import { StrategyInput } from "@/components/agents/inputs/StrategyInput";

const STEPS = [
    "analyze_facts", "element_decomposition", "fetch_judge",
    "checkpoint_analysis", "search_precedents", "evaluate_relevance", "assess_strength",
    "generate_arguments_irac", "checkpoint_arguments",
    "adversarial_search", "counter_and_judge", "argument_ordering",
    "synthesize_strategy", "format_footnotes", "verify",
    "quality_check", "checkpoint_memo",
];

export default function StrategyPage() {
    return (
        <AgentWorkspace
            agentType="strategy"
            title="Argument Builder"
            description="Enter case facts and desired relief. The agent generates IRAC arguments with verified precedents."
            steps={STEPS}
            renderInput={(props) => <StrategyInput {...props} />}
            newSessionLabel="New Argument Brief"
        />
    );
}
