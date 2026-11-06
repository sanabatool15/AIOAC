"use client";
import { createContext, useContext, useMemo, useState } from "react";

export type AddDataTab = "upload";

interface AddDataApi {
  /** Open the CSV upload. TODO (plan step 5): the describe step supplies the real upload dialog. */
  open: (tab?: AddDataTab) => void;
  /** Bumps after data is added, so lists can refetch. */
  version: number;
}

const AddDataContext = createContext<AddDataApi | null>(null);

export function useAddData() {
  const ctx = useContext(AddDataContext);
  if (!ctx) throw new Error("useAddData must be used inside <AddDataProvider>");
  return ctx;
}

// One place for "add data" for the whole app. The mock dialog (links, integrations) was deleted; CSV upload only returns in plan step 5.
export function AddDataProvider({ children }: { children: React.ReactNode }) {
  const [version] = useState(0);
  const api = useMemo(() => ({ open: () => {}, version }), [version]);
  return <AddDataContext.Provider value={api}>{children}</AddDataContext.Provider>;
}
