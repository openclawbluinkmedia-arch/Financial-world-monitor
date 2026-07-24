"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function PortfolioRedirect() {
  const r = useRouter();
  useEffect(() => { r.replace("/"); }, [r]);
  return null;
}
