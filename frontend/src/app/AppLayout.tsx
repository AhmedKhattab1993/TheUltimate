import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/screener', label: 'Screener' },
  { to: '/backtests', label: 'Backtests' },
  { to: '/grid', label: 'Grid Runs' },
  { to: '/grid/results', label: 'Grid Results' },
  { to: '/optimizer', label: 'Optimizer' },
  { to: '/data', label: 'Data' },
  { to: '/results/combined', label: 'Combined' },
]

function NavigationLink({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
          isActive
            ? 'bg-primary text-primary-foreground'
            : 'text-muted-foreground hover:text-primary'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

export function AppLayout() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <h1 className="text-lg font-semibold">MarketStructure Toolkit</h1>
          <nav className="flex items-center gap-2">
            {navItems.map((item) => (
              <NavigationLink key={item.to} {...item} />
            ))}
          </nav>
        </div>
      </header>
      <main className="container mx-auto px-4 py-6 min-h-[calc(100vh-4rem)]">
        <Outlet />
      </main>
    </div>
  )
}
