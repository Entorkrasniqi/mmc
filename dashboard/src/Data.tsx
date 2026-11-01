import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import { get } from "./api/client";
import type { ActionInfo, Definitions, Me, Operator, Spacecraft } from "./api/types";
import { usePoll } from "./hooks/usePoll";

/** How often the live state (health, newest values, lists) is read again. The API answers from the database each time. */
export const LIVE_MS = 2000;

interface DataValue {
  me: Me;
  definitions: Definitions | undefined;
  actions: ActionInfo[];
  /** operator id -> display name, for "proposed by" and the like */
  operatorNames: Record<string, string>;
  spacecraftList: Spacecraft[];
  spacecraft: Spacecraft | undefined;
  selectSpacecraft: (id: string) => void;
  /** the spacecraft list has been read at least once */
  loaded: boolean;
  error: Error | undefined;
  refresh: () => void;
}

const DataContext = createContext<DataValue | undefined>(undefined);

export function DataProvider({ me, children }: { me: Me; children: ReactNode }) {
  const definitions = usePoll(() => get<Definitions>("/api/definitions"), null).data;
  const actions = usePoll(() => get<{ items: ActionInfo[] }>("/api/actions"), null, [me.operator_id]).data?.items ?? [];
  const operators = usePoll(() => get<{ items: Operator[] }>("/api/operators"), null).data?.items ?? [];
  const live = usePoll(() => get<{ items: Spacecraft[] }>("/api/spacecraft"), LIVE_MS);
  const [selected, setSelected] = useState<string>();

  const value = useMemo<DataValue>(() => {
    const list = live.data?.items ?? [];
    return {
      me,
      definitions,
      actions,
      operatorNames: Object.fromEntries(operators.map((o) => [o.operator_id, o.display_name])),
      spacecraftList: list,
      spacecraft: list.find((s) => s.spacecraft_id === selected) ?? list[0],
      selectSpacecraft: setSelected,
      loaded: live.data !== undefined,
      error: live.error,
      refresh: live.refresh,
    };
  }, [me, definitions, actions, operators, live.data, live.error, live.refresh, selected]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function useData(): DataValue {
  const value = useContext(DataContext);
  if (!value) throw new Error("useData needs a DataProvider");
  return value;
}
