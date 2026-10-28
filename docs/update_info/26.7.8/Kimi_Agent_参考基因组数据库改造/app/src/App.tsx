import { Routes, Route } from 'react-router'
import Layout from './components/Layout'
import DatabaseHub from './pages/DatabaseHub'
import DatabaseBrowser from './pages/DatabaseBrowser'
import GeneDetail from './pages/GeneDetail'
import DatabaseAdmin from './pages/DatabaseAdmin'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DatabaseHub />} />
        <Route path="/database" element={<DatabaseHub />} />
        <Route path="/database/:speciesId" element={<DatabaseBrowser />} />
        <Route path="/database/:speciesId/gene/:geneId" element={<GeneDetail />} />
        <Route path="/database/admin" element={<DatabaseAdmin />} />
      </Routes>
    </Layout>
  )
}
