"""Repository entry point; implementation lives in the backend package."""

from src.services.character_audit import audit, main


if __name__ == "__main__":
    main()
