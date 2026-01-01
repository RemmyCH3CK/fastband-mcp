# THE AGENT BIBLE

**Version:** 1.0.0
**Last Updated:** {{DATE}}
**Status:** AUTHORITATIVE - THIS IS THE ONLY AGENT DOCUMENTATION

---

## Table of Contents

1. [The Hierarchy of Authority](#1-the-hierarchy-of-authority)
2. [The Core Laws](#2-the-core-laws)
3. [Project Overview](#3-project-overview)
4. [Workflow Guidelines](#4-workflow-guidelines)
5. [Code Standards](#5-code-standards)
6. [Testing Requirements](#6-testing-requirements)
7. [Security Rules](#7-security-rules)
8. [Communication Protocol](#8-communication-protocol)
9. [Error Recovery](#9-error-recovery)
10. [Quick Reference](#10-quick-reference)

---

## 1. THE HIERARCHY OF AUTHORITY

```
┌─────────────────────────────────────────────────────┐
│                USER ("The Boss")                    │
│         Final authority on all decisions            │
│       Can override any rule when necessary          │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│           AGENT_BIBLE.md ("The Law")                │
│     Single authoritative documentation source       │
│        Defines all rules and constraints            │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│              AGENTS ("The Crew")                    │
│      Follow the law, serve the user's goals         │
│            without exception                        │
└─────────────────────────────────────────────────────┘
```

**Key Principle:** When in doubt, escalate UP the hierarchy. Agents never make unilateral decisions on ambiguous matters.

---

## 2. THE CORE LAWS

These laws are absolute. Violation is unacceptable.

<!-- BEGIN_STRUCTURED_RULES -->
| Severity | Category | Rule |
|----------|----------|------|
| MUST | security | Never commit secrets, API keys, or credentials to version control |
| MUST | workflow | Always create feature branches for changes |
| MUST | workflow | Write clear, descriptive commit messages |
| MUST | code_style | Follow existing codebase conventions and patterns |
| MUST | testing | Verify changes work before marking complete |
| SHOULD | testing | Write tests for new features |
| SHOULD | documentation | Document significant changes and decisions |
| SHOULD | code_style | Keep functions focused and single-purpose |
| MUST_NOT | workflow | Never force push to main/master branch |
| MUST_NOT | security | Never disable security features or linters |
| MUST_NOT | workflow | Never merge without proper review |
<!-- END_STRUCTURED_RULES -->

---

## 3. PROJECT OVERVIEW

### Tech Stack
{{TECH_STACK}}

### Project Structure
{{PROJECT_STRUCTURE}}

### Key Directories
{{KEY_DIRECTORIES}}

---

## 4. WORKFLOW GUIDELINES

### {{OPERATION_MODE_HEADER}}

{{OPERATION_MODE_DESCRIPTION}}

### Standard Workflow

1. **Understand the Task**
   - Read requirements carefully
   - Identify affected files and systems
   - Plan approach before coding

2. **Create Feature Branch**
   - Branch from main/development
   - Use descriptive branch names: `feature/`, `fix/`, `refactor/`

3. **Implement Changes**
   - Follow code standards (see Section 5)
   - Make atomic, focused commits
   - Test as you go

4. **Verify Changes**
   - Run existing tests
   - Manually test functionality
   - Check for regressions

5. **Submit for Review**
   - Create pull request with clear description
   - Link to related issues/tickets
   - Wait for approval before merging

---

## 5. CODE STANDARDS

### General Principles

- **Readability First**: Code should be self-documenting
- **Consistency**: Match existing patterns in the codebase
- **Simplicity**: Prefer simple solutions over clever ones
- **DRY**: Don't Repeat Yourself, but don't over-abstract

### Naming Conventions

{{NAMING_CONVENTIONS}}

### File Organization

{{FILE_ORGANIZATION}}

### Formatting

{{FORMATTING_RULES}}

---

## 6. TESTING REQUIREMENTS

### Before Completing Any Task

- [ ] Code compiles/runs without errors
- [ ] Existing tests pass
- [ ] New functionality has been manually verified
- [ ] No console errors or warnings introduced
- [ ] Edge cases considered

### Test Coverage Expectations

{{TEST_REQUIREMENTS}}

---

## 7. SECURITY RULES

### Never Do

- Commit secrets, API keys, or credentials
- Store sensitive data in plain text
- Disable security features
- Ignore security warnings
- Use hardcoded passwords

### Always Do

- Use environment variables for secrets
- Validate and sanitize user input
- Follow principle of least privilege
- Keep dependencies updated
- Report security concerns immediately

---

## 8. COMMUNICATION PROTOCOL

### When to Ask

- Requirements are unclear or ambiguous
- Multiple valid approaches exist
- Proposed change might break existing functionality
- Task requires access you don't have
- Estimated effort significantly differs from expectations

### How to Report Progress

- Provide clear status updates
- Document blockers immediately
- Share completed work early for feedback
- Explain decisions and tradeoffs made

---

## 9. ERROR RECOVERY

### When Stuck

1. Re-read this Bible and relevant documentation
2. Search codebase for similar implementations
3. Try at least 2 different approaches
4. Document what you tried and why it failed
5. Escalate to human with clear problem description

### Common Patterns

{{ERROR_RECOVERY_PATTERNS}}

---

## 10. QUICK REFERENCE

### Essential Commands

{{ESSENTIAL_COMMANDS}}

### Key Files

{{KEY_FILES}}

### Important URLs

{{IMPORTANT_URLS}}

---

**END OF AGENT BIBLE**

*This document is the single source of truth for agent behavior in this project.*
