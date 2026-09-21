import { Megaphone, Search, Users } from "lucide-react";
import Link from "next/link";
import { LogoMarkIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const features = [
  {
    icon: Search,
    title: "Discover real leads",
    description: "Source companies and decision-makers from Apollo and Smartlead — never invented data.",
  },
  {
    icon: Users,
    title: "Score and prioritize",
    description: "Every lead is ranked by fit, intent, authority, and reachability so reps work the best ones first.",
  },
  {
    icon: Megaphone,
    title: "Run outreach campaigns",
    description: "Build sequences, enroll contacts, and track delivery, opens, and replies in one place.",
  },
];

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col bg-bg text-fg">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2 text-md font-semibold tracking-tight">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent text-white">
            <LogoMarkIcon className="h-3.5 w-3.5" stroke="currentColor" />
          </span>
          Lead Intelligence
        </div>
        <div className="flex items-center gap-2">
          <Link href="/login">
            <Button variant="ghost" size="sm">
              Log in
            </Button>
          </Link>
          <Link href="/register">
            <Button size="sm">Create workspace</Button>
          </Link>
        </div>
      </header>

      <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-6 px-6 py-20 text-center">
        <div className="flex flex-col gap-3">
          <h1 className="text-4xl font-semibold tracking-tight text-fg">
            Find, score, and reach your next customer
          </h1>
          <p className="text-lg text-fgMuted">
            A B2B lead-generation platform for agencies and sales teams — real prospect data,
            a CRM pipeline, and outbound campaigns, all in one workspace.
          </p>
        </div>
        <div className="flex gap-3">
          <Link href="/register">
            <Button size="lg">Create your workspace</Button>
          </Link>
          <Link href="/login">
            <Button variant="ghost" size="lg">
              Log in
            </Button>
          </Link>
        </div>
      </section>

      <section className="mx-auto grid w-full max-w-5xl grid-cols-1 gap-4 px-6 pb-20 sm:grid-cols-3">
        {features.map((feature) => (
          <Card key={feature.title} className="flex flex-col gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accentSoft text-accent">
              <feature.icon className="h-[18px] w-[18px]" />
            </span>
            <h2 className="text-md font-semibold text-fg">{feature.title}</h2>
            <p className="text-sm text-fgMuted">{feature.description}</p>
          </Card>
        ))}
      </section>
    </main>
  );
}
