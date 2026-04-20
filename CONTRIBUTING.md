# Contributing to ARGUS

Thank you for your interest in contributing to ARGUS. This document
provides guidelines for contributing to this project.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/vivekyarra/argus-agent.git
cd argus-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install all dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Code Standards

### Type Annotations
All functions must have complete type annotations:
```python
def process_data(input_data: dict[str, Any], limit: int = 10) -> list[str]:
```

### Docstrings
Use Google-style docstrings on all public classes and functions:
```python
def analyze(image: Image.Image) -> dict[str, Any]:
    """Analyze a screenshot for structured context.

    Args:
        image: PIL Image to analyze.

    Returns:
        Dictionary with analysis results.

    Raises:
        ValueError: If image dimensions exceed limits.
    """
```

### Security
- Never use `shell=True` in subprocess calls
- Validate all user input with **Pydantic V2** strict models
- Use `webbrowser.open()` for URL handling
- Sanitize commands before forwarding to AI
- Add OWASP Top 10 references in security-related docstrings
- Store secrets in Google Cloud Secret Manager (never `.env` in prod)

## Quality Checks

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=backend --cov=client --cov-report=term-missing

# Run specific test categories
pytest tests/test_security.py -v         # Security tests
pytest tests/test_vulnerabilities.py -v  # Vulnerability tests
pytest tests/test_property.py -v         # Hypothesis fuzzing
pytest tests/test_integration.py -v      # Integration tests

# Type checking (must pass with zero errors)
mypy --strict backend/ client/

# Linting
ruff check backend/ client/ tests/
```

## Pull Request Process

1. Create a feature branch from `main`
2. Add tests for any new functionality
3. Ensure all tests pass with `pytest tests/ -v`
4. Run `mypy --strict` with zero errors
5. Update documentation if needed
6. Submit a pull request with a clear description

## Code Review Checklist

- [ ] All functions have type annotations
- [ ] All public functions have docstrings
- [ ] `mypy --strict` passes with zero errors
- [ ] No `shell=True` in subprocess calls
- [ ] Input validation uses Pydantic V2 strict models
- [ ] Security functions reference OWASP Top 10
- [ ] Tests are included for new code (including Hypothesis where applicable)
- [ ] No secrets or API keys in code
- [ ] Coverage remains above 75%

## License

By contributing, you agree that your contributions will be licensed
under the MIT License.
