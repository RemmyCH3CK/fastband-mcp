# Security Policy

## Supported Versions

The following versions of Fastband MCP are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.2025.x (current) | Yes |
| < 1.2025.0 | No |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

1. **DO NOT** create a public GitHub issue for security vulnerabilities
2. Email security concerns to the maintainers via GitHub's private security reporting feature
3. Include the following information:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt within 48 hours
- **Initial Assessment**: Within 7 days, we will provide an initial assessment
- **Resolution Timeline**: Critical vulnerabilities will be addressed within 30 days
- **Disclosure**: We follow responsible disclosure practices

## Security Best Practices for Users

### API Key Management

1. **Never hardcode API keys** in configuration files that are committed to version control
2. Use environment variables for sensitive credentials:
   ```bash
   export ANTHROPIC_API_KEY="your-key-here"
   export OPENAI_API_KEY="your-key-here"
   export GOOGLE_API_KEY="your-key-here"
   ```
3. Add `.env` files to `.gitignore`
4. Use secrets management tools in production environments

### Configuration Security

1. The `.fastband/` directory may contain sensitive configuration - add to `.gitignore` if needed
2. Use `FASTBAND_SECRET_KEY` environment variable for web dashboard sessions:
   ```bash
   export FASTBAND_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
   ```
3. Never use the default `dev-secret-key` in production

### File System Security

1. Fastband tools operate on the file system - ensure proper file permissions
2. The tools respect system permissions but operators should:
   - Run with least-privilege principles
   - Restrict access to sensitive directories
   - Use read-only mounts where appropriate

### Network Security

1. The web dashboard binds to `127.0.0.1` by default (localhost only)
2. For production deployments:
   - Use a reverse proxy (nginx, Caddy) with TLS
   - Implement proper authentication
   - Consider network segmentation

### Database Security

1. SQLite databases are stored in `.fastband/` by default
2. For production:
   - Secure database file permissions (chmod 600)
   - Consider encrypted storage for sensitive data
   - Regular backups with secure storage

## Security Features

### Input Validation

- All user inputs through tools are validated
- File paths are validated to prevent path traversal attacks
- SQL queries use parameterized statements to prevent injection

### Path Security

Fastband implements path validation to prevent:
- Directory traversal attacks (`../` sequences)
- Symlink attacks
- Access outside allowed directories

### Secrets Handling

- API keys are never logged
- Sensitive configuration is not included in error messages
- The `to_dict()` method on configs excludes API keys from serialization

## OWASP Top 10 Considerations

### A01:2021 - Broken Access Control
- File operations validate paths before access
- Web dashboard should use authentication in production

### A02:2021 - Cryptographic Failures
- Use strong, random secret keys for Flask sessions
- API keys are handled through environment variables

### A03:2021 - Injection
- SQL queries use parameterized statements
- User inputs are validated and sanitized
- Command execution is restricted to whitelisted operations

### A04:2021 - Insecure Design
- Principle of least privilege in tool operations
- Defense in depth with multiple validation layers

### A05:2021 - Security Misconfiguration
- Secure defaults (localhost binding, debug mode off)
- Clear documentation for production setup

### A06:2021 - Vulnerable and Outdated Components
- Regular dependency updates
- Minimal dependency footprint
- Optional dependencies for providers

### A07:2021 - Identification and Authentication Failures
- Web dashboard requires proper authentication setup in production
- API key validation for AI providers

### A08:2021 - Software and Data Integrity Failures
- Input validation on all data paths
- JSON/YAML parsing with safe loaders

### A09:2021 - Security Logging and Monitoring Failures
- Comprehensive logging infrastructure
- Security events can be logged for monitoring

### A10:2021 - Server-Side Request Forgery (SSRF)
- URL validation in web tools
- Restricted network access patterns

## Dependency Security

We regularly audit dependencies for known vulnerabilities. Current dependencies:

| Package | Purpose | Security Notes |
|---------|---------|----------------|
| mcp | MCP protocol | Core protocol library |
| typer | CLI framework | Minimal attack surface |
| rich | Terminal UI | Output only |
| pyyaml | Configuration | Uses safe_load() |
| httpx | HTTP client | Modern, secure client |
| pydantic | Data validation | Strong input validation |

### Optional Dependencies

| Package | Purpose | Security Notes |
|---------|---------|----------------|
| anthropic | Claude API | Official SDK |
| openai | OpenAI API | Official SDK |
| google-generativeai | Gemini API | Official SDK |
| flask | Web dashboard | Production needs auth |
| playwright | Screenshots | Runs sandboxed browser |

## Security Updates

Security updates are released as patch versions. To update:

```bash
pip install --upgrade fastband-mcp
```

## Contact

For security concerns, use GitHub's private security reporting feature on our repository.
