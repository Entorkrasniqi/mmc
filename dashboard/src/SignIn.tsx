import { Button, Callout, Card, Code, FormGroup, H3, InputGroup } from "@blueprintjs/core";
import { Satellite } from "@blueprintjs/icons";
import { useState, type FormEvent } from "react";

import { ApiError } from "./api/client";
import { useSession } from "./Session";

/** DEV ONLY sign-in: the API accepts one static token per operator (protocols/security-and-threat-model.md). */
export function SignIn() {
  const { signIn } = useSession();
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      await signIn(token);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 401 ? "That token is not accepted." : (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="signin">
      <Card elevation={2} className="signin-card">
        <H3>
          <Satellite size={24} /> MiniSat Mission Control
        </H3>
        <Callout intent="warning" title="Development sign-in" icon="warning-sign">
          The API accepts one static token per operator. This is not a real login: tokens do not expire. Make some with{" "}
          <Code>minisat dev-tokens</Code>, put the line in <Code>.env</Code>, start <Code>minisat api</Code>, and paste one here.
        </Callout>
        <form onSubmit={submit}>
          <FormGroup label="Operator token" labelFor="token" helperText={error} intent={error ? "danger" : "none"}>
            <InputGroup
              id="token"
              type="password"
              autoComplete="off"
              placeholder="paste a token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              intent={error ? "danger" : "none"}
              autoFocus
            />
          </FormGroup>
          <Button type="submit" intent="primary" icon="log-in" text="Sign in" loading={busy} disabled={token.trim() === ""} />
        </form>
      </Card>
    </div>
  );
}
