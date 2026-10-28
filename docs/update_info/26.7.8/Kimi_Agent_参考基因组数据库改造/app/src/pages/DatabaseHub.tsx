import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, Database, Dna, Leaf, Activity, ChevronRight,
  Plus, FileCode, Terminal, X, Command, Filter, ArrowUp,
  Server, HardDrive
} from 'lucide-react';
import {
  speciesList,
  searchGenes,
  searchSpecies,
  statsOverview,
  type SpeciesDB,
  type Gene,
} from '@/data/mockData';

/* ─── easing ─── */
const easeEnter = [0, 0, 0.2, 1] as [number, number, number, number];
const easeBounce = [0.34, 1.56, 0.64, 1] as [number, number, number, number];

/* ─── Animated counter ─── */
function AnimatedNumber({ value, duration = 1200 }: { value: number; duration?: number }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          const start = performance.now();
          const step = (now: number) => {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setCount(Math.floor(eased * value));
            if (progress < 1) requestAnimationFrame(step);
          };
          requestAnimationFrame(step);
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [value, duration]);

  return <span ref={ref}>{count.toLocaleString()}</span>;
}

/* ─── Species Card ─── */
const sourceLabels = [
  { key: 'fa' as const, label: 'FA', color: 'cyan' },
  { key: 'gff' as const, label: 'GFF', color: 'aurora' },
  { key: 'go' as const, label: 'GO', color: 'success' },
  { key: 'kegg' as const, label: 'KEGG', color: 'info' },
];

function SpeciesCard({ species, index }: { species: SpeciesDB; index: number }) {
  const navigate = useNavigate();

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.4, delay: index * 0.08, ease: easeEnter }}
      whileHover={{ scale: 1.02 }}
      onClick={() => navigate(`/database/${species.id}`)}
      className="group relative cursor-pointer"
    >
      {/* Gradient border on hover */}
      <div className="absolute -inset-[1px] rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-250 pointer-events-none"
        style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.5) 0%, rgba(139,92,246,0.3) 50%, rgba(6,182,212,0.2) 100%)', padding: '1px' }}
      >
        <div className="h-full w-full rounded-2xl bg-space-800" />
      </div>

      <div className="relative h-full min-h-[220px] rounded-2xl border border-white/[0.06] bg-space-800 p-6 transition-all duration-250 group-hover:border-transparent group-hover:bg-[rgba(99,102,241,0.03)] group-hover:shadow-card-hover">
        {/* Header Row */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className="h-10 w-10 rounded-full shrink-0"
              style={{ background: species.gradient }}
            />
            <div>
              <h3 className="font-display text-base font-semibold text-space-200 leading-tight">
                {species.species}
              </h3>
              <p className="text-xs text-space-500">{species.commonName}</p>
            </div>
          </div>
          {/* Status dot */}
          <div
            className={`mt-1.5 h-3 w-3 rounded-full ${
              species.status === 'connected'
                ? 'bg-success-500 animate-pulse-dot'
                : species.status === 'error'
                ? 'bg-warning-500'
                : 'bg-error-500'
            }`}
          />
        </div>

        {/* Data Source Tags */}
        <div className="mt-4 flex flex-wrap gap-2">
          {sourceLabels.map(src => {
            const has = species.sources[src.key];
            const colorMap: Record<string, { border: string; bg: string; text: string }> = {
              cyan: { border: 'rgba(6,182,212,0.4)', bg: 'rgba(6,182,212,0.08)', text: '#22D3EE' },
              aurora: { border: 'rgba(139,92,246,0.4)', bg: 'rgba(139,92,246,0.08)', text: '#A78BFA' },
              success: { border: 'rgba(16,185,129,0.4)', bg: 'rgba(16,185,129,0.08)', text: '#34D399' },
              info: { border: 'rgba(59,130,246,0.4)', bg: 'rgba(59,130,246,0.08)', text: '#60A5FA' },
            };
            const c = colorMap[src.color];
            return (
              <span
                key={src.key}
                className="inline-flex h-[26px] items-center rounded-md px-2.5 font-mono text-[11px] font-medium"
                style={
                  has
                    ? { border: `1px solid ${c.border}`, background: c.bg, color: c.text }
                    : { border: '1px dashed #334155', color: '#475569', background: 'transparent' }
                }
              >
                {src.label}
              </span>
            );
          })}
        </div>

        {/* Footer Row */}
        <div className="mt-5 flex items-center justify-between">
          <span className="rounded-md bg-nebula-500/10 px-2.5 py-0.5 font-mono text-[11px] text-nebula-300">
            {species.version}
          </span>
          <div className="flex items-center gap-1.5 text-sm text-space-400 group-hover:text-space-300 transition-colors">
            <span>{species.geneCount.toLocaleString()} genes</span>
            <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* ─── Search Dropdown ─── */
function SearchDropdown({
  query,
  onSelect,
  onClose,
}: {
  query: string;
  onSelect: (type: 'gene' | 'species', id: string) => void;
  onClose: () => void;
}) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const genes = query.length >= 2 ? searchGenes(query) : [];
  const dbs = query.length >= 2 ? searchSpecies(query) : [];
  const allItems: { type: 'gene' | 'species'; item: Gene | SpeciesDB }[] = [
    ...genes.map(g => ({ type: 'gene' as const, item: g })),
    ...dbs.map(d => ({ type: 'species' as const, item: d })),
  ];

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(i => Math.min(i + 1, allItems.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(i => Math.max(i - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const sel = allItems[selectedIndex];
        if (sel) {
          if (sel.type === 'gene')
            onSelect('gene', (sel.item as Gene).geneId);
          else
            onSelect('species', (sel.item as SpeciesDB).id);
        }
      } else if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [allItems, selectedIndex, onSelect, onClose]);

  if (allItems.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25, ease: easeEnter }}
      className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-2xl border border-nebula-500/20 bg-space-800 shadow-dropdown max-h-[400px] overflow-y-auto scrollbar-thin"
    >
      {genes.length > 0 && (
        <div>
          <div className="px-4 py-2 text-[11px] font-medium uppercase tracking-wider text-space-500">
            Genes
          </div>
          {genes.map((gene, i) => (
            <div
              key={gene.geneId}
              onClick={() => onSelect('gene', gene.geneId)}
              className={`flex cursor-pointer items-center gap-3 px-4 py-2.5 transition-colors ${
                i === selectedIndex ? 'bg-nebula-500/10 border-l-[3px] border-nebula-500' : 'border-l-[3px] border-transparent hover:bg-nebula-500/[0.04]'
              }`}
            >
              <Dna className="h-4 w-4 shrink-0 text-nebula-400" />
              <div className="min-w-0 flex-1">
                <div className="font-mono text-[13px] text-space-200 truncate">{gene.geneId}</div>
                <div className="text-xs text-space-500 truncate">{gene.symbol} &middot; {gene.description.slice(0, 50)}...</div>
              </div>
              <span className="shrink-0 font-mono text-[11px] text-space-500">{gene.speciesName}</span>
            </div>
          ))}
        </div>
      )}
      {dbs.length > 0 && (
        <div>
          <div className="px-4 py-2 text-[11px] font-medium uppercase tracking-wider text-space-500 border-t border-space-700/50">
            Databases
          </div>
          {dbs.map((db, i) => {
            const idx = genes.length + i;
            return (
              <div
                key={db.id}
                onClick={() => onSelect('species', db.id)}
                className={`flex cursor-pointer items-center gap-3 px-4 py-2.5 transition-colors ${
                  idx === selectedIndex ? 'bg-nebula-500/10 border-l-[3px] border-nebula-500' : 'border-l-[3px] border-transparent hover:bg-nebula-500/[0.04]'
                }`}
              >
                <Database className="h-4 w-4 shrink-0 text-nebula-400" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-space-200 truncate">{db.species}</div>
                  <div className="text-xs text-space-500">{db.commonName} &middot; {db.version}</div>
                </div>
                <span className="shrink-0 font-mono text-[11px] text-space-500">{db.geneCount.toLocaleString()}</span>
              </div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}

/* ─── Add Database Modal ─── */
function AddDatabaseModal({ onClose }: { onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-[rgba(3,7,18,0.7)] backdrop-blur-sm px-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.3, ease: easeBounce }}
        onClick={e => e.stopPropagation()}
        className="w-full max-w-[560px] rounded-3xl border border-white/[0.08] bg-space-800 p-8 shadow-modal"
      >
        <div className="mb-6 flex items-center justify-between">
          <h2 className="font-display text-xl font-bold text-space-200">
            Add New Database Connection
          </h2>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-space-500 hover:bg-space-700 hover:text-space-300 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-5">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-space-300">Species Scientific Name</label>
            <input
              type="text"
              placeholder="e.g., Lactuca sativa"
              className="w-full rounded-xl border border-space-600 bg-space-900 px-4 py-3 text-sm text-space-200 placeholder-space-600 outline-none transition-colors focus:border-nebula-500 focus:ring-1 focus:ring-nebula-500/20"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-space-300">Common Name</label>
            <input
              type="text"
              placeholder="e.g., Lettuce"
              className="w-full rounded-xl border border-space-600 bg-space-900 px-4 py-3 text-sm text-space-200 placeholder-space-600 outline-none transition-colors focus:border-nebula-500 focus:ring-1 focus:ring-nebula-500/20"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-space-300">Genome Version</label>
            <input
              type="text"
              placeholder="e.g., v11"
              className="w-full rounded-xl border border-space-600 bg-space-900 px-4 py-3 text-sm text-space-200 placeholder-space-600 outline-none transition-colors focus:border-nebula-500 focus:ring-1 focus:ring-nebula-500/20"
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-space-300">Data Source File Paths</label>
            <div className="space-y-2">
              {[
                { icon: FileCode, label: 'FA file path' },
                { icon: Terminal, label: 'GFF file path' },
                { icon: Database, label: 'GO file path' },
                { icon: Server, label: 'KEGG file path' },
              ].map(({ icon: Icon, label }) => (
                <div key={label} className="flex items-center gap-2">
                  <Icon className="h-4 w-4 shrink-0 text-space-500" />
                  <input
                    type="text"
                    placeholder={label}
                    className="w-full rounded-lg border border-space-600 bg-space-900 px-3 py-2 font-mono text-xs text-space-200 placeholder-space-600 outline-none transition-colors focus:border-nebula-500"
                  />
                </div>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-dashed border-space-600 bg-space-900/50 p-4">
            <HardDrive className="h-5 w-5 text-space-500" />
            <div className="flex-1">
              <div className="text-sm font-medium text-space-300">Enable cross-version mapping</div>
              <div className="text-xs text-space-500">Map genes to a different genome assembly</div>
            </div>
            <button className="h-6 w-11 rounded-full bg-space-600 transition-colors hover:bg-space-500" />
          </div>
        </div>

        <div className="mt-8 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-xl border border-space-600 px-5 py-2.5 text-sm font-medium text-space-300 hover:border-space-500 hover:text-space-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onClose}
            className="rounded-xl bg-gradient-to-r from-nebula-500 to-aurora-500 px-5 py-2.5 text-sm font-medium text-white shadow-glow hover:brightness-110 transition-all"
          >
            Save Configuration
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

/* ─── Scroll to top ─── */
function ScrollToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 300);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <AnimatePresence>
      {visible && (
        <motion.button
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="fixed bottom-6 right-6 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-space-800 border border-space-600 text-space-400 shadow-card hover:border-nebula-500 hover:text-nebula-400 transition-colors"
        >
          <ArrowUp className="h-4 w-4" />
        </motion.button>
      )}
    </AnimatePresence>
  );
}

/* ═══════════════════════════════════════════
   MAIN PAGE: DatabaseHub
   ═══════════════════════════════════════════ */
export default function DatabaseHub() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const [filter, setFilter] = useState<'all' | 'connected' | 'disconnected' | 'error'>('all');
  const [sortBy, setSortBy] = useState<'recent' | 'name' | 'genes' | 'version'>('recent');
  const [showAddModal, setShowAddModal] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // Close search dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchFocused(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSearchSelect = useCallback(
    (type: 'gene' | 'species', id: string) => {
      if (type === 'gene') {
        const gene = searchGenes(id)[0];
        if (gene) {
          navigate(`/database/${gene.speciesId}/gene/${gene.geneId}`);
        }
      } else {
        navigate(`/database/${id}`);
      }
      setSearchFocused(false);
      setSearchQuery('');
    },
    [navigate]
  );

  // Filter & sort
  const filtered = speciesList.filter(s => {
    if (filter === 'connected') return s.status === 'connected';
    if (filter === 'disconnected') return s.status === 'disconnected';
    if (filter === 'error') return s.status === 'error';
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'name') return a.species.localeCompare(b.species);
    if (sortBy === 'genes') return b.geneCount - a.geneCount;
    if (sortBy === 'version') return a.version.localeCompare(b.version);
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });

  const filters: { key: typeof filter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'connected', label: 'Connected' },
    { key: 'disconnected', label: 'Disconnected' },
    { key: 'error', label: 'Error' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4, ease: easeEnter }}
    >
      {/* ═══════ HERO ═══════ */}
      <section className="relative min-h-[320px] overflow-hidden">
        {/* Background image with overlay */}
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: 'url(/db-hero-bg.jpg)' }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[rgba(11,17,32,0.85)] to-[rgba(11,17,32,0.95)]" />

        <div className="relative z-10 mx-auto flex max-w-[800px] flex-col items-center px-6 pb-12 pt-20 text-center">
          {/* Title */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: easeEnter }}
            className="font-display text-5xl font-bold tracking-tight text-space-100 sm:text-[48px]"
            style={{ letterSpacing: '-0.02em', lineHeight: 1.1 }}
          >
            {'\u6570\u636E\u5E93'}
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2, ease: easeEnter }}
            className="mt-3 text-base text-space-400"
          >
            Gene-Centric Database Browser
          </motion.p>

          {/* Description */}
          <motion.p
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.35, ease: easeEnter }}
            className="mt-4 max-w-[560px] text-sm leading-relaxed text-space-500"
          >
            Connect to FA, GFF, GO, and KEGG databases. Browse genes, explore
            annotations, and map across genome versions.
          </motion.p>

          {/* Search Bar */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, delay: 0.5, ease: easeBounce }}
            className="relative mt-8 w-full max-w-[640px]"
            ref={searchRef}
          >
            <div
              className={`flex items-center gap-3 rounded-full border bg-[rgba(17,24,39,0.8)] px-5 backdrop-blur-sm transition-all duration-200 ${
                searchFocused
                  ? 'border-nebula-500 shadow-[0_0_0_3px_rgba(99,102,241,0.15)]'
                  : 'border-nebula-500/30'
              }`}
            >
              <Search className="h-5 w-5 shrink-0 text-space-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onFocus={() => setSearchFocused(true)}
                placeholder="Search gene ID, symbol, or keyword..."
                className="h-[52px] w-full bg-transparent text-base text-space-200 placeholder-space-500 outline-none"
              />
              <div className="flex shrink-0 items-center gap-1 text-space-600">
                <Command className="h-3.5 w-3.5" />
                <span className="text-xs">K</span>
              </div>
            </div>

            <AnimatePresence>
              {searchFocused && searchQuery.length >= 2 && (
                <SearchDropdown
                  query={searchQuery}
                  onSelect={handleSearchSelect}
                  onClose={() => setSearchFocused(false)}
                />
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </section>

      {/* ═══════ STATS BAR ═══════ */}
      <section className="relative z-10 mx-auto max-w-[1400px] px-6 lg:px-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.4, ease: easeEnter }}
          className="-mt-6 rounded-2xl border border-white/[0.05] bg-space-800/[0.95] px-8 py-5"
        >
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            {[
              { icon: Database, value: statsOverview.totalDatabases, label: 'DATABASES' },
              { icon: Dna, value: statsOverview.totalGenes, label: 'TOTAL GENES' },
              { icon: Leaf, value: statsOverview.totalSpecies, label: 'SPECIES' },
              { icon: Activity, value: statsOverview.connected, label: 'CONNECTED' },
            ].map(({ icon: Icon, value, label }, i) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.1, ease: easeEnter }}
                className="flex flex-col items-center gap-1 text-center"
              >
                <Icon className="h-5 w-5 text-nebula-400" />
                <span className="font-display text-[28px] font-bold leading-tight text-space-200">
                  <AnimatedNumber value={value} />
                </span>
                <span className="text-[11px] font-medium uppercase tracking-[0.05em] text-space-500">
                  {label}
                </span>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* ═══════ FILTER & SORT ═══════ */}
      <section className="mx-auto max-w-[1400px] px-6 pt-8 lg:px-12">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.3, ease: easeEnter }}
          className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        >
          {/* Filter tabs */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
            {filters.map(f => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`relative whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium transition-all ${
                  filter === f.key
                    ? 'bg-nebula-500 text-white'
                    : 'text-space-400 hover:text-space-300'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Sort dropdown */}
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-space-500" />
            <span className="text-xs text-space-500">Sort by</span>
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value as typeof sortBy)}
              className="rounded-lg border border-space-600 bg-space-800 px-3 py-1.5 text-sm text-space-300 outline-none transition-colors focus:border-nebula-500"
            >
              <option value="recent">Recently Added</option>
              <option value="name">Species Name</option>
              <option value="genes">Gene Count</option>
              <option value="version">Version</option>
            </select>
          </div>
        </motion.div>
      </section>

      {/* ═══════ SPECIES CARD GRID ═══════ */}
      <section className="mx-auto max-w-[1400px] px-6 pb-12 pt-6 lg:px-12">
        {sorted.length > 0 ? (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {sorted.map((species, i) => (
              <SpeciesCard key={species.id} species={species} index={i} />
            ))}
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, ease: easeBounce }}
            className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border border-space-700/50 bg-space-800/50"
          >
            <Database className="h-16 w-16 text-space-600 mb-6" />
            <h3 className="font-display text-lg font-semibold text-space-400">
              No Databases Found
            </h3>
            <p className="mt-2 max-w-[400px] text-center text-sm text-space-500">
              No databases match the current filter. Try adjusting your filters or
              add a new database connection.
            </p>
          </motion.div>
        )}
      </section>

      {/* ═══════ ADMIN QUICK ACTIONS ═══════ */}
      <section className="mx-auto max-w-[1400px] px-6 pb-16 lg:px-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4, ease: easeEnter }}
          className="rounded-2xl border border-dashed border-nebula-500/20 bg-nebula-500/[0.03] p-6"
        >
          <h3 className="mb-4 font-display text-lg font-semibold text-nebula-400">
            Administration
          </h3>
          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              onClick={() => setShowAddModal(true)}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-nebula-500 to-aurora-500 px-5 py-2.5 text-sm font-medium text-white shadow-glow transition-all hover:brightness-110"
            >
              <Plus className="h-4 w-4" />
              Add Database
            </button>
            <Link
              to="/database/admin"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-space-600 px-5 py-2.5 text-sm font-medium text-space-300 transition-colors hover:border-nebula-400 hover:text-nebula-300"
            >
              <FileCode className="h-4 w-4" />
              Edit Config
            </Link>
            <button className="inline-flex items-center justify-center gap-2 rounded-xl border border-space-600 px-5 py-2.5 text-sm font-medium text-space-300 transition-colors hover:border-nebula-400 hover:text-nebula-300">
              <Terminal className="h-4 w-4" />
              View Logs
            </button>
          </div>
        </motion.div>
      </section>

      {/* ═══════ ADD DATABASE MODAL ═══════ */}
      <AnimatePresence>
        {showAddModal && <AddDatabaseModal onClose={() => setShowAddModal(false)} />}
      </AnimatePresence>

      {/* ═══════ SCROLL TO TOP ═══════ */}
      <ScrollToTop />
    </motion.div>
  );
}
