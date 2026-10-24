"""Pure, additive validation of dwg2text JSON records (schema version 1).

Unknown fields are ignored. Validation never modifies the supplied record.
"""


def validate(rec: dict) -> list[str]:
    """Return path-prefixed problems, or an empty list for a valid record.

    Only error and unsupported records may omit extraction fields. An invalid
    status is diagnosed alongside missing extraction fields. Present extraction
    fields are checked for every status. JSON booleans are not numbers.
    """
    problems = []

    def problem(path, message):
        problems.append(f"{path}: {message}")

    def check(value, spec, path):
        if isinstance(spec, type):
            valid = isinstance(value, spec)
            if spec is int:
                valid = valid and not isinstance(value, bool)
            if not valid:
                problem(path, f"expected {spec.__name__}")
        elif spec == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                problem(path, "expected number")
        elif isinstance(spec, dict):
            if not isinstance(value, dict):
                problem(path, "expected dict")
                return
            fields(value, spec, path, required=True)
        elif spec[0] == "list":
            if not isinstance(value, list):
                problem(path, "expected list")
                return
            if len(spec) == 3 and len(value) != spec[2]:
                problem(path, f"expected list of {spec[2]} numbers")
            for index, entry in enumerate(value):
                check(entry, spec[1], f"{path}[{index}]")
        elif spec[0] == "mapping":
            if not isinstance(value, dict):
                problem(path, "expected dict")
                return
            for key, entry in value.items():
                entry_path = f"{path}[{key!r}]"
                if not isinstance(key, str):
                    problem(entry_path, "expected str key")
                check(entry, spec[1], entry_path)

    def fields(value, specs, prefix="", required=False):
        for key, spec in specs.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in value:
                check(value[key], spec, path)
            elif required:
                problem(path, "missing required key")

    if not isinstance(rec, dict):
        return ["record: expected dict"]

    strings = ("list", str)
    fields(rec, {
        "file": str,
        "schema_version": int,
        "version": str,
        "status": str,
        "errors": strings,
        "size": int,
    }, required=True)
    if "schema_version" in rec and rec["schema_version"] != 1:
        problem("schema_version", "expected 1")
    status = rec.get("status")
    if "status" in rec and status not in ("ok", "partial", "unsupported", "error"):
        problem("status", "expected one of ok, partial, unsupported, error")
    size = rec.get("size")
    if isinstance(size, int) and not isinstance(size, bool) and size < 0:
        problem("size", "expected int >= 0")

    fields(rec, {
        "codepage": int,
        "summary": dict,
        "app": list,
        "header": dict,
        "layers": strings,
        "blocks": strings,
        "layouts": ("list", {
            "name": str, "paper": str,
            "size_mm": ("list", "number", 2), "viewports": int,
        }),
        "entity_counts": ("mapping", int),
        "text": ("mapping", strings),
        "attributes": ("list", dict),
        "dimension_text": ("list", {"block": str, "text": str}),
        "items": ("list", {"kind": str, "block": str, "text": str}),
    }, required=status not in ("unsupported", "error"))

    fields(rec, {
        "proxy_text": ("list", dict),
        "table_text": list,
        "tables": ("list", {"handle": int, "block": str, "texts": strings}),
        "xrefs": ("list", {"name": str, "path": str}),
        "images": ("list", {"path": str, "count": int}),
        "underlays": ("list", {"kind": str, "path": str}),
        "seconds": "number",
    })
    return problems
