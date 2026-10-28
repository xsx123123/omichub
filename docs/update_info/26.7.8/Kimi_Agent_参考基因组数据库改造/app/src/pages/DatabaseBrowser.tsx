import { useParams, Link } from 'react-router';
import { motion } from 'framer-motion';
import { ArrowLeft, Dna, Database, AlertTriangle } from 'lucide-react';
import { getSpeciesById } from '@/data/mockData';

export default function DatabaseBrowser() {
  const { speciesId } = useParams<{ speciesId: string }>();
  const species = speciesId ? getSpeciesById(speciesId) : undefined;

  if (!species) {
    return (
      <div className="mx-auto max-w-[1400px] px-6 py-24 text-center lg:px-12">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-error-500/10 mx-auto mb-6">
          <AlertTriangle className="h-8 w-8 text-error-500" />
        </div>
        <h2 className="font-display text-2xl font-bold text-space-200 mb-2">
          Database Not Found
        </h2>
        <p className="mb-8 text-space-500">
          The requested species database could not be found.
        </p>
        <Link
          to="/database"
          className="inline-flex items-center gap-2 rounded-lg bg-space-800 px-4 py-2.5 text-sm font-medium text-space-300 hover:bg-space-700 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Database Hub
        </Link>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
    >
      {/* Header */}
      <div className="border-b border-space-700/50 bg-space-800/50">
        <div className="mx-auto max-w-[1400px] px-6 py-6 lg:px-12">
          <div className="mb-4">
            <Link
              to="/database"
              className="inline-flex items-center gap-1.5 text-sm text-space-500 hover:text-nebula-400 transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Database Hub
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <div
              className="h-12 w-12 rounded-full"
              style={{ background: species.gradient }}
            />
            <div>
              <h1 className="font-display text-2xl font-bold text-space-100">
                {species.species}
              </h1>
              <p className="text-sm text-space-500">
                {species.commonName} &middot; {species.version}
              </p>
            </div>
            <div className="ml-auto flex items-center gap-2 rounded-full bg-space-800 px-3 py-1.5 border border-space-700/50">
              <Database className="h-4 w-4 text-nebula-400" />
              <span className="font-mono text-sm text-space-300">
                {species.geneCount.toLocaleString()} genes
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Content stub */}
      <div className="mx-auto max-w-[1400px] px-6 py-12 lg:px-12">
        <div className="rounded-2xl border border-space-700/50 bg-space-800/50 p-12 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-space-700 mx-auto mb-6">
            <Dna className="h-8 w-8 text-nebula-400" />
          </div>
          <h2 className="font-display text-xl font-semibold text-space-200 mb-2">
            Gene Browser
          </h2>
          <p className="text-space-500 mb-2 max-w-md mx-auto">
            This page will display a searchable gene table with filters,
            chromosome browser, and statistics for {species.commonName}.
          </p>
          <p className="font-mono text-xs text-space-600">
            Species ID: {speciesId}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
