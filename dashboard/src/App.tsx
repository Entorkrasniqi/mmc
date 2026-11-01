import { Button, Callout, Classes, HTMLSelect, Navbar, NavbarDivider, NavbarGroup, NavbarHeading, NonIdealState, Spinner, Switch, Tab, Tabs, Tag } from "@blueprintjs/core";
import { Satellite } from "@blueprintjs/icons";
import { useEffect, useState } from "react";

import { HealthTag } from "./components/Tags";
import { DataProvider, useData } from "./Data";
import { Alarms } from "./pages/Alarms";
import { Anomalies } from "./pages/Anomalies";
import { Commands } from "./pages/Commands";
import { GroundTrack } from "./pages/GroundTrack";
import { Overview } from "./pages/Overview";
import { SignIn } from "./SignIn";
import { useSession } from "./Session";

const PAGES = [
  { id: "overview", title: "Overview" },
  { id: "alarms", title: "Alarms" },
  { id: "commands", title: "Commands" },
  { id: "anomalies", title: "Anomalies" },
  { id: "track", title: "Ground track" },
] as const;
type PageId = (typeof PAGES)[number]["id"];

/** The page lives in the URL hash (#/commands?respond=...), so a reload or a link lands where you were. */
export function parseHash(hash: string): { page: PageId; params: URLSearchParams } {
  const [path = "", query = ""] = hash.replace(/^#\/?/, "").split("?");
  const page = (PAGES.find((p) => p.id === path)?.id ?? "overview") as PageId;
  return { page, params: new URLSearchParams(query) };
}

function useHash() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return parseHash(hash);
}

function useDarkMode() {
  const [dark, setDark] = useState(() => {
    try { return window.localStorage.getItem("minisat.dark") !== "0"; } catch { return true; }
  });
  useEffect(() => {
    document.body.classList.toggle(Classes.DARK, dark);
    try { window.localStorage.setItem("minisat.dark", dark ? "1" : "0"); } catch { /* a convenience only */ }
  }, [dark]);
  return [dark, setDark] as const;
}

function Shell({ dark, setDark }: { dark: boolean; setDark: (dark: boolean) => void }) {
  const { me, spacecraft, spacecraftList, selectSpacecraft, loaded, error } = useData();
  const { signOut } = useSession();
  const { page, params } = useHash();

  const go = (id: string) => { window.location.hash = `#/${id}`; };

  return (
    <div className="shell">
      <Navbar className="shell-nav">
        <NavbarGroup>
          <NavbarHeading><Satellite size={20} style={{ verticalAlign: "text-bottom" }} /> MiniSat</NavbarHeading>
          <NavbarDivider />
          <Tabs id="pages" selectedTabId={page} onChange={(id) => go(String(id))} animate={false}>
            {PAGES.map((p) => <Tab key={p.id} id={p.id} title={p.title} data-testid={`tab-${p.id}`} />)}
          </Tabs>
        </NavbarGroup>
        <NavbarGroup align="right">
          {spacecraftList.length > 1 && (
            <HTMLSelect minimal value={spacecraft?.spacecraft_id} onChange={(e) => selectSpacecraft(e.target.value)}>
              {spacecraftList.map((s) => <option key={s.spacecraft_id} value={s.spacecraft_id}>{s.name}</option>)}
            </HTMLSelect>
          )}
          {spacecraft && <HealthTag health={spacecraft.health_status} />}
          <NavbarDivider />
          <Tag minimal large icon="user" data-testid="who">{me.display_name} &middot; {me.role.toLowerCase()}</Tag>
          <Switch label="dark" checked={dark} onChange={() => setDark(!dark)} style={{ margin: "0 12px 0 14px" }} />
          <Button minimal icon="log-out" text="Sign out" onClick={signOut} data-testid="sign-out" />
        </NavbarGroup>
      </Navbar>

      {!spacecraft && error && <div className="page"><Callout intent="danger" icon="error" title="Cannot read the spacecraft">{error.message}</Callout></div>}
      {!spacecraft && !error && !loaded && <div className="page"><Spinner /></div>}
      {!spacecraft && !error && loaded && <NonIdealState icon="satellite" title="No spacecraft" description="Create one with 'minisat db-seed'." />}
      {spacecraft && page === "overview" && <Overview spacecraft={spacecraft} />}
      {spacecraft && page === "alarms" && <Alarms spacecraft={spacecraft} />}
      {spacecraft && page === "commands" && (
        <Commands spacecraft={spacecraft} respondTo={params.get("respond") ?? undefined} onResponded={() => { if (params.has("respond")) go("commands"); }} />
      )}
      {spacecraft && page === "anomalies" && <Anomalies spacecraft={spacecraft} />}
      {spacecraft && page === "track" && <GroundTrack spacecraft={spacecraft} />}
    </div>
  );
}

export function App() {
  const { status, me } = useSession();
  const [dark, setDark] = useDarkMode();
  if (status === "loading") return <div className="signin"><Spinner /></div>;
  if (status === "signed-out" || !me) return <SignIn />;
  return <DataProvider me={me}><Shell dark={dark} setDark={setDark} /></DataProvider>;
}
