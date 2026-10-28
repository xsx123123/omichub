import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, Menu, X, Dna, Settings, Leaf } from 'lucide-react';

const navLinks = [
  { path: '/database', label: 'Database', icon: Database },
  { path: '/database/browse', label: 'Browse', icon: Leaf },
  { path: '/database/admin', label: 'Admin', icon: Settings },
];

export default function Navbar() {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 border-b border-space-700/50 bg-space-900/90 backdrop-blur-card">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-nebula-500 to-aurora-500">
              <Dna className="h-5 w-5 text-white" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-display text-lg font-bold text-space-100">
                OmicHub
              </span>
              <span className="hidden text-space-600 sm:inline">|</span>
              <span className="hidden font-display text-sm font-semibold text-nebula-400 sm:inline">
                Database
              </span>
            </div>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden items-center gap-1 md:flex">
            {navLinks.map(link => {
              const isActive = location.pathname === link.path;
              return (
                <Link
                  key={link.path}
                  to={link.path}
                  className={`relative flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'text-nebula-400'
                      : 'text-space-400 hover:text-space-200'
                  }`}
                >
                  <link.icon className="h-4 w-4" />
                  {link.label}
                  {isActive && (
                    <motion.div
                      layoutId="navbar-indicator"
                      className="absolute inset-x-2 -bottom-[17px] h-[2px] bg-nebula-500"
                      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                    />
                  )}
                </Link>
              );
            })}
          </div>

          {/* Right side actions */}
          <div className="hidden items-center gap-3 md:flex">
            <div className="flex items-center gap-2 rounded-full bg-space-800 px-3 py-1.5 text-xs text-space-500 border border-space-700/50">
              <span className="h-1.5 w-1.5 rounded-full bg-success-500 animate-pulse-dot" />
              System Online
            </div>
          </div>

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="flex h-10 w-10 items-center justify-center rounded-lg text-space-400 hover:bg-space-800 md:hidden"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="border-t border-space-700/50 bg-space-900/95 backdrop-blur-card md:hidden overflow-hidden"
          >
            <div className="space-y-1 px-6 py-4">
              {navLinks.map(link => {
                const isActive = location.pathname === link.path;
                return (
                  <Link
                    key={link.path}
                    to={link.path}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-space-800 text-nebula-400'
                        : 'text-space-400 hover:bg-space-800 hover:text-space-200'
                    }`}
                  >
                    <link.icon className="h-4 w-4" />
                    {link.label}
                  </Link>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
