import { Button, Callout, Classes, Dialog, DialogBody, DialogFooter, FormGroup, HTMLSelect, MenuItem, NumericInput, Tag, TextArea } from "@blueprintjs/core";
import { Select } from "@blueprintjs/select";
import { useEffect, useState, type FormEvent } from "react";

import { ApiError, post, runAction } from "../api/client";
import type { ActionResponse, CommandDefinition, TimeToSafeAnswer } from "../api/types";
import { toastDone } from "../toasts";
import { EstimateView } from "./EstimatePanel";

interface Props {
  spacecraftId: string;
  commands: CommandDefinition[];
  respondsToAlarm?: string;
  onClose: () => void;
  onDone: (response: ActionResponse) => void;
}

/** The arguments as the API takes them: enum arguments by label, numbers as numbers. Null while something is missing. */
function argumentsOf(command: CommandDefinition | undefined, typed: Record<string, string>): Record<string, string | number> | null {
  if (!command) return null;
  const result: Record<string, string | number> = {};
  for (const a of command.arguments) {
    const raw = typed[a.name] ?? "";
    if (a.enum_labels) {
      if (!a.enum_labels.some((e) => e.label === raw)) return null;
      result[a.name] = raw;
    } else {
      const n = Number(raw);
      if (raw.trim() === "" || !Number.isFinite(n)) return null;
      result[a.name] = n;
    }
  }
  return result;
}

export function ProposeCommandDialog({ spacecraftId, commands, respondsToAlarm, onClose, onDone }: Props) {
  const [command, setCommand] = useState<CommandDefinition>();
  const [typed, setTyped] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string>();
  const [preview, setPreview] = useState<TimeToSafeAnswer>();
  const [previewError, setPreviewError] = useState<string>();

  const args = argumentsOf(command, typed);

  // what the satellite would say, and what the battery would do, while the user is still filling the form in
  useEffect(() => {
    setPreview(undefined);
    setPreviewError(undefined);
    if (!command || !args) return;
    const controller = new AbortController();
    post<TimeToSafeAnswer>("/api/functions/estimate-time-to-safe", { spacecraft_id: spacecraftId, command: command.name, arguments: args },
      { signal: controller.signal }).then(setPreview).catch((e: Error) => e.name !== "AbortError" && setPreviewError(e.message));
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spacecraftId, command?.name, JSON.stringify(args)]);

  const pick = (c: CommandDefinition) => {
    setCommand(c);
    setTyped(Object.fromEntries(c.arguments.map((a) => [a.name, a.enum_labels?.[0]?.label ?? ""])));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!command || !args) return;
    setBusy(true);
    setFailure(undefined);
    try {
      const response = await runAction("propose-command", {
        spacecraft_id: spacecraftId, command: command.name, arguments: args, reason: reason.trim(),
        ...(respondsToAlarm ? { responds_to_alarm_id: respondsToAlarm } : {}),
      });
      toastDone(response, `${command.name} proposed`);
      onDone(response);
    } catch (e) {
      setFailure(e instanceof ApiError ? `${e.message}${e.auditId ? ` (audit #${e.auditId})` : ""}` : (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog isOpen onClose={onClose} title="Propose a command" icon="send-message" data-testid="propose-dialog" style={{ width: 620 }}>
      <form onSubmit={submit}>
        <DialogBody>
          <p className={Classes.TEXT_MUTED}>
            A proposal sends nothing. A person approves it, and a person releases it to the link, during a contact window.
          </p>
          {respondsToAlarm && <p><Tag icon="notifications" minimal>responds to an alarm</Tag></p>}
          <FormGroup label="Command" labelInfo="(required)">
            <Select<CommandDefinition>
              items={commands}
              filterable={false}
              popoverProps={{ minimal: true }}
              itemRenderer={(item, { handleClick, handleFocus, modifiers }) => (
                <MenuItem key={item.name} text={item.name} label={item.significance === "VITAL" ? "VITAL" : undefined}
                  active={modifiers.active} onClick={handleClick} onFocus={handleFocus} roleStructure="listoption"
                  labelClassName={item.significance === "VITAL" ? "bp6-intent-danger" : undefined} />
              )}
              onItemSelect={pick}
            >
              <Button text={command?.name ?? "choose a command"} rightIcon="double-caret-vertical" data-testid="command-select" />
            </Select>
            {command && <div className="small muted" style={{ marginTop: 6 }}>{command.description}</div>}
            {command?.significance === "VITAL" && <Callout intent="warning" icon="shield" style={{ marginTop: 8 }}>A vital command: a supervisor other than you must approve it.</Callout>}
          </FormGroup>
          {command?.arguments.map((a) => (
            <FormGroup key={a.name} label={a.name.replace(/_/g, " ")} labelInfo={a.unit ? `(${a.unit})` : undefined} helperText={a.description}>
              {a.enum_labels ? (
                <HTMLSelect value={typed[a.name] ?? ""} onChange={(e) => setTyped((t) => ({ ...t, [a.name]: e.target.value }))} data-testid={`arg-${a.name}`}>
                  {a.enum_labels.map((e) => <option key={e.label} value={e.label}>{e.label}</option>)}
                </HTMLSelect>
              ) : (
                <NumericInput value={typed[a.name] ?? ""} min={a.range_min ?? undefined} max={a.range_max ?? undefined}
                  onValueChange={(_, s) => setTyped((t) => ({ ...t, [a.name]: s }))} clampValueOnBlur={false} data-testid={`arg-${a.name}`} />
              )}
            </FormGroup>
          ))}
          <FormGroup label="Reason" labelInfo="(required)" helperText="Why this command, now. The approver reads this.">
            <TextArea fill rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="reason" />
          </FormGroup>
          {previewError && <Callout intent="warning" icon="warning-sign">{previewError}</Callout>}
          {preview && command && <EstimateView data={preview} label={command.name} />}
          {failure && <Callout intent="danger" icon="error" style={{ marginTop: 8 }} data-testid="action-error">{failure}</Callout>}
        </DialogBody>
        <DialogFooter actions={
          <>
            <Button text="Cancel" onClick={onClose} />
            <Button type="submit" intent="primary" text="Propose" loading={busy} disabled={!command || !args || reason.trim() === ""} data-testid="propose-submit" />
          </>
        } />
      </form>
    </Dialog>
  );
}
