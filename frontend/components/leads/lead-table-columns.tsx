import { type ColumnDef } from "@tanstack/react-table";
import { Check, CheckCheck } from "lucide-react";
import Link from "next/link";
import { Pill } from "@/components/ui/Pill";
import { type Contact, type LeadStatus } from "@/lib/api";

export const statusOptions: { value: LeadStatus | "all"; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "new", label: "New" },
  { value: "verified", label: "Verified" },
  { value: "ready_for_outreach", label: "Ready for outreach" },
  { value: "contacted", label: "Contacted" },
  { value: "opened", label: "Opened" },
  { value: "clicked", label: "Clicked" },
  { value: "replied", label: "Replied" },
  { value: "interested", label: "Interested" },
  { value: "meeting", label: "Meeting" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
  { value: "unsubscribed", label: "Unsubscribed" },
  { value: "bounced", label: "Bounced" },
];

export const bulkTargetStatuses: LeadStatus[] = ["ready_for_outreach", "contacted", "interested", "lost"];

export const tierTone: Record<string, "success" | "accent" | "warning" | "danger" | "muted"> = {
  A: "success",
  B: "accent",
  C: "warning",
  D: "muted",
  E: "danger",
};

function GradeCell({ contact }: { contact: Contact }) {
  const qualification = contact.latest_qualification;
  if (!qualification) {
    return <span className="text-fgSubtle">—</span>;
  }
  return <Pill tone={tierTone[qualification.tier] ?? "muted"}>Tier {qualification.tier}</Pill>;
}

// WhatsApp-style read receipt: nothing until a campaign has actually
// emailed this lead, one gray tick once it's sent, two blue ticks once
// it's been opened. Nothing to click — a passive status signal only.
function EmailTicksCell({ contact }: { contact: Contact }) {
  const status = contact.email_track_status;
  if (!status) return null;
  if (status === "opened") {
    return (
      <span className="inline-flex items-center text-accent" title="Sent and opened">
        <CheckCheck className="h-4 w-4" />
      </span>
    );
  }
  return (
    <span className="inline-flex items-center text-fgSubtle" title="Sent, not opened yet">
      <Check className="h-4 w-4" />
    </span>
  );
}

export const statusTone: Record<string, "success" | "warning" | "danger" | "accent" | "muted"> = {
  won: "success",
  meeting: "success",
  verified: "success",
  interested: "accent",
  replied: "accent",
  ready_for_outreach: "accent",
  bounced: "danger",
  unsubscribed: "danger",
  lost: "danger",
  contacted: "warning",
  opened: "warning",
  clicked: "warning",
};

export const leadColumns: ColumnDef<Contact, unknown>[] = [
  {
    accessorKey: "full_name",
    header: "Name",
    cell: ({ row }) => (
      <Link
        href={`/leads/${row.original.id}`}
        className="font-medium text-fg hover:text-accent"
        onClick={(e) => e.stopPropagation()}
      >
        {row.original.full_name ?? row.original.email ?? "Unnamed contact"}
      </Link>
    ),
  },
  {
    id: "grade",
    header: "Grade",
    cell: ({ row }) => <GradeCell contact={row.original} />,
  },
  {
    id: "score",
    header: "Score",
    cell: ({ row }) => {
      const qualification = row.original.latest_qualification;
      if (!qualification) return <span className="text-fgSubtle">—</span>;
      return (
        <span className="font-mono text-fg" title={`Confidence ${qualification.confidence}%`}>
          {Math.round(qualification.composite_score)}
        </span>
      );
    },
  },
  {
    accessorKey: "company_name",
    header: "Company",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.company_name ?? "—"}</span>,
  },
  {
    accessorKey: "job_title",
    header: "Title",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.job_title ?? "—"}</span>,
  },
  {
    accessorKey: "email",
    header: "Email",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.email ?? "—"}</span>,
  },
  {
    id: "email_track_status",
    header: "Delivery",
    cell: ({ row }) => <EmailTicksCell contact={row.original} />,
  },
  {
    accessorKey: "phone",
    header: "Phone",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.phone ?? "—"}</span>,
  },
  {
    id: "location",
    header: "Location",
    cell: ({ row }) => (
      <span className="text-fgMuted">
        {[row.original.city, row.original.state, row.original.country].filter(Boolean).join(", ") || "—"}
      </span>
    ),
  },
  {
    accessorKey: "seniority",
    header: "Seniority",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.seniority ?? "—"}</span>,
  },
  {
    accessorKey: "department",
    header: "Department",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.department ?? "—"}</span>,
  },
  {
    id: "industry",
    header: "Industry",
    cell: ({ row }) => (
      <span className="text-fgMuted">
        {[row.original.industry, row.original.sub_industry].filter(Boolean).join(" · ") || "—"}
      </span>
    ),
  },
  {
    accessorKey: "company_headcount",
    header: "Company size",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.company_headcount ?? "—"}</span>,
  },
  {
    accessorKey: "company_revenue",
    header: "Revenue",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.company_revenue ?? "—"}</span>,
  },
  {
    accessorKey: "linkedin_url",
    header: "LinkedIn",
    cell: ({ row }) =>
      row.original.linkedin_url ? (
        <a
          href={row.original.linkedin_url}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="text-accent hover:underline"
        >
          View profile
        </a>
      ) : (
        <span className="text-fgMuted">—</span>
      ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Pill tone={statusTone[row.original.status] ?? "muted"}>{row.original.status.replace(/_/g, " ")}</Pill>
    ),
  },
  {
    accessorKey: "last_seen",
    header: "Last seen",
    cell: ({ row }) => (
      <span className="text-fgMuted">{new Date(row.original.last_seen).toLocaleDateString()}</span>
    ),
  },
];
