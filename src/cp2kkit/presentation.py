"""Scrolling terminal presentation; never used by machine-readable batch output."""
import os
import shutil
import textwrap


class Presenter:
    def __init__(self, stream, plain=False, width=None):
        self.stream = stream
        self.width = width or shutil.get_terminal_size((80, 24)).columns
        self.console = None
        if not plain and 'NO_COLOR' not in os.environ and stream.isatty():
            try:
                from rich.console import Console
            except ImportError:
                pass  # The standard-library core works without the optional ui extra.
            else:
                self.console = Console(file=stream, width=self.width, markup=False,
                                       highlight=False)

    def show(self, text=''):
        if self.console is not None:
            status = str(text).partition(':')[0]
            style = {'Success': 'green', 'Warning': 'yellow', 'Error': 'red'}.get(status)
            self.console.print(str(text), style=style, overflow='fold')
        else:
            # Fold, never truncate: paths and warnings remain completely visible.
            for line in str(text).split('\n'):
                print(textwrap.fill(line, width=max(1, self.width),
                                    replace_whitespace=False, drop_whitespace=False), file=self.stream)

    def heading(self, text):
        if self.console is not None:
            self.console.print(text, style='bold cyan', overflow='fold')
        else:
            self.show(text)

    def rows(self, rows):
        # Vertical key/value records remain readable even on narrow terminals.
        for key, value in rows:
            self.show(f'{key}: {value}')


def require_terminal(stdin, stdout, operation):
    if not stdin.isatty() or not stdout.isatty():
        from .errors import KitError
        raise KitError(f'{operation} requires a terminal (TTY) on stdin and stdout; '
                       'use batch subcommands such as generate-input PATH -o OUTPUT '
                       '--periodic NONE, report PATH, or cube-check PATH for scripts')
