"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { apiFetch } from "@/lib/api";

export type SessionUser = {
  id: string;
  display_name: string;
  email: string;
  birth_year: number;
  region: string;
  role: string;
  status: string;
};

export function useMe(requireAuth = true) {
  const router = useRouter();
  const query = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<SessionUser>("/auth/me"),
    retry: false,
  });
  useEffect(() => {
    if (requireAuth && query.error && (query.error as { status?: number }).status === 401) {
      router.replace("/");
    }
  }, [query.error, requireAuth, router]);
  return query;
}
