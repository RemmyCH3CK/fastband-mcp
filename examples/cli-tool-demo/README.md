# CLI Tool Demo

A command-line tool example demonstrating Fastband MCP's ticket management workflow.

## Overview

This example shows:
- How to use Fastband tickets for CLI tool development
- Complete ticket workflow from creation to resolution
- Integration patterns for CLI applications

## Prerequisites

- Python 3.10+
- Fastband MCP installed (`pip install fastband-mcp`)

## Setup

1. **Install dependencies:**

   ```bash
   cd examples/cli-tool-demo
   pip install -r requirements.txt
   ```

2. **Initialize Fastband (if not already done):**

   ```bash
   fastband init
   ```

## The Demo CLI Tool

This example includes a simple file organizer CLI tool (`organizer.py`) that:
- Lists files in a directory
- Organizes files by extension
- Shows file statistics

### Running the Tool

```bash
# List files
python organizer.py list ./sample-files

# Organize files by type
python organizer.py organize ./sample-files --dry-run

# Show statistics
python organizer.py stats ./sample-files
```

## Ticket Workflow Demo

This example demonstrates the complete Fastband ticket lifecycle:

### Step 1: Create Tickets

```bash
# Create a bug ticket
fastband tickets create \
    --title "Fix crash when directory is empty" \
    --type bug \
    --priority high \
    --description "The organizer crashes with IndexError on empty directories"

# Create a feature ticket
fastband tickets create \
    --title "Add file size filter option" \
    --type feature \
    --priority medium \
    --description "Allow users to filter files by size (min/max)"

# Create an enhancement ticket
fastband tickets create \
    --title "Improve progress output" \
    --type enhancement \
    --priority low \
    --description "Add a progress bar for large directories"
```

### Step 2: List Tickets

```bash
# List all tickets
fastband tickets list

# Filter by status
fastband tickets list --status open

# Filter by priority
fastband tickets list --priority high

# Output as JSON
fastband tickets list --json
```

### Step 3: Claim a Ticket

```bash
# Claim ticket #1 as your agent
fastband tickets claim 1 --agent "Developer"

# Check the status
fastband tickets show 1
```

### Step 4: Work on the Ticket

Make your changes to the code. For this demo, you might:
- Fix the empty directory crash
- Add input validation
- Write tests

### Step 5: Complete the Ticket

```bash
fastband tickets complete 1 \
    --problem "IndexError when iterating empty directory results" \
    --solution "Added empty check before processing file list" \
    --files "organizer.py" \
    --testing "Tested with empty, single-file, and multi-file directories"
```

### Step 6: Search Tickets

```bash
# Search by keyword
fastband tickets search "empty"

# Search specific fields
fastband tickets search "crash" --fields title,description
```

### Step 7: Update Ticket

```bash
# Change priority
fastband tickets update 2 --priority high

# Add notes
fastband tickets update 2 --notes "Blocked by ticket #1"

# Change labels
fastband tickets update 2 --labels "cli,ux,blocked"
```

## Project Structure

```
cli-tool-demo/
├── .fastband/
│   └── config.yaml      # Fastband configuration
├── organizer.py         # Demo CLI tool
├── sample-files/        # Sample files for testing
│   ├── document.txt
│   ├── image.png
│   └── script.py
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Configuration

The `.fastband/config.yaml` is configured for CLI-only mode, suitable for
command-line tool development.

## Workflow Tips

1. **One Ticket, One Focus**: Each ticket should address a single issue
2. **Claim Before Working**: Always claim tickets to avoid conflicts
3. **Document Your Changes**: Use problem/solution summaries for clarity
4. **Use Labels**: Organize tickets with labels like "bug", "feature", "blocked"

## Next Steps

- Try the complete workflow with your own tickets
- Explore ticket filtering and searching
- Check out the `mcp-integration-demo` for AI integration
