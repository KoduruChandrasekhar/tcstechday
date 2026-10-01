// Primary navigation. Areas of the product, not steps of a walkthrough.
export const NAV = [
  { href: "/", label: "Overview", icon: "home", hint: "Season status, store network and what needs attention" },
  { href: "/promotions", label: "Promotions", icon: "tag", hint: "Recommended and blocked promotions" },
  { href: "/planner", label: "Planner", icon: "sliders", hint: "Test a promotion before sending it for approval" },
  { href: "/inventory", label: "Inventory", icon: "box", hint: "Stock against festival demand, city by city" },
  { href: "/customers", label: "Customers", icon: "users", hint: "Which customer groups an offer persuades" },
  { href: "/approvals", label: "Approvals", icon: "check", hint: "Three-team sign-off and season results" },
  { href: "/performance", label: "Performance", icon: "chart", hint: "How past forecasts compared with results" },
];

export const navFor = (path: string) =>
  [...NAV].sort((a, b) => b.href.length - a.href.length).find((n) => (n.href === "/" ? path === "/" : path === n.href || path.startsWith(n.href + "/")));
