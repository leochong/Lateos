import { useState } from "react";

const phases = [
  {
    id: 0,
    label: "Phase 0",
    title: "Local Environment",
    status: "complete",
    date: "Feb 27, 2026",
    commit: "dd825f6",
    color: "#00ff9d",
    items: [
      "Git repo + Python 3.12 venv",
      "AWS CDK CLI v2.1105.0+",
      "LocalStack via Docker",
      "Pre-commit hooks (9 categories)",
      "CI/CD pipeline (7 jobs)",
      "SECURITY.md + 10 AWS baseline checks",
      "18 smoke tests — all passing",
      "10 ADRs documented",
    ],
  },
  {
    id: 1,
    label: "Phase 1",
    title: "Core Infrastructure",
    status: "complete",
    date: "Feb 27, 2026",
    commit: "Phase 1",
    color: "#00ff9d",
    items: [
      "CoreStack: API Gateway + Cognito MFA",
      "CoreStack: KMS-encrypted CloudWatch",
      "OrchestrationStack: Step Functions",
      "MemoryStack: 4 DynamoDB tables (KMS)",
      "CostProtectionStack: Kill switch at $10",
      "All 4 stacks synth cleanly",
      "ADR-011: WAF deferred (cost)",
      "ADR-013: Python pinned to 3.12",
    ],
  },
  {
    id: 2,
    label: "Phase 2",
    title: "Agent Pipeline",
    status: "complete",
    date: "Feb 28, 2026",
    commit: "f1acb81",
    color: "#00ff9d",
    items: [
      "Validator Lambda (15+ injection patterns)",
      "Orchestrator Lambda (Cognito context)",
      "Intent Classifier (rule-based)",
      "Action Router (built-in handlers)",
      "Output Sanitizer (RULE 8 redaction)",
      "Structured JSON logging",
      "29 files — 4,907 insertions committed",
      "Pre-commit hooks all passing",
    ],
  },
  {
    id: 3,
    label: "Phase 3",
    title: "Skill Lambdas",
    status: "complete",
    date: "In Progress",
    commit: null,
    color: "#ffb800",
    items: [
      "Email skill Lambda (scoped IAM)",
      "Calendar skill Lambda (scoped IAM)",
      "Web fetch skill Lambda (scoped IAM)",
      "File operations skill Lambda (scoped IAM)",
      "Step Functions full workflow wiring",
      "Bedrock Guardrails integration",
      "Full LocalStack integration testing",
      "Fix: Validator test 2 (injection patterns)",
    ],
  },
  {
    id: 4,
    label: "Phase 4",
    title: "Security Hardening",
    status: "active",
    date: "In Progress",
    commit: null,
    color: "#4d9fff",
    items: [
      "Full prompt injection test suite",
      "CVE checklist vs OpenClaw findings",
      "Pentest guide distribution",
      "Cognito advancedSecurityMode fix",
      "DECISIONS.md audit",
      "LATEOS-001–015 error codes implemented",
      "All Lambdas emit structured JSON logs",
      "Security audit agent review",
    ],
  },
  {
    id: 5,
    label: "Phase 5.5",
    title: "Documentation Sprint",
    status: "pending",
    date: "Pre-Launch",
    commit: null,
    color: "#c084fc",
    items: [
      "Code-generated architecture diagram",
      "Threat model diagram (CVE mapping)",
      "Data flow diagram",
      "README full rewrite (CISSP-level)",
      "6 scenario walkthroughs",
      "LATEOS error code catalog",
      "TRADE-OFFS.md + WHAT-WE-REJECTED.md",
      "Quick Start + Lateos vs OpenClaw + Troubleshooting",
    ],
  },
  {
    id: 6,
    label: "Phase 5",
    title: "Public Launch",
    status: "pending",
    date: "March 2026",
    commit: null,
    color: "#ff6b6b",
    items: [
      "LocalStack full integration test",
      "lateos.ai domain live",
      "github.com/Leochong/lateos public",
      "Wave 1 LinkedIn post",
      "Community pentest open",
      "AWS Marketplace evaluation",
      "CONTRIBUTING.md published",
      "SECURITY.md published",
    ],
  },
  {
    id: 7,
    label: "Phase 6",
    title: "Autonomous Scheduling",
    status: "future",
    date: "Post-Launch",
    commit: null,
    color: "#fb923c",
    items: [
      "EventBridge Scheduler (replaces heartbeat timer)",
      "Controlled Schedule Registry (DynamoDB)",
      "Approved intent whitelist (no arbitrary cron)",
      "Mandatory user confirmation for schedules",
      "Schedule expiry enforcement",
      "ADR-015: vs OpenClaw self-writing cron",
      "Threat model update for scheduling",
      "Wave 2 LinkedIn post",
    ],
  },
  {
    id: 8,
    label: "Phase 7",
    title: "HITL Browser Control",
    status: "future",
    date: "Community-Informed",
    commit: null,
    color: "#38bdf8",
    items: [
      "Step Functions waitForTaskToken approval gate",
      "Sandboxed Playwright/Chromium Lambda container",
      "Ephemeral sessions — no persistent browser auth",
      "Credentials via Secrets Manager per-task only",
      "Domain whitelist + action whitelist enforcement",
      "Screenshot audit trail → S3 + CloudTrail",
      "DENY gate: user can abort any browser action",
      "ADR-017: HITL vs autonomous browser (rejected)",
      "Threat model: browser-specific attack vectors",
      "Wave 3 LinkedIn post",
    ],
  },
  {
    id: 9,
    label: "Phase 8",
    title: "Controlled Shell Execution",
    status: "future",
    date: "Need-Based",
    commit: null,
    color: "#e879f9",
    items: [
      "Command whitelist only — no blacklist approach",
      "Ephemeral Lambda sandbox — destroyed after execution",
      "HITL approval gate — user approves exact command",
      "No network access during execution (VPC isolated)",
      "S3 scoped I/O only — no local filesystem",
      "Output sanitizer — redacts credentials from stdout",
      "Execution size + time limits enforced",
      "Full CloudTrail + DynamoDB audit trail",
      "ADR-018: Need-based shell restriction model",
      "Activated only when skill tasks require it",
    ],
  },
];

const statusConfig = {
  complete: { label: "COMPLETE", bg: "rgba(0,255,157,0.15)", border: "rgba(0,255,157,0.4)" },
  active: { label: "IN PROGRESS", bg: "rgba(255,184,0,0.15)", border: "rgba(255,184,0,0.4)" },
  pending: { label: "UPCOMING", bg: "rgba(77,159,255,0.1)", border: "rgba(77,159,255,0.25)" },
  future: { label: "PLANNED", bg: "rgba(251,146,60,0.1)", border: "rgba(251,146,60,0.25)" },
};

export default function LateosRoadmap() {
  const [selected, setSelected] = useState(3);

  const phase = phases[selected];
  const cfg = statusConfig[phase.status];

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0a0e1a",
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
      color: "#e2e8f0",
      display: "flex",
      flexDirection: "column",
    }}>
      {/* Header */}
      <div style={{
        padding: "32px 40px 24px",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        background: "linear-gradient(180deg, rgba(0,255,157,0.04) 0%, transparent 100%)",
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
          <span style={{
            fontSize: 28,
            fontWeight: 800,
            letterSpacing: "-0.02em",
            color: "#00ff9d",
          }}>LATEOS</span>
          <span style={{ color: "rgba(255,255,255,0.3)", fontSize: 13 }}>/ PROJECT ROADMAP</span>
        </div>
        <div style={{ marginTop: 6, fontSize: 12, color: "rgba(255,255,255,0.35)", letterSpacing: "0.08em" }}>
          github.com/Leochong/lateos · lateos.ai · security-by-design AI agent
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: Phase list */}
        <div style={{
          width: 220,
          borderRight: "1px solid rgba(255,255,255,0.06)",
          padding: "24px 0",
          overflowY: "auto",
          flexShrink: 0,
        }}>
          {phases.map((p) => {
            const isSelected = selected === p.id;
            const sc = statusConfig[p.status];
            return (
              <div
                key={p.id}
                onClick={() => setSelected(p.id)}
                style={{
                  padding: "14px 20px",
                  cursor: "pointer",
                  borderLeft: isSelected ? `3px solid ${p.color}` : "3px solid transparent",
                  background: isSelected ? "rgba(255,255,255,0.04)" : "transparent",
                  transition: "all 0.15s ease",
                  position: "relative",
                }}
              >
                <div style={{
                  fontSize: 10,
                  letterSpacing: "0.12em",
                  color: isSelected ? p.color : "rgba(255,255,255,0.3)",
                  marginBottom: 4,
                  fontWeight: 700,
                }}>
                  {p.label}
                </div>
                <div style={{
                  fontSize: 13,
                  color: isSelected ? "#e2e8f0" : "rgba(255,255,255,0.5)",
                  fontWeight: isSelected ? 600 : 400,
                  lineHeight: 1.3,
                }}>
                  {p.title}
                </div>
                <div style={{
                  marginTop: 6,
                  display: "inline-block",
                  fontSize: 9,
                  letterSpacing: "0.1em",
                  padding: "2px 6px",
                  borderRadius: 3,
                  background: sc.bg,
                  border: `1px solid ${sc.border}`,
                  color: p.color,
                  fontWeight: 700,
                }}>
                  {sc.label}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right: Detail */}
        <div style={{ flex: 1, padding: "32px 40px", overflowY: "auto" }}>
          {/* Phase header */}
          <div style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            marginBottom: 32,
            paddingBottom: 24,
            borderBottom: `1px solid ${phase.color}22`,
          }}>
            <div>
              <div style={{
                fontSize: 11,
                letterSpacing: "0.15em",
                color: phase.color,
                fontWeight: 700,
                marginBottom: 8,
              }}>
                {phase.label} — {statusConfig[phase.status].label}
              </div>
              <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.02em", color: "#f1f5f9" }}>
                {phase.title}
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: "rgba(255,255,255,0.35)" }}>
                {phase.date}
                {phase.commit && (
                  <span style={{
                    marginLeft: 12,
                    padding: "2px 8px",
                    background: "rgba(0,255,157,0.1)",
                    border: "1px solid rgba(0,255,157,0.2)",
                    borderRadius: 4,
                    color: "#00ff9d",
                    fontSize: 11,
                  }}>
                    ✓ {phase.commit}
                  </span>
                )}
              </div>
            </div>

            {/* Status ring */}
            <div style={{
              width: 72,
              height: 72,
              borderRadius: "50%",
              border: `2px solid ${phase.color}`,
              background: `${phase.color}11`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              boxShadow: `0 0 20px ${phase.color}33`,
            }}>
              <span style={{ fontSize: 24, fontWeight: 900, color: phase.color }}>
                {phase.id}
              </span>
            </div>
          </div>

          {/* Items grid */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 12,
          }}>
            {phase.items.map((item, i) => (
              <div
                key={i}
                style={{
                  padding: "14px 16px",
                  background: "rgba(255,255,255,0.03)",
                  border: `1px solid rgba(255,255,255,0.07)`,
                  borderRadius: 8,
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 10,
                  transition: "border-color 0.15s",
                }}
              >
                <span style={{
                  color: phase.status === "complete" ? "#00ff9d" : phase.color,
                  fontSize: 14,
                  lineHeight: 1.5,
                  flexShrink: 0,
                }}>
                  {phase.status === "complete" ? "✓" : "○"}
                </span>
                <span style={{ fontSize: 12, color: "rgba(255,255,255,0.7)", lineHeight: 1.6 }}>
                  {item}
                </span>
              </div>
            ))}
          </div>

          {/* Phase 6 special callout */}
          {phase.id === 9 && (
            <div style={{
              marginTop: 28,
              padding: "20px 24px",
              background: "rgba(232,121,249,0.07)",
              border: "1px solid rgba(232,121,249,0.2)",
              borderRadius: 10,
            }}>
              <div style={{ fontSize: 11, color: "#e879f9", fontWeight: 700, letterSpacing: "0.1em", marginBottom: 8 }}>
                NEED-BASED RESTRICTION MODEL
              </div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.6)", lineHeight: 1.8 }}>
                Shell execution is not excluded forever — it is excluded until a skill task
                genuinely requires it. When that need is validated by the community, Lateos
                enables it under the strictest possible constraints: command whitelist, ephemeral
                sandbox, HITL approval, no network, scoped I/O, full audit trail. OpenClaw gave
                shell access to everyone by default. Lateos enables it only when needed, only
                for what is needed, only with human approval.
              </div>
            </div>
          )}

          {phase.id === 8 && (
            <div style={{
              marginTop: 28,
              padding: "20px 24px",
              background: "rgba(56,189,248,0.07)",
              border: "1px solid rgba(56,189,248,0.2)",
              borderRadius: 10,
            }}>
              <div style={{ fontSize: 11, color: "#38bdf8", fontWeight: 700, letterSpacing: "0.1em", marginBottom: 8 }}>
                WHY COMMUNITY FIRST
              </div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.6)", lineHeight: 1.8 }}>
                Browser control is the highest-risk capability an AI agent can have. OpenClaw shipped it
                autonomously and got 512 CVEs. Lateos will implement it only after real users have pentested
                the core architecture and told us what browser tasks they actually need. HITL approval gates
                make silent attacks architecturally impossible — every browser action pauses and asks you first.
              </div>
            </div>
          )}

          {phase.id === 7 && (
            <div style={{
              marginTop: 28,
              padding: "20px 24px",
              background: "rgba(251,146,60,0.07)",
              border: "1px solid rgba(251,146,60,0.2)",
              borderRadius: 10,
            }}>
              <div style={{ fontSize: 11, color: "#fb923c", fontWeight: 700, letterSpacing: "0.1em", marginBottom: 8 }}>
                WHY NOT OPENCLAW'S APPROACH
              </div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.6)", lineHeight: 1.8 }}>
                OpenClaw allows agents to write arbitrary cron expressions to disk files — a prompt injection time-bomb.
                A single injection attack can schedule malicious future tasks indefinitely. Lateos Phase 6 implements
                the same autonomous scheduling capability using EventBridge + an approved intent whitelist stored in
                DynamoDB. Same power. Zero arbitrary code scheduling.
              </div>
            </div>
          )}

          {/* Progress bar across all phases */}
          <div style={{ marginTop: 40, paddingTop: 28, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ fontSize: 11, letterSpacing: "0.1em", color: "rgba(255,255,255,0.3)", marginBottom: 14, fontWeight: 700 }}>
              OVERALL PROGRESS
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              {phases.map((p) => (
                <div
                  key={p.id}
                  onClick={() => setSelected(p.id)}
                  title={`${p.label}: ${p.title}`}
                  style={{
                    flex: 1,
                    height: 6,
                    borderRadius: 3,
                    background: p.status === "complete"
                      ? "#00ff9d"
                      : p.status === "active"
                      ? "#ffb800"
                      : "rgba(255,255,255,0.1)",
                    cursor: "pointer",
                    transition: "opacity 0.15s",
                    opacity: selected === p.id ? 1 : 0.7,
                    boxShadow: p.status === "complete" ? "0 0 8px rgba(0,255,157,0.4)" : "none",
                  }}
                />
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
              <span style={{ fontSize: 10, color: "rgba(255,255,255,0.25)" }}>Phase 0</span>
              <span style={{ fontSize: 11, color: "#00ff9d", fontWeight: 700 }}>
                4 / 9 phases complete
              </span>
              <span style={{ fontSize: 10, color: "rgba(255,255,255,0.25)" }}>Phase 6</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
