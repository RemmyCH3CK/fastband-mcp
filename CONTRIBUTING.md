# Contributing to Fastband MCP

Thank you for your interest in contributing to Fastband MCP! This document provides guidelines for contributing.

## Getting Started

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/fastband-mcp
   cd fastband-mcp
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Run tests**
   ```bash
   pytest
   ```

## Development Workflow

### Branch Naming

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `refactor/description` - Code refactoring
- `docs/description` - Documentation updates

### Commit Messages

Follow conventional commits:
```
type(scope): description

[optional body]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(providers): add Gemini AI provider
fix(tickets): resolve race condition in claim_ticket
docs(readme): add installation instructions
```

### Pull Request Process

1. Create a feature branch from `develop`
2. Make your changes
3. Run tests and linting: `pytest && ruff check src/`
4. Update documentation if needed
5. Create a pull request to `develop`
6. Wait for review and address feedback

## Code Style

- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 100 characters
- Use Ruff for linting

## Testing

- Write tests for all new functionality
- Maintain >90% code coverage
- Use pytest for testing
- Place tests in `tests/` directory

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=fastband --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run tests matching pattern
pytest -k "test_provider"
```

## Documentation

- Update README.md for user-facing changes
- Add docstrings to all public functions/classes
- Update docs/ for significant features

## Reporting Issues

When reporting bugs, include:
- Python version
- OS
- Steps to reproduce
- Expected vs actual behavior
- Error messages/tracebacks

## Feature Requests

For feature requests, please:
- Check existing issues first
- Describe the use case
- Explain why this would benefit users

## Code of Conduct

Be respectful, inclusive, and professional. We're all here to build something great together.

## Questions?

Open an issue with the `question` label or reach out to maintainers.

---

Thank you for contributing!
