These are the lessons learned

Started with Python 3.14 because it was the latest available. CDK synth immediately failed — JSII doesn't support pre-release Python versions. Switched to 3.12 after diagnosing the incompatibility. Lesson: for infrastructure tooling, latest is not always best. Check runtime support before choosing your Python version, especially when AWS Lambda has a hard ceiling.

Named our CDK constructs folder constructs/ — same name as the pip package CDK depends on. Python's import system found the local folder first, causing mysterious import failures. Renamed to cdk_constructs/. Lesson: never name a local directory the same as a dependency. Check your pip packages before naming folders.

During the the project building phase, Claude wanted to include an AWS WAF but I wanted to defer this option until later release in the project roadmap. The reason being that Lateos is built on a shoestring budget. This feature will be added later and will benefit users especially enterprise users.


Validator test failing — only 4/5 passing. The fix seemed obvious: lower the block threshold from 2 to 1. Wrong. Lowering the threshold trades security for a passing test. The right question was: why is a classic prompt injection string only scoring 1? Answer: missing pattern. Fixed the pattern library, not the threshold. Lesson: never weaken a security control to make a test pass. Fix the control.
The validator was only detecting 1 threat pattern in that string, but the block threshold is 2+ patterns. So it was letting it through as a warning instead of blocking it.
The tempting wrong fix: Lower the threshold from 2 to 1. One pattern = block. Test passes. Done.
Why that was wrong: Lowering the threshold increases false positives dramatically. Legitimate user messages that happen to contain one flagged word would start getting blocked. The system becomes too aggressive and breaks normal usage.
The actual right fix: The string should have been triggering 2 patterns because it contains 2 distinct attack vectors:

Instruction override — "ignore all previous instructions"
System prompt extraction — "reveal your system prompt"

The validator was only catching one of them. The fix was to add the missing pattern to the pattern library, not weaken the threshold.
Claude Code added both patterns. All 5 tests passed. Threshold stayed at 2+.


