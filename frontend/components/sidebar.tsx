"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Anchor,
  Cpu,
  FileText,
  Globe,
  type LucideIcon,
  Plane,
  ShieldAlert,
  Wrench,
} from "lucide-react";

import { cn } from "@/lib/cn";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  domain: "maritime" | "aviation" | "cyber" | "web" | "case";
};

const PRIMARY: NavItem[] = [
  { href: "/maritime", label: "Maritime", icon: Anchor, domain: "maritime" },
  { href: "/aviation", label: "Aviation", icon: Plane, domain: "aviation" },
  { href: "/cyber", label: "Cyber Surface", icon: ShieldAlert, domain: "cyber" },
  { href: "/web", label: "AI Web Search", icon: Globe, domain: "web" },
  { href: "/case", label: "Case File", icon: FileText, domain: "case" },
];

const SECONDARY: NavItem[] = [
  { href: "/tooling", label: "Tooling Library", icon: Wrench, domain: "case" },
  { href: "/sensors", label: "Sensor Sim", icon: Cpu, domain: "case" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex w-56 flex-col gap-1 border-r border-border bg-bg-elevated p-3">
      <NavGroup label="Dashboards" items={PRIMARY} pathname={pathname} />
      <NavGroup label="Panels" items={SECONDARY} pathname={pathname} />
      <div className="mt-auto pt-3 text-[10px] uppercase tracking-wider text-fg-subtle">
        v0.1.0
      </div>
    </aside>
  );
}

function NavGroup({
  label,
  items,
  pathname,
}: {
  label: string;
  items: NavItem[];
  pathname: string;
}) {
  return (
    <div className="mb-3">
      <div className="mb-1 px-2 text-[10px] font-medium uppercase tracking-wider text-fg-subtle">
        {label}
      </div>
      <ul className="flex flex-col gap-0.5">
        {items.map((it) => {
          const active = pathname === it.href || pathname.startsWith(`${it.href}/`);
          const Icon = it.icon;
          return (
            <li key={it.href}>
              <Link
                href={it.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
                  active
                    ? "bg-bg-panel text-fg"
                    : "text-fg-muted hover:bg-bg-panel hover:text-fg",
                )}
              >
                <Icon size={14} className={cn("shrink-0", `text-domain-${it.domain}`)} />
                {it.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
