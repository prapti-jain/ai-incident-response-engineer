import Link from "next/link";

type Props = {
  current?: "dashboard" | "incidents";
};

export default function AppNav({ current }: Props) {
  const linkClass = (active: boolean) =>
    [
      "text-xs uppercase tracking-widest transition-colors",
      active ? "text-[#e5e7eb]" : "text-[#6b7280] hover:text-[#9ca3af]",
    ].join(" ");

  return (
    <nav className="flex items-center gap-4">
      <Link href="/" className={linkClass(current === "dashboard")}>
        Dashboard
      </Link>
      <span className="text-[#2a2f38]">|</span>
      <Link href="/incidents" className={linkClass(current === "incidents")}>
        Incidents
      </Link>
    </nav>
  );
}
