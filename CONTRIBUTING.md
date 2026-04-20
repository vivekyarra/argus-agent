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
- Validate all user input before processing
- Use `webbrowser.open()` for URL handling
- Sanitize commands before forwarding to AI

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=backend --cov=client --cov-report=term-missing

# Run specific test categories
pytest tests/test_security.py -v       # Security tests
pytest tests/test_integration.py -v    # Integration tests
pytest tests/ -m "not integration"     # Skip integration tests
```

## Pull Request Process

1. Create a feature branch from `main`
2. Add tests for any new functionality
3. Ensure all tests pass with `pytest tests/ -v`
4. Update documentation if needed
5. Submit a pull request with a clear description

## Code Review Checklist

- [ ] All functions have type annotations
- [ ] All public functions have docstrings
- [ ] No `shell=True` in subprocess calls
- [ ] Input validation is present
- [ ] Tests are included for new code
- [ ] No secrets or API keys in code

## License

By contributing, you agree that your contributions will be licensed
under the MIT License.
