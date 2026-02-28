# Lateos — Complete File Package Summary

**Updated:** February 17, 2026  
**Project:** Lateos (from Latin *lateo* — "to lie hidden, to be concealed")  
**Lead:** Leo Chong (@Leochong)  
**Timeline:** Local dev Feb 28-Mar 1, Public launch March 1, 2026

---

## ✅ All Files Updated with Lateos Branding

Every reference to "SecureAgent" has been replaced with "Lateos" throughout all files.

---

## 📁 File Inventory

### Core Context Files (14 total)

```
lateos/
├── CLAUDE.md                           [Root context - start here]
├── .claude/
│   ├── security-patterns.md            [Security quick reference]
│   ├── agents/                         [8 subagent definitions]
│   │   ├── orchestrator.md             (sonnet)
│   │   ├── explore-agent.md            (haiku)
│   │   ├── iac-agent.md                (sonnet)
│   │   ├── lambda-agent.md             (sonnet)
│   │   ├── tests-agent.md              (haiku)
│   │   ├── security-audit-agent.md     (opus)
│   │   ├── docs-agent.md               (haiku)
│   │   └── file-ops-agent.md           (haiku)
│   └── commands/
│       └── README.md                   [Custom slash commands]
├── infrastructure/
│   └── CLAUDE.md                       [CDK + AWS patterns]
├── lambdas/
│   └── CLAUDE.md                       [Lambda handler patterns]
└── tests/
    └── CLAUDE.md                       [Testing standards]
```

### Supporting Documents (4 total)

```
lateos-kickstart-prompt.md              [Phase 0 setup instructions - UPDATED for March 1]
lateos-project-tree.md                  [Complete 75-file project structure]
PENTEST-GUIDE.md                        [Community penetration testing guide]
linkedin-wave1-post.md                  [Two LinkedIn post variants - UPDATED]
```

---

## 🗓️ Your Timeline (Stealth Mode → Public Launch)

### Feb 17-27 (Next 10 Days — Still at Philips)

- ❌ **Do NOT start coding yet**
- ❌ **Do NOT create public GitHub repo yet**
- ✅ Review all downloaded Lateos context files
- ✅ Set up local dev environment (AWS CLI, Python 3.12, Node.js, Docker)
- ✅ Test kickstart prompt in a scratch directory locally
- ✅ Refine LinkedIn network, engage with security posts
- ✅ Collect more OpenClaw CVEs as they emerge

### Feb 28 (Day 1 — Your Clean Start)

- ✅ Create **local** Git repo: `git init lateos/`
- ✅ Copy in all 14 CLAUDE.md and agent files
- ✅ Create .gitignore manually (critical first step)
- ✅ Open Claude Code and paste the kickstart prompt
- ✅ Complete Phase 0 (scaffolding, CI/CD, tests)
- Repository stays **local only** — no GitHub push yet

### March 1 (Public Launch Day)

- ✅ Create public GitHub repo: <https://github.com/Leochong/lateos>
- ✅ Push Phase 0 completion to GitHub
- ✅ Add this conversation URL to README credits
- ✅ Post Wave 1 on LinkedIn (choose spicy or measured variant)
- ✅ First comment: link to the design conversation
- ✅ Watch the security community find it

---

## 📋 Day 1 (Feb 28) Checklist

When you sit down on Feb 28 to actually start building:

```bash
# 1. Create the directory
mkdir lateos && cd lateos

# 2. Copy in ALL 14 context files from your downloads
#    (the lateos/ folder structure you downloaded)

# 3. Initialize Git BEFORE doing anything else
git init
git add .
git commit -m "feat: add Claude Code context files and agent definitions"

# 4. Create .gitignore IMMEDIATELY
cat > .gitignore << 'EOF'
# Critical patterns - add more from kickstart prompt
.env
.env.*
!.env.example
*.pem
*.key
credentials
.aws/
cdk.out/
__pycache__/
.pytest_cache/
node_modules/
EOF

git add .gitignore
git commit -m "feat: add comprehensive .gitignore"

# 5. Open Claude Code
claude

# 6. Paste the FULL kickstart prompt
#    (from lateos-kickstart-prompt.md)

# 7. Let Claude Code build Phase 0
#    It will create 10 files:
#    - .env.example
#    - .pre-commit-config.yaml
#    - cdk.json
#    - requirements.txt + requirements-dev.txt
#    - .github/workflows/ci.yml
#    - SECURITY.md
#    - README.md
#    - scripts/verify_account_baseline.py
#    - tests/infrastructure/test_phase0.py

# 8. Verify Phase 0 completion
pre-commit run --all-files
pytest tests/infrastructure/test_phase0.py -v
cdk synth

# 9. Commit Phase 0
git add .
git commit -m "feat: complete Phase 0 - project scaffolding and CI/CD"

# 10. STOP — keep it local until March 1
#     Do NOT push to GitHub yet
```

---

## 🎯 March 1 Launch Checklist

When you're ready to go public:

```bash
# 1. Create public GitHub repo (via web UI)
#    Name: lateos
#    Description: Security-by-design AI personal agent (AWS serverless)
#    Public, MIT license

# 2. Add the remote and push
git remote add origin https://github.com/Leochong/lateos.git
git branch -M main
git push -u origin main

# 3. Update README.md credits section
#    Add this conversation URL:
#    https://claude.ai/chat/[YOUR_CONVERSATION_ID]

git add README.md
git commit -m "docs: add design conversation link to credits"
git push

# 4. Post on LinkedIn
#    Choose spicy or measured variant
#    Copy/paste, add GitHub link
#    First comment: link to design conversation

# 5. Optional: Comment on Daniel Kelley's OpenClaw post
#    (the one with 512 vulnerabilities)
#    Add value, don't promote - let people find you
```

---

## 🔒 Key Security Points (Don't Forget These)

1. **Never commit .env** — .gitignore it on Day 1
2. **All secrets in Secrets Manager** — zero plaintext files, zero env vars with values
3. **Pre-commit hooks run automatically** — catch secrets before they're committed
4. **CI pipeline blocks merge if security scans fail** — this is your safety net
5. **Security audit agent runs last** — opus-powered, read-only, must APPROVE before merge

---

## 💡 Why "Lateos"?

*Lateo* (Latin) — "to lie hidden, to be concealed"

Your agent operates invisibly in AWS serverless infrastructure. Secrets are hidden in Secrets Manager. No exposed ports. No visible attack surface. The name literally describes the architecture.

Use this in your README introduction and LinkedIn post — it's great branding.

---

## 📞 What to Do if You Get Stuck

**Before March 1 (local development):**

- Test things in a scratch directory first
- Read the CLAUDE.md files — they have the answers
- Phase 0 is just scaffolding — no complex code yet

**After March 1 (public repo):**

- Create GitHub issues for questions
- Security researchers will start opening issues — engage with them
- The community will help if the foundation is solid

---

## 🚀 Final Note

You're not just building an alternative to OpenClaw. You're demonstrating what security-first AI development looks like when a CISSP Healthcare IT professional uses Claude Code properly.

The design conversation being public is your competitive moat. Anyone can copy your code. Very few people can replicate the thought process that went into designing it.

**Good luck, Leo. Go build Lateos.**

---

**Next steps:**

1. Download all files from this conversation
2. Review them over the next 10 days
3. Feb 28: Actually start building (local only)
4. March 1: Go public with Phase 0 complete

The iron is hot. The OpenClaw conversation won't last forever. Launch on March 1.
