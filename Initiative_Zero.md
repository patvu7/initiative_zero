# Initiative Zero: AI-Native Code Modernization

## What the Human Can Now Do

A pod of engineers can safely modernize Wealthsimple's portfolio rebalancing engine, moving it from overnight batch processing to real-time execution, in 8 weeks instead of 18 months, without risking the live system.

Today, that work requires 12–15 specialists, multi-year timelines, and a high-risk cutover. Developers spend 17.3 hours per week on technical debt instead of building (McKinsey). 70% of organizations cite tech debt as their primary innovation blocker (Protiviti), rising to 78% in financial services. Meanwhile, 250 billion lines of COBOL remain in production worldwide, but the engineers who wrote them are retiring. Traditional migrations fail. Lift-and-shift just relocates problems, and line-by-line translation carries forward decades of debt.

Initiative Zero takes a different path. AI agents extract business rules from legacy code and produce a clean, technology-agnostic specification of *what the system does*. A new application is generated from scratch, in any target language. Technical debt stays behind. For Wealthsimple, this means systems like portfolio rebalancing, tax-lot accounting, and compliance reporting can be rebuilt on modern architectures that support the real-time, personalized experience clients expect. The same pipeline works for any system where critical business logic is trapped in aging code.

The 8-week timeline reflects the phased approach recommended by Anthropic's Code Modernization Playbook: 2 weeks of code archaeology and dependency mapping, 2 weeks of AI-driven analysis and proof of concept, and 4 weeks of full migration with parallel validation. A traditional rewrite of the same system typically runs 12–18 months because teams must reverse-engineer undocumented business logic manually. AI compresses that comprehension phase from months to days, which is where the time savings come from.

## What AI Is Responsible For

AI handles the cognitive heavy lifting that previously required scarce specialists, producing reusable artifacts at each stage. But it also serves as an architectural thought partner throughout the process. Engineers don't just kick off a pipeline and wait. They work conversationally with AI to explore design alternatives, pressure-test migration strategies, and understand *why* certain architectural decisions improve the system, not just *what* to change. This iterative back-and-forth is what makes a 3-person team effective where a 15-person team used to be necessary.

**Comprehension.** AI analyzes legacy code (COBOL, Java, C#) and produces a standardized Analysis Report: dependency maps, technical debt assessment, coverage gaps, and migration economics, including a confidence score that quantifies readiness.

**Business Rule Extraction.** AI distills business logic from implementation details, cross-referenced against actual production behavior via read-only telemetry. The output is a technology-agnostic requirements document describing *what* the system does, not *how* it was built. For a portfolio rebalancing engine, this means capturing rules like drift thresholds, tax-loss harvesting triggers, and asset allocation constraints in plain language that any engineer can read.

**Code Generation.** From that requirements document alone, with no source code, external AI generates a greenfield application. Each method traces to a named business rule. Proprietary code never leaves the internal network; only the plain-text specification crosses the security boundary.

**Testing and Drift Classification.** AI generates tests from the same requirements, runs both systems against identical inputs, and classifies every difference: identical, cosmetic, semantic (needs human judgment), or breaking.

## Where AI Must Stop

One decision must remain human: confirming that the AI's understanding of the business rules matches what the system *should* do. This is the specification sign-off.

AI cannot verify its own comprehension of business intent. It can extract what code *does*, but only someone who understands the domain can confirm that what the code does is what the business actually wants. If a rebalancing engine has a hardcoded 5% drift threshold, AI will faithfully extract that rule. But whether 5% is still the right threshold, whether it was a deliberate choice or an outdated default, that's a judgment call only a domain expert can make.

This sign-off matters structurally because the validated specification is the only artifact that reaches external AI for code generation. Errors here propagate through every downstream zone. The security boundary and the intellectual validation are separate concerns, but they converge at the same gate: nothing crosses until a human says the spec is right.

## The Human's Role After Deployment

The human's job doesn't end at sign-off. After the modernized system goes live, the 3-person team shifts into a monitoring and adjudication role. They watch drift classification dashboards that continuously compare the new system's outputs against the legacy system running in parallel. When the system flags a semantic difference, one that isn't clearly cosmetic or clearly breaking, a human decides whether it's acceptable or needs investigation.

Over time, as confidence builds and the legacy system is decommissioned, the team's focus moves from monitoring parity to improving the new system: adding capabilities that the old architecture couldn't support, like real-time rebalancing triggers or client-specific optimization rules. The AI keeps working as a thought partner through this phase too, helping the team evaluate new feature designs and catch regressions before they reach production.

## What Would Break First at Scale

The SME validation bottleneck. AI can extract rules from dozens of systems in parallel, but each extraction requires roughly 2 weeks of domain expert review. With a typical pool of 2–3 SMEs per legacy system and 5–7 critical systems in a portfolio, the review queue becomes the critical path.

There's a compounding benefit that eases this over time. Each validated system teaches the AI reusable domain patterns. Client onboarding, compliance checks, and transaction routing share common structures across systems. So the second system's review is lighter than the first, and the third lighter still. But the first 2–3 systems absorb the highest cost, and planning must account for that ramp.
