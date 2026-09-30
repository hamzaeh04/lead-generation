"use client";

import { useMutation } from "@tanstack/react-query";
import {
  Briefcase,
  Building2,
  ChevronDown,
  Landmark,
  type LucideIcon,
  MapPin,
  Search,
  ShoppingBag,
  Sparkles,
  SlidersHorizontal,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Label";
import { Input } from "@/components/ui/Input";
import { MultiSelectChips } from "@/components/ui/MultiSelectChips";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { TagInput } from "@/components/ui/TagInput";
import { Textarea } from "@/components/ui/Textarea";
import { cn } from "@/lib/cn";
import { type DiscoveryCriteria, parseProspectPrompt } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";

const EXAMPLE_PROMPTS: { text: string; icon: LucideIcon }[] = [
  { text: "VPs of Sales in SaaS companies, 50-200 employees", icon: Briefcase },
  { text: "Fintech founders, Series A or later", icon: Landmark },
  { text: "CMOs in e-commerce, based in the US", icon: ShoppingBag },
];

const APOLLO_SENIORITIES = [
  "owner", "founder", "c_suite", "partner", "vp", "head", "director", "manager", "senior", "entry", "intern",
];

const APOLLO_EMAIL_STATUS = ["verified", "unverified", "likely to engage", "unavailable"];

const SMARTLEAD_LEVELS = ["Staff", "Manager", "Director", "VP", "C-Suite", "Owner"];

const HEADCOUNT_BANDS = ["1 - 10", "11 - 50", "51 - 200", "201 - 500", "501 - 1K", "1K - 10K", "> 10K"];

function extra(criteria: DiscoveryCriteria, key: string): unknown {
  return criteria.extra_filters?.[key];
}

function countActiveFilters(criteria: DiscoveryCriteria): number {
  let count = 0;
  if (criteria.job_titles?.length) count++;
  if (criteria.seniorities?.length) count++;
  if (criteria.employee_count_min != null) count++;
  if (criteria.employee_count_max != null) count++;
  if (criteria.keywords) count++;
  if (criteria.domain) count++;
  if (criteria.city) count++;
  if (criteria.state) count++;
  if (criteria.country) count++;
  if (criteria.extra_filters) {
    for (const value of Object.values(criteria.extra_filters)) {
      if (Array.isArray(value) ? value.length > 0 : !!value) count++;
    }
  }
  return count;
}

function setExtra(
  criteria: DiscoveryCriteria,
  key: string,
  value: unknown,
  onChange: (criteria: DiscoveryCriteria) => void
) {
  onChange({ ...criteria, extra_filters: { ...criteria.extra_filters, [key]: value } });
}

const SECTION_ACCENTS: Record<string, string> = {
  Role: "from-indigo-500 to-violet-500",
  Company: "from-violet-500 to-fuchsia-500",
  Location: "from-fuchsia-500 to-pink-500",
  Advanced: "from-slate-500 to-slate-400",
};

function FilterSection({
  icon: Icon,
  title,
  children,
  className,
  compact,
}: {
  icon: LucideIcon;
  title: string;
  children: React.ReactNode;
  className?: string;
  /** Single-column, no matter the viewport — used in the narrow live-filters
   * side panel next to the AI prompt box, where the normal sm:grid-cols-2
   * would squeeze every field into an unreadably thin column. */
  compact?: boolean;
}) {
  const accent = SECTION_ACCENTS[title] ?? "from-accent to-accent";
  return (
    <div
      className={cn(
        "group relative flex flex-col gap-4 overflow-hidden rounded-xl border border-border bg-surface p-4 shadow-card transition-colors hover:border-accent/30",
        className
      )}
    >
      <div className={cn("absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r", accent)} />
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm",
            accent
          )}
        >
          <Icon className="h-3.5 w-3.5" />
        </span>
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
      </div>
      <div className={cn("grid grid-cols-1 gap-4", !compact && "sm:grid-cols-2")}>{children}</div>
    </div>
  );
}

function LocationFields({
  criteria,
  onChange,
  compact,
}: {
  criteria: DiscoveryCriteria;
  onChange: (criteria: DiscoveryCriteria) => void;
  compact?: boolean;
}) {
  return (
    <div className={cn("grid grid-cols-1 gap-2 sm:col-span-2", !compact && "sm:grid-cols-3")}>
      <Input
        value={criteria.city ?? ""}
        onChange={(e) => onChange({ ...criteria, city: e.target.value || undefined })}
        placeholder="City"
      />
      <Input
        value={criteria.state ?? ""}
        onChange={(e) => onChange({ ...criteria, state: e.target.value || undefined })}
        placeholder="State"
      />
      <Input
        value={criteria.country ?? ""}
        onChange={(e) => onChange({ ...criteria, country: e.target.value || undefined })}
        placeholder="Country"
      />
    </div>
  );
}

function ApolloManualFields({
  criteria,
  onChange,
  compact,
}: {
  criteria: DiscoveryCriteria;
  onChange: (criteria: DiscoveryCriteria) => void;
  compact?: boolean;
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const colSpan = compact ? "" : "lg:col-span-2";

  return (
    <div className={cn("grid grid-cols-1 gap-4", !compact && "lg:grid-cols-2")}>
      <FilterSection icon={Briefcase} title="Role" compact={compact}>
        <Field label="Job titles" className={compact ? "" : "sm:col-span-2"}>
          <TagInput
            value={criteria.job_titles ?? []}
            onChange={(v) => onChange({ ...criteria, job_titles: v })}
            placeholder="e.g. VP of Sales"
          />
        </Field>
        <Field label="Seniority" className={compact ? "" : "sm:col-span-2"}>
          <MultiSelectChips
            options={APOLLO_SENIORITIES.map((s) => ({ value: s, label: s.replace(/_/g, " ") }))}
            value={criteria.seniorities ?? []}
            onChange={(v) => onChange({ ...criteria, seniorities: v })}
          />
        </Field>
      </FilterSection>

      <FilterSection icon={Building2} title="Company" compact={compact}>
        <Field label="Min employees">
          <Input
            type="number"
            min={0}
            value={criteria.employee_count_min ?? ""}
            onChange={(e) => onChange({ ...criteria, employee_count_min: e.target.value ? Number(e.target.value) : undefined })}
          />
        </Field>
        <Field label="Max employees">
          <Input
            type="number"
            min={0}
            value={criteria.employee_count_max ?? ""}
            onChange={(e) => onChange({ ...criteria, employee_count_max: e.target.value ? Number(e.target.value) : undefined })}
          />
        </Field>
        <Field label="Keywords" htmlFor="keywords" className={compact ? "" : "sm:col-span-2"}>
          <Input
            id="keywords"
            value={criteria.keywords ?? ""}
            onChange={(e) => onChange({ ...criteria, keywords: e.target.value || undefined })}
            placeholder="e.g. dental clinic"
          />
        </Field>
      </FilterSection>

      <FilterSection icon={MapPin} title="Location" className={colSpan} compact={compact}>
        <LocationFields criteria={criteria} onChange={onChange} compact={compact} />
      </FilterSection>

      <div className={colSpan}>
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          className="flex w-full items-center justify-between rounded-lg border border-dashed border-border px-3 py-2 text-sm font-medium text-fgMuted transition-colors hover:border-accent/40 hover:text-fg"
        >
          <span className="flex items-center gap-1.5">
            <SlidersHorizontal className="h-3.5 w-3.5" />
            Advanced filters
          </span>
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", advancedOpen && "rotate-180")} />
        </button>
        {advancedOpen && (
          <FilterSection icon={SlidersHorizontal} title="Advanced" className="mt-3" compact={compact}>
            <Field label="Technologies used">
              <TagInput
                value={(extra(criteria, "technologies") as string[] | undefined) ?? []}
                onChange={(v) => setExtra(criteria, "technologies", v, onChange)}
                placeholder="e.g. salesforce"
              />
            </Field>
            <Field label="Email status" hint="Leave empty for any">
              <MultiSelectChips
                options={APOLLO_EMAIL_STATUS.map((s) => ({ value: s, label: s }))}
                value={(extra(criteria, "email_status") as string[] | undefined) ?? []}
                onChange={(v) => setExtra(criteria, "email_status", v, onChange)}
              />
            </Field>
          </FilterSection>
        )}
      </div>
    </div>
  );
}

function SmartleadManualFields({
  criteria,
  onChange,
  compact,
}: {
  criteria: DiscoveryCriteria;
  onChange: (criteria: DiscoveryCriteria) => void;
  compact?: boolean;
}) {
  const colSpan = compact ? "" : "lg:col-span-2";
  return (
    <div className={cn("grid grid-cols-1 gap-4", !compact && "lg:grid-cols-2")}>
      <FilterSection icon={Briefcase} title="Role" compact={compact}>
        <Field label="Job titles">
          <TagInput
            value={criteria.job_titles ?? []}
            onChange={(v) => onChange({ ...criteria, job_titles: v })}
            placeholder="e.g. Head of Growth"
          />
        </Field>
        <Field label="Department">
          <TagInput
            value={(extra(criteria, "department") as string[] | undefined) ?? []}
            onChange={(v) => setExtra(criteria, "department", v, onChange)}
            placeholder="e.g. Sales"
          />
        </Field>
        <Field label="Level" className={compact ? "" : "sm:col-span-2"}>
          <MultiSelectChips
            options={SMARTLEAD_LEVELS.map((s) => ({ value: s, label: s }))}
            value={(extra(criteria, "level") as string[] | undefined) ?? []}
            onChange={(v) => setExtra(criteria, "level", v, onChange)}
          />
        </Field>
      </FilterSection>

      <FilterSection icon={Building2} title="Company" compact={compact}>
        <Field label="Company domain" htmlFor="domain">
          <Input
            id="domain"
            value={criteria.domain ?? ""}
            onChange={(e) => onChange({ ...criteria, domain: e.target.value || undefined })}
            placeholder="e.g. acme.com"
          />
        </Field>
        <Field label="Industry">
          <TagInput
            value={(extra(criteria, "companyIndustry") as string[] | undefined) ?? []}
            onChange={(v) => setExtra(criteria, "companyIndustry", v, onChange)}
            placeholder="e.g. Financial Services"
          />
        </Field>
        <Field label="Company size" className={compact ? "" : "sm:col-span-2"}>
          <MultiSelectChips
            options={HEADCOUNT_BANDS.map((s) => ({ value: s, label: s }))}
            value={(extra(criteria, "companyHeadCount") as string[] | undefined) ?? []}
            onChange={(v) => setExtra(criteria, "companyHeadCount", v, onChange)}
          />
        </Field>
      </FilterSection>

      <FilterSection icon={MapPin} title="Location" className={colSpan} compact={compact}>
        <LocationFields criteria={criteria} onChange={onChange} compact={compact} />
      </FilterSection>
    </div>
  );
}

function ManualFieldsForProvider({
  provider,
  criteria,
  onChange,
  compact,
}: {
  provider: "apollo" | "smartlead";
  criteria: DiscoveryCriteria;
  onChange: (criteria: DiscoveryCriteria) => void;
  compact?: boolean;
}) {
  return provider === "apollo" ? (
    <ApolloManualFields criteria={criteria} onChange={onChange} compact={compact} />
  ) : (
    <SmartleadManualFields criteria={criteria} onChange={onChange} compact={compact} />
  );
}

/** Filter-count badge + result-limit picker + (optional) run button — the
 * same control row used under the Manual filters tab, reused under the
 * live side panel next to the AI prompt box so both places let you set
 * how many leads to fetch. The run button itself is opt-in: AI Search
 * already parses the prompt and runs the search in one click (see
 * parseMutation below), so a second "Run search" button next to the live
 * panel would just be a redundant way to re-trigger the exact same thing. */
function FiltersFooterBar({
  criteria,
  onCriteriaChange,
  onSearch,
  searching,
  runLabel = "Run search",
  showRunButton = true,
}: {
  criteria: DiscoveryCriteria;
  onCriteriaChange: (criteria: DiscoveryCriteria) => void;
  onSearch: (criteria: DiscoveryCriteria) => void;
  searching: boolean;
  runLabel?: string;
  showRunButton?: boolean;
}) {
  const activeFilterCount = countActiveFilters(criteria);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface/95 p-3 pl-4 shadow-popover backdrop-blur">
      <div className="flex items-center gap-2 text-sm text-fgMuted">
        <span
          className={cn(
            "flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-semibold",
            activeFilterCount > 0 ? "bg-accent text-white" : "bg-surface2 text-fgSubtle"
          )}
        >
          {activeFilterCount}
        </span>
        {activeFilterCount > 0
          ? `filter${activeFilterCount === 1 ? "" : "s"} applied`
          : "No filters set — this will search broadly"}
      </div>
      <div className="flex items-center gap-2">
        <Select
          value={String(criteria.limit ?? 25)}
          onValueChange={(v) => onCriteriaChange({ ...criteria, limit: Number(v) })}
        >
          <SelectTrigger className="h-10 w-[130px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[10, 25, 50, 100].map((n) => (
              <SelectItem key={n} value={String(n)}>
                {n} results
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {showRunButton && (
          <Button
            type="button"
            size="lg"
            loading={searching}
            onClick={() => onSearch(criteria)}
            className="border-none bg-gradient-to-r from-indigo-500 via-violet-500 to-pink-500 font-semibold text-white shadow-sm hover:opacity-90"
          >
            <Search className="h-3.5 w-3.5" />
            {runLabel}
          </Button>
        )}
      </div>
    </div>
  );
}

export function ProspectPanel({
  provider,
  workspaceId,
  criteria,
  onCriteriaChange,
  onSearch,
  searching,
}: {
  provider: "apollo" | "smartlead";
  workspaceId: string | undefined;
  criteria: DiscoveryCriteria;
  onCriteriaChange: (criteria: DiscoveryCriteria) => void;
  onSearch: (criteria: DiscoveryCriteria) => void;
  searching: boolean;
}) {
  const [mode, setMode] = useState<"prompt" | "manual">("prompt");
  const [prompt, setPrompt] = useState("");
  const promptRef = useRef<HTMLTextAreaElement>(null);

  // Fixed rows/height clipped anything past 3 lines behind a scrollbar
  // inside a tiny box, with the AI Search button sitting right on top of
  // it — grow the box to fit what's actually typed instead (capped so an
  // extreme prompt scrolls rather than pushing the button off-screen).
  useEffect(() => {
    const el = promptRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [prompt]);

  const parseMutation = useMutation({
    mutationFn: () => parseProspectPrompt({ workspace_id: workspaceId!, provider, prompt }),
    onSuccess: (result) => {
      const parsedCriteria = { ...result.criteria, limit: criteria.limit };
      onCriteriaChange(parsedCriteria);
      onSearch(parsedCriteria);
    },
    onError: (error) => toast.error(getErrorMessage(error, "Couldn't understand that prompt.")),
  });

  return (
    <div className="flex flex-col gap-5">
      <Tabs value={mode} onValueChange={(v) => setMode(v as "prompt" | "manual")}>
        <TabsList>
          <TabsTrigger value="prompt">
            <Sparkles className="mr-1.5 h-3 w-3" />
            AI prompt
          </TabsTrigger>
          <TabsTrigger value="manual">Manual filters</TabsTrigger>
        </TabsList>
      </Tabs>

      {mode === "prompt" && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
        <div className="flex flex-col gap-5">
          <div className="relative">
            <div
              aria-hidden
              className="pointer-events-none absolute -inset-1 rounded-[28px] bg-gradient-to-r from-indigo-500/25 via-violet-500/25 to-pink-500/25 blur-xl"
            />
            <div className="relative overflow-hidden rounded-3xl border border-border bg-surface shadow-popover">
              <div className="flex items-center gap-2 px-5 pt-4">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 via-violet-500 to-pink-500 text-white">
                  <Sparkles className="h-3 w-3" />
                </span>
                <span className="text-xs font-semibold uppercase tracking-wide text-fgSubtle">
                  AI-powered search
                </span>
              </div>

              <div className="relative px-5 pb-16 pt-2">
                <Textarea
                  ref={promptRef}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && prompt.trim() && workspaceId) {
                      e.preventDefault();
                      parseMutation.mutate();
                    }
                  }}
                  placeholder="Ask AI to build your prospect list…"
                  rows={3}
                  className="max-h-[300px] min-h-[92px] w-full resize-none overflow-y-auto border-none bg-transparent p-0 text-lg leading-relaxed shadow-none placeholder:text-fgSubtle focus:ring-0"
                />
                <Button
                  type="button"
                  loading={parseMutation.isPending || searching}
                  disabled={!prompt.trim() || !workspaceId}
                  onClick={() => parseMutation.mutate()}
                  className="absolute bottom-4 right-5 shrink-0 rounded-full border-none bg-gradient-to-r from-indigo-500 via-violet-500 to-pink-500 px-4 text-white shadow-sm hover:opacity-90"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  AI Search
                </Button>
              </div>

              <div className="flex items-center justify-between gap-3 border-t border-border bg-surface2/40 px-5 py-2.5">
                <span className="text-xs text-fgSubtle">Describe who you&apos;re looking for, in plain English.</span>
                <span className="hidden items-center gap-1 text-xs text-fgSubtle sm:flex">
                  <kbd className="rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[10px]">
                    ⌘
                  </kbd>
                  <kbd className="rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[10px]">
                    Enter
                  </kbd>
                  to search
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-xs font-medium text-fgSubtle">Try one of these</span>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {EXAMPLE_PROMPTS.map(({ text, icon: Icon }) => (
                <button
                  key={text}
                  type="button"
                  onClick={() => setPrompt(text)}
                  className="group flex flex-col gap-2.5 rounded-xl border border-border bg-surface p-3.5 text-left shadow-card transition-all hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-popover"
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accentSoft text-accent">
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  <span className="text-xs leading-snug text-fgMuted group-hover:text-fg">{text}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-fg">
            <SlidersHorizontal className="h-3.5 w-3.5 text-fgSubtle" />
            Filters
            {parseMutation.isPending && (
              <span className="text-xs font-normal text-fgSubtle">— AI is filling these in…</span>
            )}
          </div>
          <p className="text-xs text-fgSubtle">
            Fills in automatically from your prompt, or edit directly — either way it&apos;s what actually
            gets searched.
          </p>
          <div className="flex max-h-[560px] flex-col gap-4 overflow-y-auto rounded-xl border border-border bg-surface2/30 p-3">
            <ManualFieldsForProvider provider={provider} criteria={criteria} onChange={onCriteriaChange} compact />
          </div>
          <FiltersFooterBar
            criteria={criteria}
            onCriteriaChange={onCriteriaChange}
            onSearch={onSearch}
            searching={searching}
            showRunButton={false}
          />
        </div>
        </div>
      )}

      {mode === "manual" && (
        <div className="flex flex-col gap-5">
          <ManualFieldsForProvider provider={provider} criteria={criteria} onChange={onCriteriaChange} />
          <div className="sticky bottom-4 z-10">
            <FiltersFooterBar
              criteria={criteria}
              onCriteriaChange={onCriteriaChange}
              onSearch={onSearch}
              searching={searching}
            />
          </div>
        </div>
      )}
    </div>
  );
}
