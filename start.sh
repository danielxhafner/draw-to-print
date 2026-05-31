#!/bin/sh
exec "$(dirname "$0")/.venv/bin/python" "$(dirname "$0")/draw_to_printer.py" "$@"
