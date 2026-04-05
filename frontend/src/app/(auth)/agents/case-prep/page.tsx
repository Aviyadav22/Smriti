"use client";

import { AgentWorkspace } from "@/components/agents/AgentWorkspace";
import { CasePrepInput } from "@/components/agents/inputs/CasePrepInput";

const STEPS = [
    "load_analysis", "prioritize", "checkpoint_issues",
    "deep_search", "argument_order", "checkpoint_strategy",
    "strategy_memo", "verify", "checkpoint_memo",
];

export default function CasePrepPage() {
    return (
        <AgentWorkspace
            agentType="case_prep"
            title="Case Prep Agent"
            description="Select an analyzed document to generate a strategy memo with prioritized issues and precedent search."
            steps={STEPS}
            renderInput={(props) => <CasePrepInput {...props} />}
            newSessionLabel="New Case Prep"
        />
    );
}
