import { AUTH_TEXT, authFor, nonNull, opAnchor, type Operation, type TagInfo, typeLabel } from "@/lib/openapi";
import { SchemaView } from "./SchemaView";

function curl(op: Operation, auth: string): string {
  const path = op.path.replace(/\{(\w+)\}/g, (_, n) => `<${n}>`);
  const lines = [`curl -X ${op.method.toUpperCase()} "https://api.pingie.app${path}"`];
  if (auth === "session") lines.push(`  -H "Authorization: Bearer $PINGIE_SESSION"`);
  if (auth === "admin") lines.push(`  -H "Authorization: Bearer $PINGIE_ADMIN_TOKEN"`);
  if (auth === "widget" || auth === "widget-start") lines.push(`  -H "Origin: https://help.example.com"`);
  if (auth === "widget") lines.push(`  -H "X-Conversation-Token: $CONVERSATION_TOKEN"`);
  if (op.body?.contentType === "application/json") lines.push(`  -H "Content-Type: application/json"`, `  -d '{ … }'`);
  if (op.body?.contentType === "multipart/form-data") lines.push(`  -F "file=@handbook.pdf"`);
  return lines.join(" \\\n");
}

export function OperationCard({ op, tag }: { op: Operation; tag: TagInfo }) {
  const auth = authFor(op, tag);
  const params = op.parameters.filter((p) => !(p.in === "header" && ["origin", "authorization"].includes(p.name.toLowerCase())));
  const id = opAnchor(op);

  return (
    <section className="op" id={id}>
      <h3 className="op-title">
        <a className="anchor" href={`#${id}`} aria-hidden="true">
          #
        </a>
        {op.summary}
      </h3>
      <div className="op-line">
        <span className={`method method-${op.method}`}>{op.method.toUpperCase()}</span>
        <code className="op-path">{op.path}</code>
      </div>
      {op.description && (
        <div className="op-desc">
          {op.description.split("\n\n").map((para, i) => (
            <p key={i}>{para.replace(/\n/g, " ")}</p>
          ))}
        </div>
      )}
      <p className="op-auth">
        <span className={`auth auth-${auth}`}>{auth === "none" ? "public" : auth.replace("-start", "")}</span>
        {AUTH_TEXT[auth]}
      </p>

      {params.length > 0 && (
        <>
          <h4>Parameters</h4>
          <div className="table-wrap">
            <table className="fields">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>In</th>
                  <th>Type</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {params.map((p) => {
                  const s = p.schema ? nonNull(p.schema).schema : undefined;
                  const notes = [p.description, s?.default !== undefined && s?.default !== null ? `default ${JSON.stringify(s.default)}` : ""]
                    .filter(Boolean)
                    .join(" · ");
                  return (
                    <tr key={`${p.in}-${p.name}`}>
                      <td>
                        <code className="field-name">{p.name}</code>
                        {p.required && <span className="req">required</span>}
                      </td>
                      <td>{p.in}</td>
                      <td>
                        <code className="field-type">{typeLabel(p.schema)}</code>
                      </td>
                      <td>{notes}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {op.body && (
        <>
          <h4>
            Request body <span className="muted">· {op.body.contentType}</span>
          </h4>
          <SchemaView schema={op.body.schema} />
        </>
      )}

      <h4>Responses</h4>
      {op.responses.map((r) => (
        <div key={r.status} className="response">
          <div className="response-head">
            <span className={`status status-${r.status[0]}`}>{r.status}</span>
            <span>{r.description}</span>
            {r.contentType && r.contentType !== "application/json" && <span className="muted">· {r.contentType}</span>}
          </div>
          {r.schema && Object.keys(r.schema).length > 0 ? (
            <SchemaView schema={r.schema} />
          ) : (
            r.status.startsWith("2") && r.status !== "204" && <p className="schema-note">JSON object; see the guide for the fields.</p>
          )}
        </div>
      ))}

      <details className="example">
        <summary>Example request</summary>
        <div className="code">
          <span className="code-lang">bash</span>
          <pre>
            <code>{curl(op, auth)}</code>
          </pre>
        </div>
      </details>
    </section>
  );
}
