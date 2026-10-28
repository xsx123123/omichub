import { useParams, Link } from 'react-router';
import { motion } from 'framer-motion';
import { ArrowLeft, Dna, FileText, AlertTriangle } from 'lucide-react';
import { getGeneById, getSpeciesById } from '@/data/mockData';

export default function GeneDetail() {
  const { speciesId, geneId } = useParams<{ speciesId: string; geneId: string }>();
  const gene = geneId ? getGeneById(geneId) : undefined;
  const species = speciesId ? getSpeciesById(speciesId) : undefined;

  if (!gene || !species) {
    return (
      <div className="mx-auto max-w-[1400px] px-6 py-24 text-center lg:px-12">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-error-500/10 mx-auto mb-6">
          <AlertTriangle className="h-8 w-8 text-error-500" />
        </div>
        <h2 className="font-display text-2xl font-bold text-space-200 mb-2">
          Gene Not Found
        </h2>
        <p className="mb-8 text-space-500">
          The requested gene could not be found in this database.
        </p>
        <Link
          to={speciesId ? `/database/${speciesId}` : '/database'}
          className="inline-flex items-center gap-2 rounded-lg bg-space-800 px-4 py-2.5 text-sm font-medium text-space-300 hover:bg-space-700 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
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
          <div className="mb-4 flex items-center gap-2 text-sm text-space-500">
            <Link to="/database" className="hover:text-nebula-400 transition-colors">Database</Link>
            <span>/</span>
            <Link to={`/database/${speciesId}`} className="hover:text-nebula-400 transition-colors">
              {species.commonName}
            </Link>
            <span>/</span>
            <span className="text-nebula-400">{gene.geneId}</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-nebula-500/10">
              <Dna className="h-6 w-6 text-nebula-400" />
            </div>
            <div>
              <h1 className="font-mono text-xl font-bold text-space-100">
                {gene.geneId}
              </h1>
              <p className="text-sm text-space-500">
                {gene.symbol} &middot; {gene.chromosome}:{gene.start}-{gene.end} ({gene.strand} strand)
              </p>
            </div>
            <div className="ml-auto">
              <span className={`inline-flex items-center rounded-full px-3 py-1 font-mono text-xs font-medium ${
                gene.status === 'REVIEWED' ? 'bg-success-500/10 text-success-400' :
                gene.status === 'VALIDATED' ? 'bg-info-500/10 text-info-400' :
                gene.status === 'PROVISIONAL' ? 'bg-warning-500/10 text-warning-400' :
                gene.status === 'PREDICTED' ? 'bg-aurora-500/10 text-aurora-400' :
                'bg-space-600/20 text-space-400'
              }`}>
                {gene.status}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Content stub */}
      <div className="mx-auto max-w-[1400px] px-6 py-12 lg:px-12">
        <div className="rounded-2xl border border-space-700/50 bg-space-800/50 p-12 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-space-700 mx-auto mb-6">
            <FileText className="h-8 w-8 text-cyan-400" />
          </div>
          <h2 className="font-display text-xl font-semibold text-space-200 mb-2">
            Gene Detail Page
          </h2>
          <p className="text-space-500 mb-4 max-w-md mx-auto">
            {gene.description}
          </p>
          <div className="font-mono text-xs text-space-600 space-y-1">
            <p>Gene ID: {geneId}</p>
            <p>Species: {species.species} ({species.version})</p>
            <p>Location: {gene.chromosome}:{gene.start}-{gene.end}</p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
