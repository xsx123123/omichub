export type DatabaseStatus = 'connected' | 'disconnected' | 'error';

export interface SpeciesDB {
  id: string;
  species: string;
  commonName: string;
  version: string;
  status: DatabaseStatus;
  geneCount: number;
  sources: {
    fa: boolean;
    gff: boolean;
    go: boolean;
    kegg: boolean;
  };
  image: string;
  gradient: string;
  createdAt: string;
}

export interface Gene {
  geneId: string;
  symbol: string;
  chromosome: string;
  start: number;
  end: number;
  strand: '+' | '-';
  status: 'REVIEWED' | 'VALIDATED' | 'PROVISIONAL' | 'PREDICTED' | 'MODEL';
  description: string;
  speciesId: string;
  speciesName: string;
}

export interface GOTerm {
  id: string;
  name: string;
  namespace: 'BP' | 'MF' | 'CC';
  evidence: string;
}

export interface KEGGPathway {
  id: string;
  name: string;
  geneCount: number;
}

export interface Transcript {
  id: string;
  geneId: string;
  length: number;
  cdsStart: number;
  cdsEnd: number;
  exons: number;
}

export const speciesList: SpeciesDB[] = [
  {
    id: 'lettuce_v11',
    species: 'Lactuca sativa',
    commonName: 'Lettuce',
    version: 'v11',
    status: 'connected',
    geneCount: 45230,
    sources: { fa: true, gff: true, go: true, kegg: true },
    image: '/species-lettuce.jpg',
    gradient: 'linear-gradient(135deg, #10B981, #34D399)',
    createdAt: '2024-01-15',
  },
  {
    id: 'lettuce_v8',
    species: 'Lactuca sativa',
    commonName: 'Lettuce',
    version: 'v8',
    status: 'connected',
    geneCount: 38910,
    sources: { fa: true, gff: true, go: true, kegg: false },
    image: '/species-lettuce.jpg',
    gradient: 'linear-gradient(135deg, #10B981, #34D399)',
    createdAt: '2023-06-20',
  },
  {
    id: 'arabidopsis_tair10',
    species: 'Arabidopsis thaliana',
    commonName: 'Arabidopsis',
    version: 'TAIR10',
    status: 'connected',
    geneCount: 27416,
    sources: { fa: true, gff: true, go: true, kegg: true },
    image: '/species-arabidopsis.jpg',
    gradient: 'linear-gradient(135deg, #8B5CF6, #A78BFA)',
    createdAt: '2024-02-01',
  },
  {
    id: 'rice_irgsp1',
    species: 'Oryza sativa',
    commonName: 'Rice',
    version: 'IRGSP-1.0',
    status: 'connected',
    geneCount: 30600,
    sources: { fa: true, gff: true, go: true, kegg: true },
    image: '/species-rice.jpg',
    gradient: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
    createdAt: '2023-11-10',
  },
  {
    id: 'tomato_sl40',
    species: 'Solanum lycopersicum',
    commonName: 'Tomato',
    version: 'SL4.0',
    status: 'disconnected',
    geneCount: 34120,
    sources: { fa: true, gff: true, go: false, kegg: false },
    image: '/species-tomato.jpg',
    gradient: 'linear-gradient(135deg, #EF4444, #F87171)',
    createdAt: '2024-03-05',
  },
  {
    id: 'maize_b73',
    species: 'Zea mays',
    commonName: 'Maize',
    version: 'B73 RefGen_v5',
    status: 'error',
    geneCount: 39700,
    sources: { fa: true, gff: false, go: false, kegg: false },
    image: '/species-maize.jpg',
    gradient: 'linear-gradient(135deg, #F59E0B, #D97706)',
    createdAt: '2024-01-20',
  },
];

export const geneList: Gene[] = [
  {
    geneId: 'Lsat_1_v5_gn_1_104632',
    symbol: 'LSAT_001',
    chromosome: 'chr1',
    start: 104632,
    end: 105890,
    strand: '+',
    status: 'REVIEWED',
    description: 'Putative WRKY transcription factor 40, involved in stress response',
    speciesId: 'lettuce_v11',
    speciesName: 'Lactuca sativa',
  },
  {
    geneId: 'Lsat_1_v5_gn_2_208410',
    symbol: 'LSAT_002',
    chromosome: 'chr2',
    start: 208410,
    end: 209200,
    strand: '-',
    status: 'VALIDATED',
    description: 'Cytochrome P450 family protein, flavonoid biosynthesis',
    speciesId: 'lettuce_v11',
    speciesName: 'Lactuca sativa',
  },
  {
    geneId: 'Lsat_1_v5_gn_3_56201',
    symbol: 'LSAT_003',
    chromosome: 'chr3',
    start: 56201,
    end: 57890,
    strand: '+',
    status: 'REVIEWED',
    description: 'NBS-LRR resistance protein, downy mildew resistance',
    speciesId: 'lettuce_v11',
    speciesName: 'Lactuca sativa',
  },
  {
    geneId: 'Lsat_1_v5_gn_4_891200',
    symbol: 'LSAT_004',
    chromosome: 'chr4',
    start: 891200,
    end: 892500,
    strand: '+',
    status: 'PROVISIONAL',
    description: 'Expansin A1, cell wall loosening protein',
    speciesId: 'lettuce_v11',
    speciesName: 'Lactuca sativa',
  },
  {
    geneId: 'Lsat_1_v5_gn_5_1200340',
    symbol: 'LSAT_005',
    chromosome: 'chr5',
    start: 1200340,
    end: 1201500,
    strand: '-',
    status: 'REVIEWED',
    description: 'MADS-box transcription factor SOC1, flowering time regulation',
    speciesId: 'lettuce_v11',
    speciesName: 'Lactuca sativa',
  },
  {
    geneId: 'Lsat_1_v5_gn_6_450012',
    symbol: 'LSAT_006',
    chromosome: 'chr6',
    start: 450012,
    end: 451200,
    strand: '+',
    status: 'PREDICTED',
    description: 'Receptor-like protein kinase, defense signaling pathway',
    speciesId: 'lettuce_v11',
    speciesName: 'Lactuca sativa',
  },
  {
    geneId: 'Lsat_1_v5_gn_7_782300',
    symbol: 'LSAT_007',
    chromosome: 'chr7',
    start: 782300,
    end: 783900,
    strand: '-',
    status: 'VALIDATED',
    description: 'Sucrose synthase, carbohydrate metabolism',
    speciesId: 'lettuce_v11',
    speciesName: 'Lactuca sativa',
  },
  {
    geneId: 'Lsat_1_v5_gn_8_1560020',
    symbol: 'LSAT_008',
    chromosome: 'chr8',
    start: 1560020,
    end: 1561200,
    strand: '+',
    status: 'REVIEWED',
    description: 'MYB transcription factor, anthocyanin biosynthesis regulation',
    speciesId: 'lettuce_v11',
    speciesName: 'Lactuca sativa',
  },
  {
    geneId: 'AT1G01010',
    symbol: 'NAC001',
    chromosome: 'chr1',
    start: 3760,
    end: 5630,
    strand: '+',
    status: 'REVIEWED',
    description: 'NAC domain containing protein 1, developmental process',
    speciesId: 'arabidopsis_tair10',
    speciesName: 'Arabidopsis thaliana',
  },
  {
    geneId: 'AT1G01020',
    symbol: 'ARF18',
    chromosome: 'chr1',
    start: 6780,
    end: 8730,
    strand: '-',
    status: 'REVIEWED',
    description: 'Auxin response factor 18, hormone-mediated signaling',
    speciesId: 'arabidopsis_tair10',
    speciesName: 'Arabidopsis thaliana',
  },
  {
    geneId: 'AT2G03850',
    symbol: 'FT',
    chromosome: 'chr2',
    start: 28500,
    end: 29600,
    strand: '+',
    status: 'REVIEWED',
    description: 'FLOWERING LOCUS T, phosphatidylethanolamine binding protein',
    speciesId: 'arabidopsis_tair10',
    speciesName: 'Arabidopsis thaliana',
  },
  {
    geneId: 'Os01g0100100',
    symbol: 'OsMADS3',
    chromosome: 'chr1',
    start: 10230,
    end: 12100,
    strand: '+',
    status: 'VALIDATED',
    description: 'MADS-box transcription factor, floral organ identity',
    speciesId: 'rice_irgsp1',
    speciesName: 'Oryza sativa',
  },
  {
    geneId: 'Os02g0100500',
    symbol: 'OsDREB1A',
    chromosome: 'chr2',
    start: 45200,
    end: 46800,
    strand: '-',
    status: 'REVIEWED',
    description: 'Dehydration responsive element binding protein 1A',
    speciesId: 'rice_irgsp1',
    speciesName: 'Oryza sativa',
  },
  {
    geneId: 'SolydC1.2LG01g00560',
    symbol: 'SlPIN1',
    chromosome: 'chr1',
    start: 56200,
    end: 58900,
    strand: '+',
    status: 'PREDICTED',
    description: 'PIN-FORMED auxin efflux carrier, polar auxin transport',
    speciesId: 'tomato_sl40',
    speciesName: 'Solanum lycopersicum',
  },
  {
    geneId: 'Zm00001eb000010',
    symbol: 'ZmTB1',
    chromosome: 'chr1',
    start: 15230,
    end: 17800,
    strand: '+',
    status: 'PROVISIONAL',
    description: 'Teosinte branched 1, TCP transcription factor',
    speciesId: 'maize_b73',
    speciesName: 'Zea mays',
  },
];

export const goTerms: GOTerm[] = [
  { id: 'GO:0006355', name: 'regulation of transcription, DNA-templated', namespace: 'BP', evidence: 'IDA' },
  { id: 'GO:0006950', name: 'response to stress', namespace: 'BP', evidence: 'IEP' },
  { id: 'GO:0005515', name: 'protein binding', namespace: 'MF', evidence: 'IPI' },
  { id: 'GO:0003677', name: 'DNA binding', namespace: 'MF', evidence: 'IDA' },
  { id: 'GO:0005634', name: 'nucleus', namespace: 'CC', evidence: 'IDA' },
  { id: 'GO:0005829', name: 'cytosol', namespace: 'CC', evidence: 'IDA' },
  { id: 'GO:0009737', name: 'response to abscisic acid', namespace: 'BP', evidence: 'IEP' },
  { id: 'GO:0016301', name: 'kinase activity', namespace: 'MF', evidence: 'IDA' },
  { id: 'GO:0009507', name: 'chloroplast', namespace: 'CC', evidence: 'IDA' },
  { id: 'GO:0009877', name: 'signal transduction', namespace: 'BP', evidence: 'IMP' },
];

export const keggPathways: KEGGPathway[] = [
  { id: 'ko04075', name: 'Plant hormone signal transduction', geneCount: 156 },
  { id: 'ko00940', name: 'Phenylpropanoid biosynthesis', geneCount: 89 },
  { id: 'ko01100', name: 'Metabolic pathways', geneCount: 3420 },
  { id: 'ko04016', name: 'MAPK signaling pathway - plant', geneCount: 234 },
  { id: 'ko00941', name: 'Flavonoid biosynthesis', geneCount: 67 },
  { id: 'ko00195', name: 'Photosynthesis', geneCount: 145 },
  { id: 'ko03013', name: 'RNA transport', geneCount: 198 },
  { id: 'ko04141', name: 'Protein processing in endoplasmic reticulum', geneCount: 112 },
];

export const transcripts: Transcript[] = [
  { id: 'Lsat_1_v5_gn_1_104632.1', geneId: 'Lsat_1_v5_gn_1_104632', length: 1258, cdsStart: 45, cdsEnd: 1089, exons: 3 },
  { id: 'Lsat_1_v5_gn_1_104632.2', geneId: 'Lsat_1_v5_gn_1_104632', length: 980, cdsStart: 32, cdsEnd: 856, exons: 2 },
  { id: 'Lsat_1_v5_gn_2_208410.1', geneId: 'Lsat_1_v5_gn_2_208410', length: 1567, cdsStart: 78, cdsEnd: 1420, exons: 4 },
];

export const statsOverview = {
  totalDatabases: speciesList.length,
  totalGenes: speciesList.reduce((acc, s) => acc + s.geneCount, 0),
  totalSpecies: new Set(speciesList.map(s => s.species)).size,
  connected: speciesList.filter(s => s.status === 'connected').length,
};

export function searchGenes(query: string): Gene[] {
  const q = query.toLowerCase();
  return geneList.filter(
    g =>
      g.geneId.toLowerCase().includes(q) ||
      g.symbol.toLowerCase().includes(q) ||
      g.description.toLowerCase().includes(q)
  );
}

export function searchSpecies(query: string): SpeciesDB[] {
  const q = query.toLowerCase();
  return speciesList.filter(
    s =>
      s.species.toLowerCase().includes(q) ||
      s.commonName.toLowerCase().includes(q) ||
      s.version.toLowerCase().includes(q)
  );
}

export function getSpeciesById(id: string): SpeciesDB | undefined {
  return speciesList.find(s => s.id === id);
}

export function getGenesBySpeciesId(speciesId: string): Gene[] {
  return geneList.filter(g => g.speciesId === speciesId);
}

export function getGeneById(geneId: string): Gene | undefined {
  return geneList.find(g => g.geneId === geneId);
}
