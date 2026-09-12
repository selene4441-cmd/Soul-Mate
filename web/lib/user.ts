"use client";

import { useEffect, useState } from "react";

export function useUserId(): [number, (next: number) => void] {
  const [userId, setUserIdState] = useState<number>(1);

  useEffect(() => {
    const raw = window.localStorage.getItem("soulmate:user_id");
    const parsed = Number(raw || "1");
    if (Number.isFinite(parsed) && parsed >= 1) setUserIdState(parsed);
  }, []);

  function setUserId(next: number) {
    const normalized = Number.isFinite(next) && next >= 1 ? Math.floor(next) : 1;
    setUserIdState(normalized);
    window.localStorage.setItem("soulmate:user_id", String(normalized));
  }

  return [userId, setUserId];
}

