# Playlist Helper Project Guidelines

## Commands
- Run application: `python main.py`
- Install dependencies: `pip install -e .` or `uv pip install -e .`
- Lint: `ruff check .`
- Format: `ruff format .`

## Code Style Guidelines
- **Imports**: Group in order: standard library, third-party, local modules
- **Typing**: Use type hints for all function parameters and return values
- **Error handling**: Use explicit error handling with try/except blocks
- **Naming**:
  - Functions: snake_case
  - Classes: PascalCase
  - Constants: UPPER_SNAKE_CASE
  - Variables: snake_case
- **Function length**: Keep functions under 25 lines for readability
- **Documentation**: Add docstrings to all functions and classes
- **Environment variables**: Load from .env file, never hardcode secrets

## Architecture
- Use pure functions where possible
- Separate API interaction from business logic
- Gracefully handle API errors and rate limits