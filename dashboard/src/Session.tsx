import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { clearToken, get, getToken, request, setToken, setUnauthorizedHandler } from "./api/client";
import type { Me } from "./api/types";

interface SessionValue {
  status: "loading" | "signed-out" | "signed-in";
  me: Me | undefined;
  /** Check the token with the API and, if it is good, keep it for this tab. Throws the API's error otherwise. */
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
}

const SessionContext = createContext<SessionValue | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionValue["status"]>("loading");
  const [me, setMe] = useState<Me>();

  const signOut = useCallback(() => {
    clearToken();
    setMe(undefined);
    setStatus("signed-out");
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(signOut);
    if (!getToken()) {                                  // nothing to check: go straight to the sign-in screen
      setStatus("signed-out");
      return;
    }
    let cancelled = false;
    get<Me>("/api/me")
      .then((who) => {
        if (cancelled) return;
        setMe(who);
        setStatus("signed-in");
      })
      .catch(() => !cancelled && setStatus("signed-out"));
    return () => {
      cancelled = true;
    };
  }, [signOut]);

  const signIn = useCallback(async (token: string) => {
    const who = await request<Me>("/api/me", { token: token.trim() });
    setToken(token.trim());
    setMe(who);
    setStatus("signed-in");
  }, []);

  const value = useMemo(() => ({ status, me, signIn, signOut }), [status, me, signIn, signOut]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession needs a SessionProvider");
  return value;
}
