# Lessons Learned Building Lateos

**Author:** Leo Chong
**Written:** [To be completed by Leo before public launch]
**Purpose:** Document real problems encountered during development and how they were solved

---

**IMPORTANT:** This document is intentionally written by the project lead (Leo) in his own words, not AI-generated. It demonstrates genuine understanding of the challenges faced during development and serves as a credibility signal that this project was thoughtfully engineered, not "vibe coded."

---

## The Python 3.14 / JSII Incompatibility

[Leo to write: What happened when we tried Python 3.14, how we discovered the JSII incompatibility, why we decided to pin to Python 3.12, what this taught us about dependency management in CDK projects]

---

## The `constructs/` Directory Naming Conflict

[Leo to write: How the infrastructure/constructs/ directory shadowed the pip constructs package, what errors this caused during CDK synthesis, how we discovered the issue, why we renamed it to cdk_constructs/, what this taught us about Python's import system]

---

## Why WAF Was Deferred to Phase 2

[Leo to write: Initial plan to include WAF in Phase 1, cost analysis showing $8-15/month for local development, decision to defer per ADR-011, trade-offs considered, when WAF will be enabled for production]

---

## LocalStack vs. Real AWS: The Testing Gap

[Leo to write: Differences encountered between LocalStack and real AWS, specific services that behave differently, how this affected testing strategy, lessons about when to trust LocalStack vs. when to validate on real AWS]

---

## The Prompt Injection Detection Threshold (2+ Patterns)

[Leo to write: Initial approach, false positive problems with single-pattern threshold, decision to change to 2+ patterns per ADR-014, how we validated this decision with real test cases, what edge cases we're still monitoring]

---

## Bedrock Guardrails on Output Only (Not Input)

[Leo to write: Initial plan for dual input+output Guardrails, cost analysis showing 50% savings with output-only, security trade-off discussion, why we decided this was acceptable per ADR-015, what monitoring we put in place]

---

## One IAM Role Per Skill Lambda

[Leo to write: Initial consideration of shared IAM role, security analysis of blast radius, decision to implement ADR-016 (one role per skill), how this affected CDK code organization, what this taught us about defense in depth]

---

## What I'd Do Differently Next Time

[Leo to write: Reflections on the overall development process, what worked well, what could be improved, advice for others building similar systems, honest assessment of AI-assisted development approach]

---

## Notes for Future Maintainers

[Leo to write: Things to watch out for when extending Lateos, common pitfalls, architectural decisions that are fragile and might need refactoring, technical debt that was intentionally accepted]

---

**End of Document**

*This document will be completed by Leo Chong before the public launch of Lateos. The headers above provide structure for documenting the real challenges and decisions made during development, proving this was an engineered project with thoughtful trade-offs, not a code dump from an AI assistant.*
