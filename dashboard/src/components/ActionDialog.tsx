import { Button, Callout, Classes, Dialog, DialogBody, DialogFooter, FormGroup, HTMLSelect, InputGroup, TextArea } from "@blueprintjs/core";
import { DateInput } from "@blueprintjs/datetime";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";

import { ApiError, runAction } from "../api/client";
import type { ActionInfo, ActionResponse } from "../api/types";
import { toastDone } from "../toasts";
import { buildParams, fieldKind, label, resolve } from "../util/schema";

interface Props {
  action: ActionInfo | undefined;
  isOpen: boolean;
  onClose: () => void;
  onDone?: (response: ActionResponse) => void;
  /** Parameters the user does not type (the object the dialog is about). */
  fixed?: Record<string, unknown>;
  /** Initial text of fields. */
  initial?: Record<string, string>;
  /** Fields to leave out altogether (they get the server's default). */
  hide?: string[];
  /** Fields the UI insists on although the schema says optional (for example the note when approving a risky command). */
  require?: string[];
  title?: string;
  intro?: ReactNode;
  submitText?: string;
  summary?: string;
}

const LONG_TEXT = /(note|reason|cause)$/;

/**
 * A dialog for any action, built from the JSON Schema the API publishes for it. The server does the real checking; this
 * form only helps to fill the request in, and shows the server's answer as it is when the request is refused.
 */
export function ActionDialog({ action, isOpen, onClose, onDone, fixed = {}, initial = {}, hide = [], require = [], title, intro, submitText, summary }: Props) {
  const [values, setValues] = useState<Record<string, string>>(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string>();
  const [busy, setBusy] = useState(false);

  const properties = action?.schema.properties ?? {};
  const required = useMemo(() => [...(action?.schema.required ?? []), ...require], [action, require]);
  const names = Object.keys(properties).filter((n) => !(n in fixed) && !hide.includes(n));
  const set = (name: string, value: string) => setValues((v) => ({ ...v, [name]: value }));

  const close = () => {
    setFailure(undefined);
    setErrors({});
    onClose();
  };

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!action) return;
    const built = buildParams(properties, required, values, { ...fixed, ...Object.fromEntries(hide.map((h) => [h, undefined])) });
    setErrors(built.errors);
    if (Object.keys(built.errors).length > 0) return;
    setBusy(true);
    setFailure(undefined);
    try {
      const response = await runAction(action.slug, Object.fromEntries(Object.entries(built.params).filter(([, v]) => v !== undefined)));
      toastDone(response, summary ?? `${action.name} done`);
      setValues(initial);
      onDone?.(response);
      onClose();
    } catch (e) {
      const message = e instanceof ApiError ? `${e.outcome === "DENIED" ? "Refused" : e.outcome === "INVALID" ? "Not possible" : "Failed"}: ${e.message}${e.auditId ? ` (audit #${e.auditId})` : ""}` : (e as Error).message;
      setFailure(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog isOpen={isOpen} onClose={close} title={title ?? action?.name ?? "Action"} icon="take-action" data-testid="action-dialog">
      <form onSubmit={submit}>
        <DialogBody>
          {action && <p className={Classes.TEXT_MUTED}>{action.description}</p>}
          {intro}
          {names.map((name) => {
            const property = properties[name]!;
            const kind = fieldKind(property);
            const isRequired = required.includes(name);
            const help = errors[name] ?? resolve(property).description;
            return (
              <FormGroup key={name} label={label(name)} labelInfo={isRequired ? "(required)" : "(optional)"} labelFor={`f-${name}`}
                helperText={help} intent={errors[name] ? "danger" : "none"}>
                {kind === "enum" ? (
                  <HTMLSelect id={`f-${name}`} fill value={values[name] ?? ""} onChange={(e) => set(name, e.target.value)}>
                    <option value="">{isRequired ? "choose…" : "—"}</option>
                    {resolve(property).enum!.map((o) => <option key={o} value={o}>{o}</option>)}
                  </HTMLSelect>
                ) : kind === "datetime" ? (
                  <DateInput
                    value={values[name] ?? null}
                    onChange={(value) => set(name, value ?? "")}
                    timePrecision="minute"
                    timezone="UTC"
                    showTimezoneSelect={false}
                    dateFnsFormat="yyyy-MM-dd HH:mm"
                    placeholder="yyyy-MM-dd HH:mm (UTC)"
                    fill
                    inputProps={{ id: `f-${name}`, "data-testid": `field-${name}` } as object}
                  />
                ) : kind === "object" || LONG_TEXT.test(name) ? (
                  <TextArea id={`f-${name}`} fill rows={kind === "object" ? 3 : 2} value={values[name] ?? ""} onChange={(e) => set(name, e.target.value)} data-testid={`field-${name}`} />
                ) : (
                  <InputGroup id={`f-${name}`} value={values[name] ?? ""} onChange={(e) => set(name, e.target.value)}
                    placeholder={kind === "list" ? "ids separated by commas" : undefined} data-testid={`field-${name}`} />
                )}
              </FormGroup>
            );
          })}
          {failure && <Callout intent="danger" icon="error" data-testid="action-error">{failure}</Callout>}
        </DialogBody>
        <DialogFooter
          actions={
            <>
              <Button text="Cancel" onClick={close} />
              <Button type="submit" intent="primary" text={submitText ?? "Run"} loading={busy} data-testid="action-submit" />
            </>
          }
        />
      </form>
    </Dialog>
  );
}
