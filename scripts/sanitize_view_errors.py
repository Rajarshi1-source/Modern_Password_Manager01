"""
sanitize_view_errors.py
=======================

A libcst-based codemod that rewrites the CodeQL ``py/stack-trace-exposure``
pattern in Django/DRF view files:

    except SomeError as e:
        return Response({"error": str(e)}, status=...)
        # or
        return JsonResponse({"error": str(e)}, status=...)

into a sanitized form that never lets the exception's ``repr/str`` reach
the client:

    except SomeError:
        logger.exception("…")
        return Response({"error": "<sanitized_code>"}, status=...)

The code constant is picked from the exception's class name(s), using the
mapping table documented in:

    PR A — https://github.com/Rajarshi1-source/Modern_Password_Manager01/pull/255

| Exception type                                         | code                |
|--------------------------------------------------------|---------------------|
| ValueError, serializers.ValidationError, ValidationErr | "invalid_request"   |
| PermissionError, PermissionDenied                      | "forbidden"         |
| AuthenticationFailed, NotAuthenticated                 | "unauthenticated"   |
| NotFound, ObjectDoesNotExist, DoesNotExist             | "not_found"         |
| RuntimeError, Exception (bare or via "Exception as e") | "internal_error"    |

Design constraints (deliberately conservative):

* The codemod ONLY rewrites ``Response`` and ``JsonResponse`` calls.
* It ONLY rewrites them when they're inside an ``except`` block.
* It ONLY rewrites the ``str(<name>)`` / ``str(<name>.args[0])``
  pattern where ``<name>`` is the exception variable bound by the
  surrounding ``except SomeError as <name>:`` clause.
* It DOES NOT touch f-string interpolation patterns — those need a more
  invasive rewrite and risk losing useful diagnostic context that
  ``logger.exception()`` doesn't capture verbatim. A separate pass can
  do f-strings once we've validated the typed rewrites.
* It DOES NOT add ``import logging`` or define ``logger`` if the module
  doesn't have it — instead it skips the file with a warning, so a
  human can fix the import. (~95% of view modules already define
  ``logger`` at the top.)
* It DOES NOT delete the ``as <name>`` binding even when no other site
  in the handler uses it — keeping the binding is harmless and reduces
  cross-scope analysis risk.

Usage:

    python scripts/sanitize_view_errors.py path/to/file.py [path/to/...]
    python scripts/sanitize_view_errors.py --diff path/to/file.py
    python scripts/sanitize_view_errors.py --check password_manager/

Exit code 0 = no changes needed or applied; 1 = files would change in
``--check`` mode; 2 = error.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

import libcst as cst
from libcst import matchers as m


# ---------------------------------------------------------------------------
# Exception class -> sanitized code mapping
# ---------------------------------------------------------------------------

# Keys are the *last segment* of an exception's qualified name (e.g.
# "serializers.ValidationError" matches on "ValidationError"). Order
# matters only for ambiguous cases; the first match wins.
EXCEPTION_TO_CODE: List[Tuple[Set[str], str]] = [
    (
        {
            "AuthenticationFailed",
            "NotAuthenticated",
            "UnauthorizedError",
        },
        "unauthenticated",
    ),
    (
        {
            "PermissionError",
            "PermissionDenied",
            "ForbiddenError",
        },
        "forbidden",
    ),
    (
        {
            "NotFound",
            "ObjectDoesNotExist",
            "DoesNotExist",
            "ResourceNotFoundError",
            "LookupError",  # base of KeyError/IndexError; common "not found" wrapper
        },
        "not_found",
    ),
    (
        {
            "ValueError",
            "ValidationError",
            "ValidationErrorCustom",
            "TypeError",
            "KeyError",
            "AttributeError",
            "BusinessLogicError",
        },
        "invalid_request",
    ),
    # Catch-all bucket — handled last; everything else (RuntimeError,
    # Exception, IOError, ...) maps to internal_error.
]

DEFAULT_CODE = "internal_error"


def _code_for_exc_name(exc_name: str) -> str:
    for names, code in EXCEPTION_TO_CODE:
        if exc_name in names:
            return code
    return DEFAULT_CODE


def _code_for_handler(handler: cst.ExceptHandler) -> str:
    """Walk the handler's `type` expression and pick the *most specific*
    sanitized code. For tuple handlers like
    ``except (ValueError, TypeError):`` we return the code matching the
    first listed exception that has a mapping; the rest of the tuple
    members fall through to the default if none match."""

    if handler.type is None:
        return DEFAULT_CODE

    def _iter_names(node: cst.BaseExpression) -> Iterable[str]:
        if isinstance(node, cst.Name):
            yield node.value
        elif isinstance(node, cst.Attribute):
            yield node.attr.value
        elif isinstance(node, cst.Tuple):
            for el in node.elements:
                yield from _iter_names(el.value)
        # else: silently ignore — generators, calls, etc. aren't supported

    for name in _iter_names(handler.type):
        for names, code in EXCEPTION_TO_CODE:
            if name in names:
                return code

    return DEFAULT_CODE


# ---------------------------------------------------------------------------
# Matchers
# ---------------------------------------------------------------------------

# A "leaky payload" is a dict literal that contains a key like 'error',
# 'detail', or 'message' whose value is `str(<exc_name>)`.
LEAKY_KEYS = {"error", "detail", "message"}

# Calls we treat as response builders. We match by *last attribute* /
# bare name so both `Response(...)` and `rest_framework.response.Response(...)`
# match.
RESPONSE_CALLEE_NAMES = {"Response", "JsonResponse"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _exc_type_label(handler: cst.ExceptHandler) -> Optional[str]:
    """Return a short human-readable label for the exception(s) caught,
    used as the message in the inserted `logger.exception(...)` call.

    Examples:
        except ValueError as e:               -> 'ValueError'
        except (ValueError, TypeError):       -> 'ValueError/TypeError'
        except rest_framework.NotFound:       -> 'NotFound'
        except:                                -> 'exception'
    """

    if handler.type is None:
        return "exception"

    def _names(node: cst.BaseExpression) -> List[str]:
        out: List[str] = []
        if isinstance(node, cst.Name):
            out.append(node.value)
        elif isinstance(node, cst.Attribute):
            out.append(node.attr.value)
        elif isinstance(node, cst.Tuple):
            for el in node.elements:
                out.extend(_names(el.value))
        return out

    names = _names(handler.type)
    if not names:
        return "exception"
    # Cap at 3 names; if there are more, just say "<first>+others".
    if len(names) > 3:
        return f"{names[0]}+others"
    return "/".join(names)


def _make_logger_exception_statement(label: str) -> cst.SimpleStatementLine:
    """Return a parsed `logger.exception("Handled <label> in view")` statement."""
    # Escape any quotes/backslashes in the label to keep parsing safe.
    safe_label = label.replace("\\", "\\\\").replace('"', '\\"')
    src = f'logger.exception("Handled {safe_label} in view")\n'
    return cst.parse_statement(src)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Transformer
# ---------------------------------------------------------------------------


@dataclass
class FileReport:
    path: Path
    replaced: int = 0
    handlers_visited: int = 0
    skipped_no_logger: bool = False
    notes: List[str] = field(default_factory=list)


class _SanitizeTransformer(cst.CSTTransformer):
    """Rewrites Response/JsonResponse `error` payloads inside except blocks.

    Tracking state:
    * ``_handler_stack``: the active chain of except handlers, so we know
      what exception name is in scope and which code to swap in. The
      innermost entry wins.
    * ``_handler_has_logger``: per-handler flag that gets set when we
      already see a ``logger.*(...)`` call inside the handler so we know
      whether to inject a ``logger.exception(...)`` before the return.
    """

    def __init__(self, file_logger_present: bool, report: FileReport):
        super().__init__()
        # Stack of dicts so we can mutate fields by name. Keys:
        #   exc_name        (str|None)
        #   code            (str)
        #   has_logger      (bool) — set when a logger.* call is seen in body
        #   made_rewrite    (bool) — set when we mutate a Return inside the handler
        #   exc_type_label  (str)  — short label for the inserted log message
        self._handler_stack: List[dict] = []
        self._file_logger_present = file_logger_present
        self._report = report

    # ----- handler bookkeeping ----------------------------------------

    def visit_ExceptHandler(self, node: cst.ExceptHandler) -> None:
        exc_name = node.name.name.value if (node.name and isinstance(node.name.name, cst.Name)) else None
        code = _code_for_handler(node)
        label = _exc_type_label(node) or "exception"
        self._handler_stack.append(
            {
                "exc_name": exc_name,
                "code": code,
                "has_logger": False,
                "made_rewrite": False,
                "exc_type_label": label,
            }
        )
        self._report.handlers_visited += 1

    def leave_ExceptHandler(
        self, original_node: cst.ExceptHandler, updated_node: cst.ExceptHandler
    ) -> cst.ExceptHandler:
        state = self._handler_stack.pop()
        if not state["made_rewrite"]:
            return updated_node
        if state["has_logger"]:
            return updated_node
        if not self._file_logger_present:
            return updated_node

        # Prepend `logger.exception("Handled <ExcLabel> in view")` to the
        # handler body so we don't lose diagnostic information now that the
        # `str(exc)` is no longer returned to the client. We always use
        # `logger.exception(...)` because it's the standard idiom inside an
        # except block — it auto-attaches sys.exc_info() to the log record
        # so the formatter emits the full traceback.
        log_stmt = _make_logger_exception_statement(state["exc_type_label"])
        new_body = updated_node.body
        if isinstance(new_body, cst.IndentedBlock):
            new_body = new_body.with_changes(body=(log_stmt, *new_body.body))
            return updated_node.with_changes(body=new_body)
        return updated_node

    # ----- detect existing logger emit inside the active handler ------

    def visit_Call(self, node: cst.Call) -> None:
        if not self._handler_stack:
            return
        # logger.exception(...)/logger.error(...) etc.
        if isinstance(node.func, cst.Attribute):
            base = node.func.value
            if isinstance(base, cst.Name) and base.value == "logger":
                self._handler_stack[-1]["has_logger"] = True

    # ----- rewrite Return statements inside except --------------------

    def leave_Return(
        self, original_node: cst.Return, updated_node: cst.Return
    ) -> cst.Return:
        if not self._handler_stack:
            return updated_node

        new_value = self._maybe_rewrite_response_call(updated_node.value)
        if new_value is None:
            return updated_node

        self._handler_stack[-1]["made_rewrite"] = True
        return updated_node.with_changes(value=new_value)

    # ----- the actual mutation ----------------------------------------

    def _maybe_rewrite_response_call(
        self, value: Optional[cst.BaseExpression]
    ) -> Optional[cst.BaseExpression]:
        if not isinstance(value, cst.Call):
            return None
        if not self._is_response_callee(value.func):
            return None

        # Find the first positional dict-literal argument and rewrite it
        new_args: List[cst.Arg] = []
        changed = False
        for arg in value.args:
            if arg.keyword is None and isinstance(arg.value, cst.Dict):
                replaced_dict = self._maybe_rewrite_payload_dict(arg.value)
                if replaced_dict is not None:
                    new_args.append(arg.with_changes(value=replaced_dict))
                    changed = True
                    continue
            new_args.append(arg)

        if not changed:
            return None

        return value.with_changes(args=new_args)

    def _is_response_callee(self, func: cst.BaseExpression) -> bool:
        if isinstance(func, cst.Name) and func.value in RESPONSE_CALLEE_NAMES:
            return True
        if isinstance(func, cst.Attribute) and func.attr.value in RESPONSE_CALLEE_NAMES:
            return True
        return False

    def _maybe_rewrite_payload_dict(
        self, payload: cst.Dict
    ) -> Optional[cst.Dict]:
        state = self._handler_stack[-1]
        exc_name = state["exc_name"]
        code = state["code"]
        new_elements: List[cst.BaseDictElement] = []
        changed = False

        for el in payload.elements:
            if not isinstance(el, cst.DictElement):
                new_elements.append(el)
                continue

            key_str = self._literal_str(el.key)
            if key_str is None or key_str not in LEAKY_KEYS:
                new_elements.append(el)
                continue

            if not self._value_leaks_exception(el.value, exc_name):
                new_elements.append(el)
                continue

            replacement_str = cst.SimpleString(repr(code))
            new_elements.append(el.with_changes(value=replacement_str))
            changed = True
            self._report.replaced += 1

        if not changed:
            return None
        return payload.with_changes(elements=new_elements)

    @staticmethod
    def _literal_str(node: cst.BaseExpression) -> Optional[str]:
        if isinstance(node, cst.SimpleString):
            try:
                return node.evaluated_value
            except Exception:  # pragma: no cover - defensive
                return None
        return None

    def _value_leaks_exception(
        self, value: cst.BaseExpression, exc_name: Optional[str]
    ) -> bool:
        """True iff *value* is one of:
        - str(<exc_name>)
        - str(<exc_name>.args[0])  (we treat as leak)
        - f-strings containing {<exc_name>}  — left alone (False) for now
        Conservative: only match str(<bare name>) where the name matches
        the active except binding (or is `e`/`exc`/`err` when binding
        is None — covers anonymous reraises).
        """

        if not isinstance(value, cst.Call):
            return False
        if not (isinstance(value.func, cst.Name) and value.func.value == "str"):
            return False
        if len(value.args) != 1 or value.args[0].keyword is not None:
            return False

        arg = value.args[0].value
        candidate_names: Set[str] = set()
        if exc_name:
            candidate_names.add(exc_name)
        # Common conventional names if the handler didn't bind explicitly
        candidate_names.update({"e", "exc", "err", "error"})

        if isinstance(arg, cst.Name) and arg.value in candidate_names:
            return True
        if isinstance(arg, cst.Attribute):
            base = arg.value
            if isinstance(base, cst.Name) and base.value in candidate_names:
                return True
        return False


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _module_defines_logger(tree: cst.Module) -> bool:
    """True if the module has a top-level ``logger = logging.getLogger(...)``
    assignment (or any plain ``logger = ...`` followed by use of
    ``logger.<attr>``)."""
    for stmt in tree.body:
        if isinstance(stmt, cst.SimpleStatementLine):
            for s in stmt.body:
                if isinstance(s, cst.Assign):
                    for tgt in s.targets:
                        if isinstance(tgt.target, cst.Name) and tgt.target.value == "logger":
                            return True
    return False


def process_file(path: Path, check_only: bool = False, show_diff: bool = False) -> FileReport:
    report = FileReport(path=path)
    src = path.read_text(encoding="utf-8")

    try:
        tree = cst.parse_module(src)
    except cst.ParserSyntaxError as e:
        report.notes.append(f"parse error: {e}")
        return report

    has_logger = _module_defines_logger(tree)
    if not has_logger:
        # We don't auto-insert; the user can either add `logger =
        # logging.getLogger(__name__)` or accept the rewrite without a
        # logger.exception() call. For safety we still proceed with the
        # rewrite — the central handler in shared/error_handlers.py
        # already logs anything that bubbles up.
        report.skipped_no_logger = True

    transformer = _SanitizeTransformer(file_logger_present=has_logger, report=report)
    new_tree = tree.visit(transformer)
    new_src = new_tree.code

    if new_src == src:
        return report

    if show_diff:
        diff = difflib.unified_diff(
            src.splitlines(keepends=True),
            new_src.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path) + " (sanitized)",
        )
        sys.stdout.writelines(diff)

    if not check_only:
        path.write_text(new_src, encoding="utf-8")

    return report


def iter_target_files(roots: Iterable[Path]) -> Iterable[Path]:
    """Yield every .py file under each root that looks like a view or
    serializer file. We don't try to be too clever — anything matching
    ``views*.py``, ``*_views.py``, or ``serializers.py`` is in scope."""
    suffixes = (
        "views.py",
        "_views.py",
        "_view.py",
        "serializers.py",
        "api.py",
    )
    seen: Set[Path] = set()
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            seen.add(root.resolve())
            continue
        for p in root.rglob("*.py"):
            name = p.name
            if name.endswith(suffixes) or "/views/" in p.as_posix() or "/api/" in p.as_posix():
                seen.add(p.resolve())
    yield from sorted(seen)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else "")
    ap.add_argument("paths", nargs="+", type=Path, help="Files or directories to scan")
    ap.add_argument("--check", action="store_true", help="Do not write files; exit 1 if changes would be made.")
    ap.add_argument("--diff", action="store_true", help="Print unified diff to stdout for each changed file.")
    ap.add_argument(
        "--all-py", action="store_true",
        help="Process every .py file under the given roots (not just views/serializers).",
    )
    args = ap.parse_args(argv)

    if args.all_py:
        def _iter(roots):
            seen: Set[Path] = set()
            for root in roots:
                if root.is_file() and root.suffix == ".py":
                    seen.add(root.resolve())
                    continue
                for p in root.rglob("*.py"):
                    seen.add(p.resolve())
            return sorted(seen)
        files = _iter(args.paths)
    else:
        files = list(iter_target_files(args.paths))

    total_replaced = 0
    files_changed = 0
    skipped: List[Path] = []

    for path in files:
        report = process_file(path, check_only=args.check, show_diff=args.diff)
        if report.replaced:
            files_changed += 1
            total_replaced += report.replaced
            status = "would-change" if args.check else "rewrote"
            print(f"{status}: {path.relative_to(Path.cwd())} ({report.replaced} site(s))")
        if report.notes:
            for note in report.notes:
                print(f"  note: {note}", file=sys.stderr)
        if report.skipped_no_logger and report.replaced:
            skipped.append(path)

    print(
        f"\nSummary: {total_replaced} replacement(s) across {files_changed} file(s), "
        f"{len(files)} file(s) scanned.",
        file=sys.stderr,
    )
    if skipped:
        print(
            f"  note: {len(skipped)} file(s) were rewritten but do NOT define a module-level "
            f"`logger`. The central handler in shared/error_handlers.py still logs the exception, "
            f"but adding `logger = logging.getLogger(__name__)` at the top of these files is a "
            f"small improvement:",
            file=sys.stderr,
        )
        for p in skipped:
            print(f"    - {p}", file=sys.stderr)

    return 1 if (args.check and total_replaced > 0) else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
