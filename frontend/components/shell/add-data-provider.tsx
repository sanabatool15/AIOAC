"use client";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { AddDataModal, type AddDataTab } from "./add-data-modal";

interface AddDataApi {
  open: (tab?: AddDataTab) => void;
  /** Bumps after data is added, so lists (sidebar) can refetch. */
  version: number;
}

const AddDataContext = createContext<AddDataApi | null>(null);

export function useAddData() {
  const ctx = useContext(AddDataContext);
  if (!ctx) throw new Error("useAddData must be used inside <AddDataProvider>");
  return ctx;
}

// One modal for the whole app: composer attach and sidebar data sources both open it.
export function AddDataProvider({ children }: { children: React.ReactNode }) {
  const [tab, setTab] = useState<AddDataTab | null>(null);
  const [version, setVersion] = useState(0);
  const open = useCallback((t: AddDataTab = "upload") => setTab(t), []);
  const api = useMemo(() => ({ open, version }), [open, version]);

  return (
    <AddDataContext.Provider value={api}>
      {children}
      {tab && (
        <AddDataModal
          initialTab={tab}
          onClose={() => setTab(null)}
          onAdded={() => setVersion((v) => v + 1)}
        />
      )}
    </AddDataContext.Provider>
  );
}
