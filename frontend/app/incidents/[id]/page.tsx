"use client";

import { useParams } from "next/navigation";

import IncidentDetail from "@/components/IncidentDetail";

export default function IncidentDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  if (Number.isNaN(id)) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-[#f87171]">
        Invalid incident ID
      </div>
    );
  }

  return (
    <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <IncidentDetail incidentId={id} />
    </main>
  );
}
