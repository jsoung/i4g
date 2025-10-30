"""Compatibility shim so existing scripts still work after renaming the CLI."""

from i4g.cli.admin import main


if __name__ == "__main__":
    main()
