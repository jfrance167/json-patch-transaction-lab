"""Checked local CLI with fixed diagnostics and exclusive report creation."""
import argparse
import io
from pathlib import Path
import sys
from .contract import LabError, Unsupported, parse, read
from .model import analyze, render


def write_checked(handle, content):
    count = handle.write(content)
    if type(count) is not int or count != len(content):
        raise OSError("short output write")
    handle.flush()


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise LabError("invalid command arguments")

    def _print_message(self, message, file=None):
        if message:
            write_checked(file if file is not None else sys.stderr, message)


def main(argv=None):
    """Exit 0 unchanged, 1 changed, 4 rejected, 2 invalid/limit/I/O, 3 unsupported."""
    parser = Parser(prog="patch-lab", description="Bounded supplied synthetic ordered JSON Patch values.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, help="exclusive fresh ASCII JSON report")
    stdout_delivery = True
    try:
        # Windows text stdout otherwise expands LF to CRLF after the byte cap.
        # Restrict configuration to the owned interpreter wrapper; test/adapted
        # sinks still receive the same checked text write and flush contract.
        if type(sys.stdout) is io.TextIOWrapper:
            sys.stdout.reconfigure(newline="\n")
        args = parser.parse_args(argv)
        stdout_delivery = False
        report, code = analyze(parse(read(args.input)))
        content = render(report)
        if args.output is not None:
            if args.output.exists() and args.output.samefile(args.input):
                raise OSError("output aliases input")
            with args.output.open("x", encoding="ascii", newline="\n") as handle:
                write_checked(handle, content)
        else:
            stdout_delivery = True
            write_checked(sys.stdout, content)
        return code
    except Unsupported as error:
        code, message = 3, str(error)
    except LabError as error:
        code, message = 2, str(error)
    except (OSError, UnicodeError, ValueError):
        code, message = 2, "I/O or output delivery failed"
        if stdout_delivery:
            # Dirty buffered sinks must not change controlled exit 2 to exit 120.
            sys.stdout = io.StringIO()
    try:
        write_checked(sys.stderr, render({"status": "unsupported" if code == 3 else "error", "reason": message}))
    except (OSError, UnicodeError, ValueError):
        sys.stderr = io.StringIO()
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
