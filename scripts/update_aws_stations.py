#!/usr/bin/env python3
"""Developer CLI: verify/refresh the bundled AWS observation station catalog.

The catalog in ``custom_components/kma/aws_stations.py`` is a snapshot of the
public KMA page https://www.weather.go.kr/w/weather/land/aws-obs.do. This tool
parses that page (or a local ``--html`` file), keeps only SA/SS/SG stations, and
compares the result with the bundled catalog.

Usage (from the repository root)::

    python scripts/update_aws_stations.py --check
    python scripts/update_aws_stations.py --write [--date YYYY-MM-DD]
    python scripts/update_aws_stations.py --check --html saved-page.html

Exit codes: ``0`` in sync / written, ``1`` catalog drift (check), ``2`` error or
refused write.

Notes:
  * stdlib-only; the repository is never imported or executed (the catalog is
    read with ``ast``/``literal_eval``).
  * only the bundled catalog file is ever written.
  * ``tests/fixtures/official_sg_stations.json`` is an independent golden
    regression oracle and is never rewritten here. When the official source
    changes, review the reported station changes and update that fixture by hand;
    do not derive the tests' expected values from the modified catalog.
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "custom_components" / "kma" / "aws_stations.py"
SOURCE_URL = "https://www.weather.go.kr/w/weather/land/aws-obs.do"
INCLUDED_STN_SP = ("SA", "SS", "SG")
PER_LINE = 4

_SIDO_RE = re.compile(
    r"var\s+sidoStations\s*=\s*JSON\.parse\(\s*(\"(?:\\.|[^\"\\])*\")\s*\)",
    re.DOTALL,
)
_DATE_RE = re.compile(r"(추출일:\s*)(\d{4}-\d{2}-\d{2})")


class CatalogError(Exception):
    """The bundled catalog file is missing or has an unexpected shape."""


class SourceError(Exception):
    """The official page could not be parsed into a usable station list."""


def fetch_html(url: str = SOURCE_URL) -> str:
    """Fetch the public page (no auth, no API subscription)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "hass-kma-catalog-refresh/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")  # strict: no silent U+FFFD


def _positive_int(raw: object) -> int | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def parse_source(html: str) -> dict[int, tuple[str, str]]:
    """Parse the double-encoded ``sidoStations`` blob into ``{id: (name, region)}``.

    Keeps only ``stnSp`` in SA/SS/SG, requires a positive integer ``awsId``, an
    exact ``nameKo`` and a non-empty first ``addr`` token as the region. Exact
    duplicates are deduplicated; conflicting duplicates are rejected.
    """
    match = _SIDO_RE.search(html)
    if match is None:
        raise SourceError("sidoStations JSON.parse(...) not found in the page")
    try:
        decoded = json.loads(match.group(1))
        regions = json.loads(decoded)
    except (ValueError, TypeError) as err:
        raise SourceError(f"sidoStations is not valid double-encoded JSON: {err}") from err
    if not isinstance(regions, dict) or not regions:
        raise SourceError("sidoStations is empty or not an object")

    catalog: dict[int, tuple[str, str]] = {}
    for stations in regions.values():
        if not isinstance(stations, list):
            raise SourceError("sidoStations region entry is not a list")
        for station in stations:
            if not isinstance(station, dict) or station.get("stnSp") not in INCLUDED_STN_SP:
                continue
            station_id = _positive_int(station.get("awsId"))
            if station_id is None:
                raise SourceError(f"invalid awsId: {station.get('awsId')!r}")
            name = station.get("nameKo")
            if not isinstance(name, str) or not name.strip():
                raise SourceError(f"invalid nameKo for station {station_id}")
            addr = station.get("addr")
            if not isinstance(addr, str) or not addr.split():
                raise SourceError(f"invalid addr for station {station_id}")
            value = (name, addr.split()[0])
            existing = catalog.get(station_id)
            if existing is None:
                catalog[station_id] = value
            elif existing != value:
                raise SourceError(
                    f"conflicting duplicate id {station_id}: {existing!r} vs {value!r}"
                )
    if not catalog:
        raise SourceError("no SA/SS/SG stations found in the page")
    return catalog


def read_catalog(path: Path) -> tuple[str, dict[int, tuple[str, str]], ast.AST]:
    """Return (source, map, value_node) for the bundled catalog, without importing it."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        raise CatalogError(f"cannot parse {path}: {err}") from err
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "AWS_STATION_CATALOG"
        ):
            try:
                catalog = ast.literal_eval(node.value)
            except (ValueError, SyntaxError) as err:
                raise CatalogError(f"AWS_STATION_CATALOG is not a literal: {err}") from err
            return source, catalog, node.value
    raise CatalogError("AWS_STATION_CATALOG annotated assignment not found")


def format_changes(
    old: dict[int, tuple[str, str]], new: dict[int, tuple[str, str]]
) -> list[str]:
    """Human-reviewable summary of catalog changes."""
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(k for k in set(old) & set(new) if old[k] != new[k])
    lines: list[str] = []
    if added:
        lines.append("added %d: %s" % (len(added), ", ".join(f"{k} {new[k]}" for k in added)))
    if removed:
        lines.append("removed %d: %s" % (len(removed), ", ".join(str(k) for k in removed)))
    if changed:
        lines.append(
            "changed %d: %s"
            % (len(changed), ", ".join(f"{k} {old[k]} -> {new[k]}" for k in changed))
        )
    return lines


def _offset(source: str, lineno: int, col: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(line) for line in lines[: lineno - 1]) + col


def _validate_date(raw: str) -> str:
    try:
        return _dt.date.fromisoformat(raw).isoformat()
    except ValueError as err:
        raise ValueError(f"--date must be ISO YYYY-MM-DD, got {raw!r}") from err


def _entry_text(station: int, name: str, region: str) -> str:
    return (
        f"{station}: ({json.dumps(name, ensure_ascii=False)}, "
        f"{json.dumps(region, ensure_ascii=False)})"
    )


def _row_text(indent: str, entries: list[str]) -> str:
    return indent + ",    ".join(entries) + ","


def _assert_supported_shape(
    source: str,
    value_node: ast.AST,
    rows: dict[int, list[int]],
    old: dict[int, tuple[str, str]],
) -> None:
    """Refuse any catalog body this tool cannot reproduce byte-for-byte.

    The profile is checked in full, once, against the *current* data, before any
    row is rebuilt. Three conditions:

    1. the dict opens and closes on their own lines;
    2. every interior line belongs to an AST entry row, so a comment line, a blank
       line, or any other non-row body content is rejected;
    3. every row's text is exactly ``_row_text(indent, [_entry_text(...)])`` for its
       own entries.

    Condition 3 is what catches a trailing comment after a row's final comma and
    any unusual spacing, without inspecting characters: the row is regenerated from
    its parsed values and compared to the original bytes. Because the comparison
    uses the same ``_entry_text`` the writer emits, a body the tool itself produced
    always passes -- including station names that contain ``#`` inside a quoted
    string. Character scanning would wrongly reject those.

    Raises ``CatalogError``, reported by the CLI as exit 2 without writing.
    """
    lines = source.splitlines()
    first = value_node.lineno
    last = value_node.end_lineno
    if last - first < 2:
        raise CatalogError("catalog literal does not open and close on separate lines")
    if lines[first - 1][value_node.col_offset + 1 :].strip():
        raise CatalogError(f"line {first}: nothing may follow the catalog's opening brace")
    if lines[last - 1][: value_node.end_col_offset - 1].strip():
        raise CatalogError(f"line {last}: nothing may precede the catalog's closing brace")

    row_lines = set(rows)
    for lineno in range(first + 1, last):
        if lineno not in row_lines:
            text = lines[lineno - 1].strip()
            detail = "blank line" if not text else f"non-row line {text!r}"
            raise CatalogError(
                f"line {lineno}: {detail} in the catalog body cannot be preserved; "
                "remove it or update the station by hand"
            )

    for lineno in sorted(row_lines):
        original = lines[lineno - 1]
        indent = original[: len(original) - len(original.lstrip())]
        rebuilt = _row_text(
            indent, [_entry_text(station, *old[station]) for station in rows[lineno]]
        )
        if rebuilt != original:
            raise CatalogError(
                f"line {lineno}: row is not the plain 'station: (name, region),' "
                "layout this tool preserves (trailing comment or unusual spacing?); "
                "refusing to rewrite it"
            )


def apply_targeted(
    source: str,
    value_node: ast.AST,
    old: dict[int, tuple[str, str]],
    new: dict[int, tuple[str, str]],
) -> str:
    """Rewrite only the rows whose data changed, preserving every other byte.

    The catalog is laid out as indented rows of ``station: (name, region)`` entries
    separated by ``",    "``. Whole-literal re-rendering would re-chunk the whole
    file whenever a row is not a multiple of ``PER_LINE``, producing a huge diff for
    a one-record change. Instead:

    * a changed entry is re-rendered on its own existing row (+1/-1);
    * a removed entry is dropped from its own row, and an emptied row is dropped;
    * added entries are appended after the last row, deterministically sorted.

    Rows whose data is untouched are re-emitted verbatim. The body profile is
    verified up front by ``_assert_supported_shape``, so anything this writer could
    not reproduce is refused with ``CatalogError`` before a single byte changes,
    rather than being silently dropped.
    """
    keys = list(getattr(value_node, "keys", []))
    values = list(getattr(value_node, "values", []))

    # Group the existing entries into rows, by the line each value tuple starts on,
    # so a row's members are known before any of them changes.
    stations_on_row: dict[int, list[int]] = {}
    for index, value in enumerate(values):
        stations_on_row.setdefault(value.lineno, []).append(index)
    rows = {lineno: [ast.literal_eval(keys[i]) for i in idx] for lineno, idx in stations_on_row.items()}

    _assert_supported_shape(source, value_node, rows, old)

    lines = source.splitlines()
    out_rows: list[str] = []
    for lineno in sorted(rows):
        kept = [s for s in rows[lineno] if s in new]
        if not kept:
            continue  # whole row removed
        original = lines[lineno - 1]
        indent = original[: len(original) - len(original.lstrip())]
        out_rows.append(
            _row_text(indent, [_entry_text(s, *new[s]) for s in kept])
        )

    added = sorted(set(new) - set(old))
    for start in range(0, len(added), PER_LINE):
        chunk = added[start : start + PER_LINE]
        out_rows.append(_row_text("    ", [_entry_text(s, *new[s]) for s in chunk]))

    start_off = _offset(source, value_node.lineno, value_node.col_offset)
    end_off = _offset(source, value_node.end_lineno, value_node.end_col_offset)
    return source[:start_off] + "{\n" + "\n".join(out_rows) + "\n}" + source[end_off:]


def build_written_source(
    source: str,
    value_node: ast.AST,
    old: dict[int, tuple[str, str]],
    new: dict[int, tuple[str, str]],
    date_str: str,
) -> str:
    """Return the new file text, preserving the literal when the map is unchanged.

    Raises ``CatalogError`` when the catalog has no ``추출일`` field, so a missing
    metadata line is never silently ignored (and no write happens).
    """
    if _DATE_RE.search(source) is None:
        raise CatalogError("catalog has no 추출일 field to update")
    if new == old:
        updated = source  # keep existing literal formatting (no whole-catalog reflow)
    else:
        updated = apply_targeted(source, value_node, old, new)
    return _DATE_RE.sub(lambda m: m.group(1) + date_str, updated, count=1)


def atomic_write_catalog(
    path: Path, new_source: str, expected: dict[int, tuple[str, str]]
) -> None:
    """Validate the generated Python/map, then atomically replace the catalog.

    The temp file lives in the same directory (so ``os.replace`` is atomic), the
    existing file mode is preserved, and any failure leaves the original untouched.
    """
    try:
        tree = ast.parse(new_source)
    except SyntaxError as err:
        raise CatalogError(f"generated catalog is not valid Python: {err}") from err
    written = None
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "AWS_STATION_CATALOG"
        ):
            written = ast.literal_eval(node.value)
            break
    if written != expected:
        raise CatalogError("generated catalog does not round-trip; refusing to write")

    mode = path.stat().st_mode
    # 원본 줄바꿈(LF/CRLF)을 유지한다. 텍스트 모드 기본값은 Windows에서 LF를 CRLF로 바꾼다.
    newline = "\r\n" if b"\r\n" in path.read_bytes() else "\n"
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline=newline) as handle:
            handle.write(new_source)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def run(
    args: argparse.Namespace,
    *,
    catalog_path: Path = CATALOG_PATH,
    fetch=fetch_html,
) -> int:
    """Execute one check/write run. Returns the process exit code."""
    if args.check and args.date:
        print("error: --date is only valid with --write", file=sys.stderr)
        return 2
    if args.check and args.allow_removals:
        print("error: --allow-removals is only valid with --write", file=sys.stderr)
        return 2

    if args.html:
        try:
            raw = Path(args.html).read_bytes()
        except OSError as err:
            print(f"error: cannot read --html {args.html}: {err}", file=sys.stderr)
            return 2
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError as err:
            print(f"error: --html {args.html} is not valid UTF-8: {err}", file=sys.stderr)
            return 2
    else:
        try:
            html = fetch()
        except (OSError, UnicodeDecodeError) as err:
            print(f"error: cannot fetch {SOURCE_URL}: {err}", file=sys.stderr)
            return 2

    try:
        source, old_map, value_node = read_catalog(catalog_path)
    except CatalogError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    try:
        new_map = parse_source(html)
    except SourceError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    changes = format_changes(old_map, new_map)

    if args.check:
        if changes:
            print(f"catalog drift ({len(old_map)} -> {len(new_map)} stations):")
            for line in changes:
                print("  " + line)
            return 1
        print(f"in sync: {len(old_map)} stations")
        return 0

    removed = set(old_map) - set(new_map)
    if removed and not args.allow_removals:
        print(
            f"refusing to remove {len(removed)} station id(s); "
            "review the source, then pass --allow-removals if intended",
            file=sys.stderr,
        )
        for station in sorted(removed)[:20]:
            print(f"  {station} {old_map[station]}", file=sys.stderr)
        return 2

    if args.date:
        try:
            date_str = _validate_date(args.date)
        except ValueError as err:
            print(f"error: {err}", file=sys.stderr)
            return 2
    else:
        date_str = _dt.date.today().isoformat()

    try:
        new_source = build_written_source(source, value_node, old_map, new_map, date_str)
    except CatalogError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    if new_source == source:
        print(f"no changes to write ({len(new_map)} stations, date {date_str})")
        return 0

    try:
        atomic_write_catalog(catalog_path, new_source, new_map)
    except (CatalogError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(f"wrote {catalog_path} ({len(new_map)} stations, date {date_str})")
    for line in changes:
        print("  " + line)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify or refresh the bundled AWS observation station catalog.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="compare with the official source; exit 1 on drift (never writes)")
    mode.add_argument("--write", action="store_true",
                      help="update the bundled catalog from the official source")
    parser.add_argument("--html", metavar="FILE",
                        help="parse a saved page instead of fetching the network")
    parser.add_argument("--date", metavar="ISO",
                        help="snapshot date for --write (default: today, ISO YYYY-MM-DD)")
    parser.add_argument("--allow-removals", action="store_true",
                        help="permit removing existing station ids on --write")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
