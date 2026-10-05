import { PageHeader } from "@/components/page-header";
import { TeamBuilder } from "@/components/team-builder";

export default function NewCustomTeamPage() {
  return (
    <>
      <PageHeader back="/teams/new" title="Custom team" subtitle="Build a roster by hand from any provider." />
      <TeamBuilder />
    </>
  );
}
