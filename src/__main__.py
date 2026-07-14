"""Allow ``python -m src`` to invoke the headless command-line interface."""

from .cli import main


raise SystemExit(main())
