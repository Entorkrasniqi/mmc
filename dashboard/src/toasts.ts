import { OverlayToaster, Position, type IconName, type Intent, type ToastProps, type Toaster } from "@blueprintjs/core";

import { ApiError } from "./api/client";
import type { ActionResponse } from "./api/types";

let toaster: Promise<Toaster> | undefined;

function show(props: ToastProps): void {
  toaster ??= OverlayToaster.create({ position: Position.TOP_RIGHT, maxToasts: 4 });
  void toaster.then((t) => t.show(props));
}

export function toast(message: string, intent: Intent = "none", icon?: IconName, timeout = 6000): void {
  show({ message, intent, icon, timeout });
}

/** A refused or failed request, with what the server said and where to find the record of it. */
export function toastError(error: unknown, what?: string): void {
  if (error instanceof ApiError) {
    const where = error.auditId ? ` (audit #${error.auditId})` : error.correlationId ? ` (id ${error.correlationId.slice(0, 8)})` : "";
    const lead = error.outcome === "DENIED" ? "Refused" : error.outcome === "INVALID" ? "Not possible" : what ?? "Failed";
    show({ message: `${lead}: ${error.message}${where}`, intent: error.outcome === "DENIED" || error.outcome === "INVALID" ? "warning" : "danger", timeout: 10000 });
  } else {
    show({ message: `${what ?? "Failed"}: ${(error as Error).message}`, intent: "danger", timeout: 10000 });
  }
}

/** An action that worked: what it did, and the warnings the rules attached (they matter more than the success). */
export function toastDone(response: ActionResponse, summary: string): void {
  show({ message: `${summary} (audit #${response.audit_id}${response.replayed ? ", repeated request" : ""})`, intent: "success", icon: "tick", timeout: 5000 });
  for (const warning of response.warnings) show({ message: warning, intent: "warning", icon: "warning-sign", timeout: 12000 });
}
