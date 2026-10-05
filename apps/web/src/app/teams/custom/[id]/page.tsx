"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { CardSkeletons, QueryError } from "@/components/query-state";
import { TeamBuilder } from "@/components/team-builder";
import { api } from "@/lib/api";

export default function EditCustomTeamPage() {
  const { id } = useParams<{ id: string }>();
  const query = useQuery({ queryKey: ["manual-team", id], queryFn: () => api.manualTeam(Number(id)) });
  return (
    <>
      <PageHeader back="/teams" title="Edit custom team" />
      {query.isPending && <CardSkeletons count={2} />}
      {query.isError && <QueryError error={query.error} />}
      {query.data && <TeamBuilder key={query.data.id} team={query.data} />}
    </>
  );
}
