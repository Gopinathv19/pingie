import { nonNull, refName, resolve, type Schema, typeLabel } from "@/lib/openapi";

function constraints(s: Schema): string[] {
  const out: string[] = [];
  if (s.minLength !== undefined) out.push(`min length ${s.minLength}`);
  if (s.maxLength !== undefined) out.push(`max length ${s.maxLength}`);
  if (s.minimum !== undefined) out.push(`≥ ${s.minimum}`);
  if (s.maximum !== undefined) out.push(`≤ ${s.maximum}`);
  if (s.pattern) out.push(`pattern ${s.pattern}`);
  if (s.default !== undefined && s.default !== null) out.push(`default ${JSON.stringify(s.default)}`);
  return out;
}

/** The object behind a field (through $ref, arrays and nullable unions), if any. */
function nested(s: Schema): { name: string; schema: Schema } | null {
  const { schema } = nonNull(s);
  const target = schema.type === "array" ? schema.items : schema;
  const name = refName(target);
  const resolved = resolve(target);
  if (name && resolved?.properties) return { name, schema: resolved };
  return null;
}

/** A field table for an object schema; nested objects expand inline. */
export function SchemaView({ schema, depth = 0 }: { schema: Schema; depth?: number }) {
  const s = resolve(schema);
  if (!s) return null;
  if (s.type === "array" && s.items) {
    return (
      <div>
        <p className="schema-note">
          Array of <code>{typeLabel(s.items)}</code>
        </p>
        {depth < 3 && <SchemaView schema={s.items} depth={depth + 1} />}
      </div>
    );
  }
  if (!s.properties) {
    return (
      <p className="schema-note">
        <code>{typeLabel(schema)}</code>
        {s.description ? ` · ${s.description}` : ""}
      </p>
    );
  }
  const required = new Set(s.required ?? []);
  return (
    <div className="table-wrap">
      <table className="fields">
        <thead>
          <tr>
            <th>Field</th>
            <th>Type</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(s.properties).map(([name, prop]) => {
            const { schema: p } = nonNull(prop);
            const child = depth < 3 ? nested(prop) : null;
            const notes = [p.description, ...constraints(p)].filter(Boolean).join(" · ");
            return (
              <tr key={name}>
                <td>
                  <code className="field-name">{name}</code>
                  {required.has(name) && <span className="req">required</span>}
                </td>
                <td>
                  <code className="field-type">{typeLabel(prop)}</code>
                </td>
                <td>
                  {notes}
                  {child && (
                    <details className="nested">
                      <summary>{child.name} fields</summary>
                      <SchemaView schema={child.schema} depth={depth + 1} />
                    </details>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
