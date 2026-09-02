"""Minimal JSON Schema (2020-12 subset) validator.

Zero-dependency fallback used when the `jsonschema` package is not installed.
Supports only the keywords this project's schemas use:

  type (incl. ["x","null"]), properties, required, additionalProperties (bool|schema),
  minProperties, enum, const, items (single schema), minItems, minimum, maximum,
  exclusiveMinimum, exclusiveMaximum, minLength, maxLength, pattern,
  $ref (local "#/..."), oneOf, anyOf, allOf.

Not a general implementation. If you extend the schemas, extend this too (and the
tests in tests/test_validate.py that exercise it).
"""
from __future__ import annotations

import re
from typing import Any, List


class SchemaError(Exception):
    pass


def _typename(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def _type_ok(value: Any, t: str) -> bool:
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "string":
        return isinstance(value, str)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "null":
        return value is None
    return False


class Validator:
    def __init__(self, root_schema: dict):
        self.root = root_schema

    def validate(self, instance: Any) -> List[str]:
        errs: List[str] = []
        self._check(instance, self.root, "$", errs)
        return errs

    # --- internal -------------------------------------------------------------

    def _resolve_ref(self, ref: str) -> dict:
        if not ref.startswith("#/"):
            raise SchemaError(f"only local refs supported, got {ref!r}")
        node: Any = self.root
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            node = node[part]
        return node

    def _check(self, value: Any, schema: dict, path: str, errs: List[str]) -> None:
        if schema is True or schema == {}:
            return
        if schema is False:
            errs.append(f"{path}: schema forbids any value")
            return

        if "$ref" in schema:
            self._check(value, self._resolve_ref(schema["$ref"]), path, errs)
            # sibling keywords next to $ref are ignored in this subset
            return

        for combiner in ("allOf", "anyOf", "oneOf"):
            if combiner in schema:
                subs = schema[combiner]
                results = []
                for i, sub in enumerate(subs):
                    e: List[str] = []
                    self._check(value, sub, f"{path}", e)
                    results.append(e)
                passed = [i for i, e in enumerate(results) if not e]
                if combiner == "allOf" and len(passed) != len(subs):
                    for e in results:
                        errs.extend(e)
                elif combiner == "anyOf" and not passed:
                    errs.append(f"{path}: does not match any of {len(subs)} allowed shapes")
                elif combiner == "oneOf" and len(passed) != 1:
                    errs.append(
                        f"{path}: must match exactly one allowed shape, matched {len(passed)}"
                    )

        if "type" in schema:
            types = schema["type"]
            if isinstance(types, str):
                types = [types]
            if not any(_type_ok(value, t) for t in types):
                errs.append(
                    f"{path}: expected type {'/'.join(types)}, got {_typename(value)}"
                )
                return

        if "const" in schema and value != schema["const"]:
            errs.append(f"{path}: must equal {schema['const']!r}")

        if "enum" in schema and value not in schema["enum"]:
            errs.append(f"{path}: {value!r} not in {schema['enum']}")

        if isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                errs.append(f"{path}: string shorter than {schema['minLength']}")
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                errs.append(f"{path}: string longer than {schema['maxLength']}")
            if "pattern" in schema and not re.search(schema["pattern"], value):
                errs.append(f"{path}: {value!r} does not match /{schema['pattern']}/")

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                errs.append(f"{path}: {value} < minimum {schema['minimum']}")
            if "maximum" in schema and value > schema["maximum"]:
                errs.append(f"{path}: {value} > maximum {schema['maximum']}")
            if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
                errs.append(f"{path}: {value} <= exclusiveMinimum {schema['exclusiveMinimum']}")
            if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
                errs.append(f"{path}: {value} >= exclusiveMaximum {schema['exclusiveMaximum']}")

        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                errs.append(f"{path}: array shorter than {schema['minItems']}")
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for i, item in enumerate(value):
                    self._check(item, item_schema, f"{path}[{i}]", errs)

        if isinstance(value, dict):
            props = schema.get("properties", {})
            for req in schema.get("required", []):
                if req not in value:
                    errs.append(f"{path}: missing required property '{req}'")
            if "minProperties" in schema and len(value) < schema["minProperties"]:
                errs.append(f"{path}: fewer than {schema['minProperties']} properties")
            addl = schema.get("additionalProperties", True)
            for k, v in value.items():
                if k in props:
                    self._check(v, props[k], f"{path}.{k}", errs)
                elif addl is False:
                    errs.append(f"{path}: unknown property '{k}'")
                elif isinstance(addl, dict):
                    self._check(v, addl, f"{path}.{k}", errs)


def validate(instance: Any, schema: dict) -> List[str]:
    """Return a list of human-readable error strings (empty == valid)."""
    return Validator(schema).validate(instance)
