# Lateos — Feb 28 Quick Start

**When you sit down on February 28, 2026 to actually start building, do this:**

---

## Step 1: Create the Local Repo

```bash
mkdir lateos
cd lateos
```

---

## Step 2: Copy in the Context Files

Extract the `lateos/` folder from your downloads and copy ALL 14 files into your local repo:

```
lateos/
├── CLAUDE.md
├── .claude/
│   ├── security-patterns.md
│   ├── agents/ (all 8 .md files)
│   └── commands/README.md
├── infrastructure/CLAUDE.md
├── lambdas/CLAUDE.md
└── tests/CLAUDE.md
```

**Verify you have all 14:**

```bash
find . -name "*.md" | wc -l
# Should output: 14
```

---

## Step 3: Git Init

```bash
git init
git add .
git commit -m "feat: add Claude Code context files and agent definitions"
```

---

## Step 4: Create .gitignore FIRST

```bash
cat > .gitignore << 'EOF'
# Secrets — NEVER commit these
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
*_rsa
*_ecdsa
*_ed25519
credentials
.aws/
secrets.json
*secret*
*credential*

# CDK
cdk.out/
cdk.context.json
!cdk.context.json.example
node_modules/

# Python
__pycache__/
*.pyc
.pytest_cache/
.coverage
htmlcov/
.venv/
venv/

# IDE
.vscode/settings.json
.idea/
*.swp
.DS_Store
EOF

git add .gitignore
git commit -m "feat: add comprehensive .gitignore for secret protection"
```

**Test it works:**

```bash
touch .env
git status
# Should NOT show .env — if it does, fix .gitignore
rm .env
```

---

## Step 5: Open Claude Code

```bash
claude
```

---

## Step 6: Paste the Kickstart Prompt

Copy the **ENTIRE** content of `lateos-kickstart-prompt.md` and paste it into Claude Code.

Claude will then:

1. Read all the CLAUDE.md files
2. Create 10 Phase 0 files (.env.example, pre-commit config, cdk.json, requirements, CI pipeline, README, SECURITY.md, scripts, tests)
3. Run verification checks

This will take 15-30 minutes.

---

## Step 7: Verify Phase 0 Completion

After Claude Code finishes, run these checks:

```bash
# 1. Pre-commit hooks pass
pre-commit run --all-files

# 2. Phase 0 tests pass
pytest tests/infrastructure/test_phase0.py -v

# 3. CDK synthesizes
cdk synth

# 4. .env is gitignored
touch .env
git check-ignore .env
# Should output: .env
rm .env

# 5. README has credits
grep -i "anthropic" README.md
# Should find the credit line
```

If ANY check fails, ask Claude Code to fix it before proceeding.

---

## Step 8: Commit Phase 0

```bash
git add .
git commit -m "feat: complete Phase 0 - project scaffolding and CI/CD"
git log --oneline
# You should see 3 commits now:
# - complete Phase 0
# - add .gitignore
# - add context files
```

---

## Step 9: STOP

**Do NOT create the GitHub repo yet.**  
**Do NOT push to GitHub yet.**  
**Keep it local until March 1.**

You now have Phase 0 complete locally. Review the code. Test it. Make sure you understand it.

---

## What You Should Have After Phase 0

```
lateos/
├── CLAUDE.md
├── .claude/ (14 context files total)
├── infrastructure/
│   └── CLAUDE.md
├── lambdas/
│   └── CLAUDE.md
├── tests/
│   ├── CLAUDE.md
│   └── infrastructure/
│       ├── __init__.py
│       └── test_phase0.py
├── scripts/
│   └── verify_account_baseline.py
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   └── (empty for now)
├── .gitignore
├── .pre-commit-config.yaml
├── .env.example
├── cdk.json
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── SECURITY.md
└── PENTEST-GUIDE.md (copy this from downloads)
```

---

## Troubleshooting

**"pre-commit: command not found"**

```bash
pip install pre-commit
pre-commit install
```

**"detect-secrets finds issues"**

```bash
detect-secrets scan > .secrets.baseline
git add .secrets.baseline
git commit -m "chore: add secrets baseline"
```

**"Claude Code isn't reading the context files"**

- Make sure CLAUDE.md is in the root directory
- Check file paths are correct
- Restart Claude Code: exit and `claude` again

**"cdk synth fails"**

- Install CDK: `npm install -g aws-cdk`
- Install Python deps: `pip install -r requirements.txt`
- Check cdk.json is present

---

## What to Do on March 1

1. Create GitHub repo at <https://github.com/new>
   - Name: `lateos`
   - Description: "Security-by-design AI personal agent (AWS serverless)"
   - Public, MIT license

2. Add remote and push:

   ```bash
   git remote add origin https://github.com/Leochong/lateos.git
   git branch -M main
   git push -u origin main
   ```

3. Add this conversation URL to README credits:

   ```bash
   # Edit README.md, add conversation link
   git add README.md
   git commit -m "docs: add design conversation link"
   git push
   ```

4. Post on LinkedIn (choose spicy or measured variant from downloads)

5. First comment on your LinkedIn post: link to the design conversation

---

You're ready. Feb 28 is your starting line. March 1 is launch day.

**Go build Lateos, Leo.**
