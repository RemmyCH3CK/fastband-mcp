# THE AGENT BIBLE

**Version:** 2.0.0
**Last Updated:** {{GENERATION_DATE}}
**Project:** {{PROJECT_NAME}}
**Status:** AUTHORITATIVE - THIS IS THE ONLY AGENT DOCUMENTATION

---

## Table of Contents

1. [The Hierarchy of Authority](#1-the-hierarchy-of-authority)
2. [The Ten Laws](#2-the-ten-laws)
3. [Project Architecture](#3-project-architecture)
4. [Ticket Workflow (7 Steps)](#4-ticket-workflow-7-steps)
5. [Agent Ops Log Protocol](#5-agent-ops-log-protocol)
6. [Verification Requirements](#6-verification-requirements)
7. [Review Agent Protocol](#7-review-agent-protocol)
8. [MCP Tool Reference](#8-mcp-tool-reference)
9. [Security Requirements](#9-security-requirements)
10. [Error Recovery & Common Fixes](#10-error-recovery--common-fixes)
11. [Memory Architecture Protocol](#11-memory-architecture-protocol)
12. [Quick Reference Card](#12-quick-reference-card)

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
│         FASTBAND MCP TOOLS ("The Enforcer")         │
│       Programmatic enforcement of all rules         │
│     Tools BLOCK violations before they happen       │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│          AGENT_BIBLE.md ("The Law")                 │
│     Single authoritative documentation source       │
│     All other agent docs are DEPRECATED             │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│              AGENTS ("The Crew")                    │
│      Follow the law, obey the tools, serve          │
│         the user's goals without exception          │
└─────────────────────────────────────────────────────┘
```

**Key Principle:** When in doubt, escalate UP the hierarchy. Agents never make unilateral decisions on ambiguous matters.

---

## 2. THE TEN LAWS

These laws are absolute. Violation triggers automatic rejection.

### LAW 1: Ops Log Reporting is Mandatory

**THE RULE:**
All agents MUST report their actions to the Agent Operations Log. This enables safe parallel agent coordination.

**BEFORE STARTING ANY WORK:**
```python
# Check for holds/directives FIRST
directive = mcp__fastband-mcp__ops_log_latest_directive()
if directive.get("is_hold"):
    print(f"HOLD in effect - STOP: {directive['formatted']}")
    # DO NOT PROCEED until hold is lifted
```

**REQUIRED REPORTS:**
- `ops_log_write()` - General status updates
- `ops_log_rebuild()` - Before AND after container rebuilds
- `ops_log_clearance()` - Grant/hold work for other agents

**RATIONALE:**
Without ops log coordination, parallel agents will:
- Overwrite each other's changes
- Restart services while others are testing
- Deploy during active development
- Create merge conflicts

**Hub UI:** {{HUB_URL}}/control-plane

---

### LAW 2: Never Commit Secrets

**THE RULE:**
Credentials, API keys, tokens, and secrets MUST NEVER be committed to version control.

**FORBIDDEN:**
- Hardcoded API keys in source code
- Real credentials in `.env` files committed to git
- Tokens in config files
- Secrets in test fixtures
- Passwords in comments or logs

**REQUIRED:**
```python
# Use environment variables
api_key = os.environ.get("API_KEY")

# Use .env.example with placeholders
API_KEY=your-key-here

# Validate before use
if not api_key:
    raise ValueError("API_KEY not configured")
```

**ENFORCEMENT:**
- Pre-commit hooks scan for secret patterns
- Security audit tools detect exposed credentials
- MCP tools block commits containing secrets

---

### LAW 3: Use Parameterized Queries Only

**THE RULE:**
ALL database operations MUST use parameterized queries or validated identifiers.

**FORBIDDEN:**
```python
# NEVER DO THIS - SQL INJECTION VULNERABILITY
query = f"SELECT * FROM {table_name}"
cursor.execute(f"PRAGMA table_info('{user_input}')")
```

**REQUIRED:**
```python
# Use parameterized queries
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# Or use security validators for identifiers
from fastband.core.security import validate_sql_identifier
safe_name = validate_sql_identifier(table_name)
```

---

### LAW 4: Validate All Paths

**THE RULE:**
File paths from user input MUST be validated before use to prevent path traversal attacks.

**FORBIDDEN:**
```python
# NEVER DO THIS - PATH TRAVERSAL VULNERABILITY
path = Path(user_input).resolve()
with open(path) as f:
    return f.read()
```

**REQUIRED:**
```python
from fastband.core.security import PathValidator

validator = PathValidator(allowed_roots=[Path.cwd(), Path.home()])
safe_path = validator.validate(user_input)  # Raises on traversal attempt
```

**CHECKS PERFORMED:**
- `..` sequence detection (raw and URL-encoded)
- Symlink resolution and validation
- Null byte injection prevention
- Allowed roots enforcement

---

### LAW 5: Screenshots Must Be Analyzed

**THE RULE:**
Screenshots are NOT just captured - they MUST be analyzed for verification using the Vision API.

**BEFORE screenshot must show:**
- The actual problem/feature being addressed
- NOT a login page or unrelated page

**AFTER screenshot must show:**
- The same page/feature as BEFORE
- Visible evidence the fix works

**REQUIRED ANALYSIS:**
```python
# Analyze EACH screenshot
mcp__fastband-mcp__analyze_screenshot_with_vision(
    screenshot_path="screenshots/ticket_XXXX_before.png",
    expected_content="description of what should be visible",
    ticket_id="XXXX",
    analysis_type="validation"
)

# Compare BEFORE and AFTER
mcp__fastband-mcp__compare_screenshots_with_vision(
    before_screenshot_path="...",
    after_screenshot_path="...",
    ticket_id="XXXX",
    expected_change="what should be different"
)
```

**REJECTION TRIGGERS:**
- `is_login_page: true` - REJECT immediately
- `is_valid: false` - REJECT immediately
- `verdict: "FAIL"` - REJECT immediately

---

### LAW 6: Test Before Completing

**THE RULE:**
Agents MUST verify changes work before marking tickets complete. "Code looks correct" is NOT sufficient.

**FORBIDDEN:**
- Completing tickets without running tests
- Assuming changes work without verification
- Skipping browser/API testing for web changes
- Placeholder or stub implementations

**REQUIRED:**
```bash
# Run the test suite
{{TEST_COMMAND}}

# For web changes, verify in browser
{{BROWSER_TEST_COMMAND}}

# Check for runtime errors
{{LINT_COMMAND}}
```

---

### LAW 7: Never Auto-Resolve Tickets

**THE RULE:**
Only humans can set ticket status to "Resolved". Agents complete work and submit for review.

**AGENT WORKFLOW:**
1. Work on ticket
2. Run tests
3. Call `complete_ticket_safely()` → sets status to "Under Review"
4. Spawn review agents
5. **STOP** - wait for approvals
6. After approvals → status becomes "Awaiting Approval"
7. **Human** reviews and resolves

**FORBIDDEN:**
```python
# NEVER DO THIS - WILL BE BLOCKED
update_ticket(ticket_id="XXXX", status="Resolved")
```

---

### LAW 8: Never Give Up

**THE RULE:**
Agents must persist through difficulties. Giving up is not an option.

**BEFORE ESCALATING, YOU MUST:**
1. Read at least 3 relevant documentation files
2. Try at least 2 different approaches
3. Search the codebase for similar implementations
4. Document exactly what you tried and what happened
5. Explain why each approach failed with specific errors

**FORBIDDEN:**
- "This is too hard, I'll skip it"
- "I'll just do a workaround"
- Placeholder or partial implementations
- Giving up without exhaustive research

---

### LAW 9: Keep the Bible Updated

**THE RULE:**
If you discover outdated or incorrect information in this Bible, you MUST propose an update.

**PROCESS:**
1. Document the discrepancy you found
2. Note where in the Bible it appears
3. Propose the correction
4. Request human approval for the change

**Bible accuracy is everyone's responsibility.**

---

### LAW 10: Commit Changes After Work

**THE RULE:**
After completing work and before submitting for review, agents MUST commit changes to git.

**WORKFLOW:**
1. Complete coding work
2. Run tests to verify
3. Commit with descriptive message referencing ticket
4. Call `complete_ticket_safely()`
5. After human approval, ASK before pushing

**COMMIT MESSAGE FORMAT:**
```
[Ticket #XXXX] Brief description

- Detail of what changed
- Why it changed

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>
```

**FORBIDDEN:**
- Pushing without human confirmation
- Force pushing to main/master
- Committing without running tests first

---

## 3. PROJECT ARCHITECTURE

### Tech Stack

{{TECH_STACK_TABLE}}

### Directory Structure

```
{{PROJECT_STRUCTURE}}
```

### Key Files

{{KEY_FILES_TABLE}}

### Development URLs

| Purpose | URL |
|---------|-----|
| **Hub Dashboard** | {{HUB_URL}} |
| **API Endpoint** | {{API_URL}} |
| **Health Check** | {{HEALTH_URL}} |

---

## 4. TICKET WORKFLOW (8 Steps)

```
🔴 Open → 🟡 In Progress → 🔍 Under Review → 🔵 Awaiting Approval → 🟢 Resolved
                ↑                    ↓
                └── (if rejected) ───┘

         ┌─────────────────────────────────────────────────────────────┐
         │  REVIEW LOOP: Agent must wait for ALL 3 review approvals    │
         │  If ANY reviewer rejects → Fix issues → Re-spawn reviewers  │
         │  Only after ALL 3 APPROVE → Ticket moves to Awaiting Approval│
         │  THEN agent can move to next ticket                         │
         └─────────────────────────────────────────────────────────────┘
```

### Step 1: Start Session & Claim Agent Name

**Agent Naming Convention:** All agents MUST use the format `FB_Agent{N}` where N is the next available number.

```python
# FIRST: Check ops log to find available agent name
ops_entries = mcp__fastband-mcp__ops_log_read(since="24h")

# Find which FB_Agent names are in use
active_agents = set()
for entry in ops_entries.get("entries", []):
    agent = entry.get("agent", "")
    if agent.startswith("FB_Agent"):
        active_agents.add(agent)

# Pick next available number
agent_num = 1
while f"FB_Agent{agent_num}" in active_agents:
    agent_num += 1
my_agent_name = f"FB_Agent{agent_num}"

# Start your agent session with the correct name
mcp__fastband-mcp__start_agent_session(
    agent_name=my_agent_name,
    session_context="new_ticket"
)

# CRITICAL: Check for holds BEFORE doing anything
directive = mcp__fastband-mcp__ops_log_latest_directive()
if directive.get("is_hold"):
    print(f"HOLD in effect: {directive['formatted']}")
    # DO NOT PROCEED - wait for clearance
```

**Agent Name Rules:**
- Format: `FB_Agent1`, `FB_Agent2`, `FB_Agent3`, etc.
- Always check ops log first to avoid name collisions
- Use your assigned name consistently throughout the session
- Announce your name when starting: `ops_log_write(agent=my_agent_name, action="session_started")`

### Step 2: Claim Ticket

```python
# Check platform health
mcp__fastband-mcp__check_platform_health()

# Claim the ticket (use your assigned FB_Agent name)
mcp__fastband-mcp__claim_ticket(
    ticket_id="1234",
    agent_name=my_agent_name,  # e.g., "FB_Agent1"
    auto_start=True
)

# Announce to ops log
mcp__fastband-mcp__ops_log_write(
    agent=my_agent_name,
    action="claimed_ticket",
    ticket_id="1234",
    details="Starting work on feature X"
)
```

### Step 3: Take BEFORE Screenshot

```python
mcp__fastband-mcp__take_screenshot(
    url="{{DEV_URL}}/feature-page",
    output_path="screenshots/ticket_1234_before.png",
    wait_seconds=3
)
```

### Step 4: Do the Work

- Edit code files
- Follow existing code patterns
- Add error handling
- Write tests for new functionality

**If rebuild needed:**
```python
# Announce rebuild to other agents
mcp__fastband-mcp__ops_log_rebuild(
    agent=my_agent_name,  # e.g., "FB_Agent1"
    ticket_id="1234",
    container="{{SERVICE_NAME}}",
    files_changed=["file1.py", "file2.js"],
    status="requested"
)

# Wait for clearance if other agents are testing
# Then rebuild
mcp__fastband-mcp__build_container(service_name="{{SERVICE_NAME}}")

# Announce completion
mcp__fastband-mcp__ops_log_rebuild(
    agent=my_agent_name,
    ticket_id="1234",
    container="{{SERVICE_NAME}}",
    files_changed=["file1.py", "file2.js"],
    status="complete"
)
```

### Step 5: Verify & Take AFTER Screenshot

```python
# Run tests
# {{TEST_COMMAND}}

# Take AFTER screenshot
mcp__fastband-mcp__take_screenshot(
    url="{{DEV_URL}}/feature-page",
    output_path="screenshots/ticket_1234_after.png",
    wait_seconds=3
)

# Analyze both screenshots
mcp__fastband-mcp__compare_screenshots_with_vision(
    before_screenshot_path="screenshots/ticket_1234_before.png",
    after_screenshot_path="screenshots/ticket_1234_after.png",
    ticket_id="1234",
    expected_change="Description of what should be fixed"
)
```

### Step 6: Commit & Complete

```python
# Commit changes FIRST
mcp__fastband-mcp__commit_changes(
    repo="{{REPO_NAME}}",
    ticket_id="1234",
    commit_message="Fix description here",
    files_to_add=None
)

# Then complete safely
mcp__fastband-mcp__complete_ticket_safely(
    ticket_id="1234",
    before_screenshot_path="screenshots/ticket_1234_before.png",
    after_screenshot_path="screenshots/ticket_1234_after.png",
    problem_summary="What was broken",
    solution_summary="What was fixed and how",
    files_modified=["file1.py", "file2.js"],
    testing_notes="Ran tests, verified in browser"
)
```

### Step 7: Spawn Review Agents & Wait for Approval

**CRITICAL:** You MUST wait for ALL 3 review agents to approve before moving on.

```python
# Spawn ALL review agents in PARALLEL
review_results = []

# Code Review Agent
code_review = Task(
    subagent_type="general-purpose",
    description=f"Code Review for Ticket #{ticket_id}",
    prompt=f"""You are a CODE REVIEW AGENT for ticket #{ticket_id}.
    Your agent name: FB_CodeReview_{ticket_id}

    REQUIRED STEPS:
    1. start_agent_session(agent_name="FB_CodeReview_{ticket_id}", is_subagent=True)
    2. get_ticket_details("{ticket_id}")
    3. Read ALL modified files listed in the ticket
    4. Run tests: {{TEST_COMMAND}}
    5. analyze_screenshot_with_vision() on BOTH screenshots
    6. approve_code_review() or reject_code_review()

    You MUST reject if:
    - Tests fail
    - Code quality is poor
    - Screenshots don't show the fix
    - You are uncertain about anything"""
)

# Security Review Agent
security_review = Task(
    subagent_type="general-purpose",
    description=f"Security Review for Ticket #{ticket_id}",
    prompt=f"""You are a SECURITY REVIEW AGENT for ticket #{ticket_id}.
    Your agent name: FB_SecurityReview_{ticket_id}

    REQUIRED STEPS:
    1. start_agent_session(agent_name="FB_SecurityReview_{ticket_id}", is_subagent=True)
    2. get_ticket_details("{ticket_id}")
    3. Read ALL modified files
    4. Check for: hardcoded secrets, SQL injection, path traversal, XSS
    5. approve_code_review() or reject_code_review()

    You MUST reject if ANY security issue found."""
)

# Process Audit Agent
process_review = Task(
    subagent_type="general-purpose",
    description=f"Process Audit for Ticket #{ticket_id}",
    prompt=f"""You are a PROCESS AUDIT AGENT for ticket #{ticket_id}.
    Your agent name: FB_ProcessAudit_{ticket_id}

    REQUIRED STEPS:
    1. start_agent_session(agent_name="FB_ProcessAudit_{ticket_id}", is_subagent=True)
    2. get_ticket_details("{ticket_id}")
    3. Verify BEFORE screenshot exists and shows the problem
    4. Verify AFTER screenshot exists and shows the fix
    5. Verify problem_summary and solution_summary are detailed
    6. Verify files_modified matches actual changes
    7. approve_code_review() or reject_code_review()

    You MUST reject if:
    - Screenshots are missing or invalid
    - Screenshots show login/error pages
    - Summaries are vague or incomplete"""
)

# WAIT for all review results
code_result = TaskOutput(task_id=code_review.id, block=True)
security_result = TaskOutput(task_id=security_review.id, block=True)
process_result = TaskOutput(task_id=process_review.id, block=True)
```

### Step 8: Handle Review Results (REVIEW LOOP)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    REVIEW LOOP - MUST COMPLETE                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐     ALL 3 APPROVE?     ┌──────────────────────┐   │
│  │ Spawn 3     │ ─────────────────────► │ Ticket moves to      │   │
│  │ Review      │         YES            │ Awaiting Approval    │   │
│  │ Agents      │                        │                      │   │
│  └─────────────┘                        │ ★ NOW you can move   │   │
│        │                                │   to next ticket ★   │   │
│        │ ANY REJECT?                    └──────────────────────┘   │
│        ▼                                                            │
│  ┌─────────────┐                                                    │
│  │ Read reject │                                                    │
│  │ feedback    │                                                    │
│  └─────────────┘                                                    │
│        │                                                            │
│        ▼                                                            │
│  ┌─────────────┐                                                    │
│  │ Fix issues  │ ◄──────────────────────────────────────────┐      │
│  │ identified  │                                             │      │
│  └─────────────┘                                             │      │
│        │                                                     │      │
│        ▼                                                     │      │
│  ┌─────────────┐                                             │      │
│  │ Re-spawn    │ ────── LOOP until all approve ──────────────┘      │
│  │ reviewers   │                                                    │
│  └─────────────┘                                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# Check all review results
all_approved = (
    code_result.get("approved") and
    security_result.get("approved") and
    process_result.get("approved")
)

if all_approved:
    # SUCCESS! Ticket automatically moves to AWAITING_APPROVAL
    print(f"✅ All reviews passed for ticket #{ticket_id}")
    print("Ticket is now Awaiting Human Approval")

    # NOW you can move to the next ticket
    # Go back to Step 1 for the next ticket

else:
    # REJECTION - Must fix and retry
    print(f"❌ Reviews failed for ticket #{ticket_id}")

    # Collect all rejection feedback
    if not code_result.get("approved"):
        print(f"Code Review Issues: {code_result.get('issues')}")
    if not security_result.get("approved"):
        print(f"Security Issues: {security_result.get('issues')}")
    if not process_result.get("approved"):
        print(f"Process Issues: {process_result.get('issues')}")

    # FIX THE ISSUES
    # ... make code changes based on feedback ...

    # Re-run tests
    # ... run {{TEST_COMMAND}} ...

    # Take new AFTER screenshot if needed
    # ... take_screenshot() ...

    # Re-commit changes
    # ... commit_changes() ...

    # GO BACK TO STEP 7 - Re-spawn review agents
    # This loop continues until ALL 3 approve
```

**Key Rules:**
- You CANNOT move to another ticket until ALL 3 reviews pass
- Each rejection means: fix → re-commit → re-spawn reviewers
- The review loop may iterate multiple times
- Only when all 3 approve does ticket move to "Awaiting Approval"
- Human approval is separate - you don't wait for that

---

## 5. AGENT OPS LOG PROTOCOL

### Purpose

The Agent Ops Log enables safe parallel agent coordination:
- **Holds** - Stop all agents from proceeding
- **Clearances** - Allow specific agents to proceed
- **Rebuild announcements** - Coordinate container restarts
- **Status updates** - Track what each agent is doing

### Checking for Holds (MANDATORY)

```python
# ALWAYS check before starting work
directive = mcp__fastband-mcp__ops_log_latest_directive()

if directive.get("is_hold"):
    # STOP - Another agent has requested a hold
    print(f"HOLD: {directive['formatted']}")
    print(f"Reason: {directive.get('reason', 'Not specified')}")
    print(f"Issued by: {directive.get('agent', 'Unknown')}")
    # DO NOT PROCEED until hold is lifted
```

### Issuing Holds

```python
# When you need exclusive access (e.g., before deploy)
mcp__fastband-mcp__ops_log_clearance(
    agent=my_agent_name,  # e.g., "FB_Agent1"
    action="hold",
    reason="Deploying to production - all agents hold",
    affected_agents=["all"]
)
```

### Granting Clearance

```python
# When hold is no longer needed
mcp__fastband-mcp__ops_log_clearance(
    agent=my_agent_name,
    action="clearance",
    reason="Deployment complete - resume normal operations",
    affected_agents=["all"]
)
```

### Announcing Rebuilds

```python
# BEFORE rebuild - warn other agents
mcp__fastband-mcp__ops_log_rebuild(
    agent=my_agent_name,
    ticket_id="1234",
    container="webapp",
    files_changed=["app.py", "templates/base.html"],
    status="requested"
)

# AFTER rebuild - notify completion
mcp__fastband-mcp__ops_log_rebuild(
    agent=my_agent_name,
    ticket_id="1234",
    container="webapp",
    files_changed=["app.py", "templates/base.html"],
    status="complete"
)
```

### Reading the Ops Log

```python
# Get recent entries
entries = mcp__fastband-mcp__ops_log_read(
    limit=20,
    agent_filter=None,  # or specific agent name
    action_filter=None  # or "rebuild", "clearance", etc.
)

# Check what other agents are doing
active = mcp__fastband-mcp__check_active_agents()
```

### Ops Log Best Practices

| Situation | Action |
|-----------|--------|
| Starting work | `ops_log_write()` - announce what you're doing |
| Before rebuild | `ops_log_rebuild(status="requested")` |
| After rebuild | `ops_log_rebuild(status="complete")` |
| Before deploy | `ops_log_clearance(action="hold")` |
| After deploy | `ops_log_clearance(action="clearance")` |
| Blocking issue | `ops_log_write()` - document the problem |

---

## 6. VERIFICATION REQUIREMENTS

### Before Completing Any Ticket

| Check | How to Verify |
|-------|---------------|
| Tests pass | `{{TEST_COMMAND}}` |
| No lint errors | `{{LINT_COMMAND}}` |
| Feature works | Manual verification or browser test |
| Screenshots valid | Vision API analysis |

### Screenshot Validation

| Issue | Action |
|-------|--------|
| Shows login page | REJECT immediately |
| Before/after show different pages | REJECT |
| No visible change | REJECT |
| Cannot verify content | REJECT |

### Code Review Checklist

- [ ] All modified files reviewed
- [ ] Syntax is valid
- [ ] Tests pass
- [ ] No security issues
- [ ] Feature works as expected
- [ ] Screenshots are valid

---

## 7. REVIEW AGENT PROTOCOL

### Required Review Agents

| Agent | Focus Area |
|-------|------------|
| **Code Review** | Syntax, logic, tests, functionality |
| **Security Review** | Credentials, injection, path traversal |
| **Process Audit** | Workflow compliance, screenshots |

### Approval Command

```python
mcp__fastband-mcp__approve_code_review(
    ticket_id="1234",
    reviewer_agent="Code_Review_Agent",
    review_type="code",
    review_summary="All checks passed",
    checks_passed=["syntax", "tests", "security", "screenshots"],
    issues_found=[],
    suggestions=[]
)
```

### Rejection Command

```python
mcp__fastband-mcp__reject_code_review(
    ticket_id="1234",
    reviewer_agent="Code_Review_Agent",
    rejection_reason="Tests failing",
    issues_found=["test_auth.py::test_login FAILED"],
    requested_changes=["Fix the authentication test"],
    checklist_failures=["tests_pass"]
)
```

### Standard Rejection Reasons

Use these exact phrases for consistency:
1. `Screenshots not embedded in resolution`
2. `Screenshot shows login page`
3. `Before/after screenshots show different pages`
4. `Problem/solution summary missing or generic`
5. `Tests failing`
6. `Security vulnerability detected`
7. `Code not committed before completion`

---

## 8. MCP TOOL REFERENCE

### Session & Onboarding

| Tool | Purpose |
|------|---------|
| `start_agent_session()` | Begin agent session |
| `acknowledge_documentation()` | Mark docs as read |
| `complete_onboarding()` | Complete onboarding |
| `get_onboarding_status()` | Check onboarding status |

### Ticket Management

| Tool | Purpose |
|------|---------|
| `get_open_tickets()` | List open tickets |
| `get_ticket_details()` | Get full ticket info |
| `claim_ticket()` | Assign ticket to yourself |
| `resume_ticket()` | Resume work on ticket |
| `complete_ticket_safely()` | Complete with verification |

### Agent Coordination (Ops Log)

| Tool | Purpose |
|------|---------|
| `ops_log_write()` | Write general log entry |
| `ops_log_clearance()` | Grant/hold clearance |
| `ops_log_rebuild()` | Announce rebuild operations |
| `ops_log_read()` | Query recent entries |
| `ops_log_latest_directive()` | Get current hold/clearance |
| `check_active_agents()` | See what others are doing |

### Screenshots & Verification

| Tool | Purpose |
|------|---------|
| `take_screenshot()` | Capture browser screenshot |
| `analyze_screenshot_with_vision()` | AI analysis of screenshot |
| `compare_screenshots_with_vision()` | Compare before/after |
| `describe_screenshot()` | Get description of screenshot |

### Code Review

| Tool | Purpose |
|------|---------|
| `approve_code_review()` | Approve ticket |
| `reject_code_review()` | Reject with reasons |
| `get_review_status()` | Check review status |
| `get_review_feedback()` | Get reviewer feedback |

### Platform & Deployment

| Tool | Purpose |
|------|---------|
| `check_platform_health()` | Verify platform status |
| `build_container()` | Rebuild container |
| `commit_changes()` | Commit to git |

### Memory Management

| Tool | Purpose |
|------|---------|
| `memory_budget()` | Check token budget and thresholds |
| `memory_tier_status()` | View items across all 5 tiers |
| `memory_handoff_prepare()` | Create handoff packet for next agent |
| `memory_handoff_accept()` | Accept pending handoff from previous agent |
| `memory_handoff_list()` | List all pending handoffs |
| `memory_bible_load()` | Lazy-load Bible sections on demand |
| `memory_global_stats()` | View aggregate memory stats |

**Key Thresholds:**
- **60%** - Prepare handoff packet
- **80%** - MUST handoff immediately

See [Section 11: Memory Architecture Protocol](#11-memory-architecture-protocol) for detailed usage.

---

## 9. SECURITY REQUIREMENTS

### Credentials

```python
# CORRECT - Environment variable
api_key = os.environ.get("API_KEY")

# WRONG - Hardcoded (NEVER DO THIS)
api_key = "sk-..."
```

### SQL Queries

```python
# CORRECT - Parameterized
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# WRONG - String interpolation (NEVER DO THIS)
cursor.execute(f"SELECT * FROM {table_name}")
```

### Path Handling

```python
# CORRECT - Validated
from fastband.core.security import PathValidator
validator = PathValidator(allowed_roots=[Path.cwd()])
safe_path = validator.validate(user_input)

# WRONG - Direct use (NEVER DO THIS)
path = Path(user_input).resolve()
```

### Error Messages

```python
# CORRECT - Generic message
raise HTTPException(status_code=400, detail="Invalid request")

# WRONG - Leaks internals (NEVER DO THIS)
raise HTTPException(status_code=400, detail=f"Path {path} not found: {error}")
```

---

## 10. ERROR RECOVERY & COMMON FIXES

### Pattern #1: Ops Log Hold Active

**Symptom:** Cannot proceed, hold in effect

**Fix:**
1. Check who issued the hold: `ops_log_latest_directive()`
2. Wait for clearance OR contact the holding agent
3. Do NOT bypass - the hold exists for a reason

### Pattern #2: Screenshot Shows Login Page

**Symptom:** Vision API rejects screenshot

**Fix:**
1. Ensure authentication in screenshot capture
2. Use correct URL (not redirect to login)
3. Wait for page to fully load before capture

### Pattern #3: Tests Failing

**Symptom:** pytest returns failures

**Fix:**
1. Read the specific test failure message
2. Fix the code, not the test (unless test is wrong)
3. Run tests again before completing

### Pattern #4: Merge Conflict

**Symptom:** Git cannot merge changes

**Fix:**
1. Check ops log - another agent may have pushed
2. Pull latest changes
3. Resolve conflicts carefully
4. Run tests after resolution

### Pattern #5: Container Not Updating

**Symptom:** Changes not reflected after edit

**Fix:**
1. Announce rebuild via ops_log_rebuild()
2. Rebuild container
3. Clear browser cache
4. Verify changes are present

---

## 11. MEMORY ARCHITECTURE PROTOCOL

### Overview

Fastband uses a 5-tier memory architecture optimized for cost efficiency and seamless agent handoffs:

```
┌─────────────────────────────────────────────────────────────────┐
│                   5-TIER MEMORY ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────┤
│  Tier 0: HOT (20k tokens)    - Active working context            │
│  Tier 1: WARM (session)      - Current ticket + recent actions   │
│  Tier 2: COOL (semantic)     - Embeddings of past solutions      │
│  Tier 3: COLD (archive)      - Compressed ticket histories       │
│  Tier 4: FROZEN (bible)      - Lazy-loaded reference docs        │
└─────────────────────────────────────────────────────────────────┘

KEY INSIGHT: "The ticket IS the memory, not the conversation."
```

### Token Budget System

| Tier | Default Tokens | When to Expand |
|------|----------------|----------------|
| MINIMAL | 20,000 | Default for simple tasks |
| STANDARD | 40,000 | >5 files modified |
| EXPANDED | 60,000 | >3 failed attempts |
| MAXIMUM | 80,000 | Emergency ceiling |

### Handoff Thresholds

```
┌───────────────────────────────────────────────────────────────┐
│                    TOKEN BUDGET THRESHOLDS                     │
├───────────────────────────────────────────────────────────────┤
│  0%  ──────────── 60% ──────────── 80% ──────────── 100%      │
│       NORMAL       │    PREPARE     │    CRITICAL    │         │
│       OPERATION    │    HANDOFF     │    HANDOFF     │         │
└───────────────────────────────────────────────────────────────┘

At 60%: Start preparing handoff packet
At 80%: MUST handoff immediately
```

### Checking Your Budget

```python
# Check budget status periodically
budget = mcp__fastband-mcp__memory_budget(
    session_id=session_id
)

print(f"Usage: {budget['usage_percentage']}%")
print(f"Tier: {budget['tier']}")

if budget["should_handoff"]:
    print("⚠️ WARNING: Prepare handoff packet")

if budget["must_handoff"]:
    print("🚨 CRITICAL: Handoff required NOW")
```

### Preparing a Handoff

When approaching 60% budget, prepare your context for the next agent:

```python
mcp__fastband-mcp__memory_handoff_prepare(
    session_id=session_id,
    agent_name=my_agent_name,
    ticket_id=current_ticket_id,
    ticket_status="in_progress",
    ticket_summary="Fixed auth bug by updating token validation",
    completed_tasks=["Read codebase", "Identified bug", "Fixed validation"],
    pending_tasks=["Write tests", "Take after screenshot"],
    current_task="Writing unit tests",
    files_modified=["auth.py", "validators.py"],
    handoff_notes="Token validation was failing for expired tokens"
)
```

### Accepting a Handoff

When starting, check for pending handoffs:

```python
# List pending handoffs
pending = mcp__fastband-mcp__memory_handoff_list()

if pending["count"] > 0:
    # Accept the handoff
    handoff = mcp__fastband-mcp__memory_handoff_accept(
        packet_id=pending["packets"][0]["packet_id"],
        agent_name=my_agent_name
    )

    # Read the onboarding context
    print(handoff["onboarding_context"])

    # Continue where previous agent left off
    ticket_id = handoff["ticket_id"]
```

### Lazy Bible Loading

The Agent Bible is loaded progressively to save tokens:

```python
# Initial load: Summary only (~850 tokens)
bible = mcp__fastband-mcp__memory_bible_load(
    session_id=session_id,
    section_id="summary"
)

# Load specific sections when needed
review_section = mcp__fastband-mcp__memory_bible_load(
    session_id=session_id,
    section_id="LAW 7"  # Review protocol
)

# Or load sections for a specific tool
sections = mcp__fastband-mcp__memory_bible_load(
    session_id=session_id,
    for_tool="submit_review"  # Loads relevant sections
)
```

### Memory MCP Tools Reference

| Tool | Purpose |
|------|---------|
| `memory_budget()` | Check token budget status |
| `memory_tier_status()` | View items across all 5 tiers |
| `memory_handoff_prepare()` | Create handoff packet |
| `memory_handoff_accept()` | Accept pending handoff |
| `memory_handoff_list()` | List pending handoffs |
| `memory_bible_load()` | Lazy-load Bible sections |
| `memory_global_stats()` | View aggregate stats |

### Best Practices

1. **Monitor Budget Regularly**
   - Check `memory_budget()` after major operations
   - Don't wait until 80% to prepare handoff

2. **Keep Hot Memory Clean**
   - Only essential context in working memory
   - Code context loads on-demand from files

3. **Document Handoffs Thoroughly**
   - Clear ticket summary
   - List completed AND pending tasks
   - Include any blockers or warnings

4. **Use Lazy Loading**
   - Start with Bible summary
   - Load full sections only when needed
   - Tool-triggered loading is automatic

---

## 12. QUICK REFERENCE CARD

### The 10 Laws (Summary)

1. **Ops Log Mandatory** - Report all actions, check for holds
2. **Never Commit Secrets** - Use environment variables
3. **Parameterized Queries** - No SQL injection
4. **Validate All Paths** - No path traversal
5. **Analyze Screenshots** - Vision API verification
6. **Test Before Completing** - No assumptions
7. **Never Auto-Resolve** - Human approval only
8. **Never Give Up** - Persist through problems
9. **Update the Bible** - Keep docs accurate
10. **Commit After Work** - Git commits required

### Essential Commands

```python
# Check ops log for available agent name
ops_entries = ops_log_read(since="24h")
# Pick next available: FB_Agent1, FB_Agent2, etc.

# Start session with your FB_Agent name
start_agent_session(agent_name="FB_Agent1")

# Check for holds BEFORE any work
ops_log_latest_directive()

# Claim ticket
claim_ticket(ticket_id="1234", agent_name="FB_Agent1")

# Complete safely
complete_ticket_safely(ticket_id="1234", ...)

# WAIT for all 3 review approvals before next ticket
```

### Status Flow

```
🔴 Open → 🟡 In Progress → 🔍 Under Review → 🔵 Awaiting Approval → 🟢 Resolved
```

### When Stuck

1. Check the Ops Log for relevant notes
2. Re-read this Bible
3. Search codebase for similar implementations
4. Try at least 2 different approaches
5. Document what you tried
6. Then escalate to human

---

**END OF AGENT BIBLE**

*This document supersedes all previous agent documentation. Other agent docs are DEPRECATED.*
