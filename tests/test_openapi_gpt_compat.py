"""The ChatGPT actions importer rejects any response schema that is a bare
`object` with no `properties`. Walk the generated OpenAPI spec the way the
importer does and fail on any offender, so a future `-> Dict[str, Any]`
route can't silently break the custom GPT import again."""

from scriptoria.api import app


def _resolve(schema, spec):
    while "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = spec["components"]["schemas"][name]
    return schema


def _offenders(schema, spec, context, seen=None):
    seen = seen if seen is not None else set()
    ref = schema.get("$ref")
    if ref in seen:
        return
    if ref:
        seen.add(ref)
    schema = _resolve(schema, spec)
    if schema.get("type") == "object" and not schema.get("properties"):
        yield context
    for sub in schema.get("anyOf", []) + schema.get("allOf", []) + schema.get("oneOf", []):
        yield from _offenders(sub, spec, context, seen)
    if "items" in schema:
        yield from _offenders(schema["items"], spec, context + ("items",), seen)
    for name, prop in schema.get("properties", {}).items():
        yield from _offenders(prop, spec, context + (name,), seen)


def test_every_response_object_schema_declares_properties():
    spec = app.openapi()
    bad = []
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            for status, response in op.get("responses", {}).items():
                schema = response.get("content", {}).get("application/json", {}).get("schema")
                if schema:
                    bad.extend(_offenders(schema, spec, (path, method, status)))
    assert not bad, f"bare object schemas (GPT importer rejects these): {bad}"
