import { safeSourceUrl } from './researchPresentation'
import { reactive, watch, type Ref } from 'vue'
import { agentToolsApi } from '@/api/agentTools'
import { datasetsApi } from '@/api/datasets'
import { researchFailure, type ResearchSession } from '@/api/researchAgent'
import type { ResearchActionV1, ResearchWorkflowView } from '@/types/treasureIsland'

type Row = Record<string, unknown>
const row = (value: unknown): Row => value && typeof value === 'object' && !Array.isArray(value) ? value as Row : {}
const rows = (value: unknown): Row[] => Array.isArray(value) ? value.map(row) : []
const str = (value: unknown): string => typeof value === 'string' ? value : ''
const list = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
function empty(projectSelected = false): ResearchWorkflowView {
  return { open: false, busy: false, projectSelected, gaps: [], samples: [], relations: [], files: [], datasets: [], assets: [], workflows: [], proposals: [], tasks: [], reports: [], deliveryStatus: 'UNKNOWN', sources: [], allowedTools: [], downloadCapabilities: [], catalogStatus: 'UNKNOWN' }
}
/** Vue owns network/identity and discards late results across sessions, projects and actions. */
export function useResearchWorkflow(session: Ref<ResearchSession | null>) {
  const view = reactive<ResearchWorkflowView>(empty())
  let generation = 0
  const proposalVersions = new Map<string, { dataset: string; version: string }>()
  const sharedProposals = new Map<string, 'downloads.prepare' | 'analysis.prepare'>()
  watch(() => [session.value?.session_id, session.value?.project_id], () => { ++generation; Object.assign(view, empty(!!session.value?.project_id), { accession: undefined, versionId: undefined, datasetId: undefined, manifestHash: undefined, error: undefined, status: undefined }); proposalVersions.clear(); sharedProposals.clear() }, { flush: 'sync' })
  function proposal(value: unknown, kind: 'import' | 'analysis') {
    const item = row(value), preview = row(item.preview)
    const id = str(kind === 'import' ? item.ingestion_id : item.analysis_proposal_id)
    if (!id) return
    const details = Object.entries({ accession: preview.accession, mode: preview.mode, max_bytes: preview.max_bytes, expected_bytes: preview.expected_bytes ?? 'UNKNOWN', flow: item.flow_id ?? preview.flow_id })
      .filter(([, value]) => typeof value === 'string' || typeof value === 'number')
      .filter(([key]) => !/path|directory|token|secret/i.test(key))
      .map(([label, value]) => ({ label, value: String(value) }))
    if (Array.isArray(preview.selected)) details.push(...rows(preview.selected).map(selected => ({ label: 'file/run', value: str(selected.run_accession) || str(selected.original_name) })))
    view.proposals = [...view.proposals.filter(p => p.id !== id), { id, kind, state: str(item.state) || 'PREPARED', hash: str(item.parameters_hash), expires: str(item.expires_at), details }]
  }
  async function action(intent: ResearchActionV1, background = false): Promise<void> {
    if (intent.type === 'workflow.close') { ++generation; view.open = false; view.busy = false; return }
    const current = session.value
    if (!current) return
    if (intent.type === 'task.open' || intent.type === 'report.open') {
      if (!/^[0-9a-f-]{36}$/i.test(intent.type === 'task.open' ? intent.taskId : intent.reportId)) return
      window.location.assign(intent.type === 'task.open' ? `/tasks/${encodeURIComponent(intent.taskId)}` : `/reports?reportId=${encodeURIComponent(intent.reportId)}`)
      return
    }
    // Persistent prepare/decision calls are never automatically replayed.
    if (view.busy && !['dataset.inspect','dataset.list','dataset.version','records.refresh'].includes(intent.type)) return
    const snapshot = ++generation
    view.open = !background; view.busy = true; view.error = ''; view.projectSelected = !!current.project_id
    const projectId = current.project_id
    const valid = () => snapshot === generation && current.session_id === session.value?.session_id && projectId === session.value?.project_id
    const invoke = async (capability: string, args: Row = {}) => {
      if (!valid() || !view.allowedTools?.includes(capability)) throw { response: { status: 403 } }
      return (await agentToolsApi.invoke(current.session_id, capability, args)).result
    }
    try {
      // Refresh authorization for every action; historical cards are never permissions.
      const catalog = await agentToolsApi.capabilities(current.session_id)
      if (!valid()) return
      const allowedTools = catalog.tools.map(tool => tool.capability_id)
      if (view.allowedTools?.some(tool => !allowedTools.includes(tool))) {
        Object.assign(view, empty(!!current.project_id), {
          open: !background, busy: true, accession: undefined, versionId: undefined,
          datasetId: undefined, manifestHash: undefined, status: undefined, error: '',
        })
        proposalVersions.clear()
        sharedProposals.clear()
      }
      view.allowedTools = allowedTools
      view.catalogStatus = allowedTools.length ? 'AVAILABLE' : 'UNAVAILABLE'
      if (view.allowedTools.includes('downloads.describe_capabilities')) {
        const description = row(await invoke('downloads.describe_capabilities'))
        if (!valid()) return
        view.downloadCapabilities = rows(description.capabilities).map(item => ({
          source: str(item.source_type), states: list(item.states), reasons: list(item.limitations),
          // A UI projection cannot grant execution, even if a malformed response says true.
          executionAllowed: false as const,
        }))
      } else { view.downloadCapabilities = [] }
      if (intent.type === 'capabilities.refresh') return
      if (intent.type === 'dataset.inspect') {
        Object.assign(view, { open: true, busy: true, accession: intent.discoveryRef, datasetId: undefined, versionId: undefined, manifestHash: undefined, files: [], sources: [], samples: [], gaps: [], assets: [] })
        const result = row(await invoke('dataset.discover', { accession: intent.discoveryRef }))
        if (!valid()) return
        view.accession = str(result.primary_accession) || intent.discoveryRef
        view.status = str(result.status)
        view.sources = rows(result.source_evidence).flatMap(source => { const url = safeSourceUrl(source.url); return url ? [{ url, digest: str(source.response_sha256) }] : [] })
        view.gaps = [...list(result.confidence_flags), ...list(result.limitations)]
        if (result.error_code) view.gaps.push(str(result.error_code))
        view.samples = rows(result.samples).map((sample, index) => ({ id: str(sample.sample_key) || str(sample.accession) || str(sample.sample_accession) || String(index + 1), summary: [sample.title, sample.organism, sample.characteristics, sample.processing].flat().filter(value => typeof value === 'string').join(' · ') }))
        view.relations = rows(result.related_accessions).map(edge => ({ from: str(edge.from), to: str(edge.to), relation: str(edge.relation) }))
        view.files = [
          ...rows(result.runs).map(run => ({ id: str(run.run_accession), label: [run.run_accession, run.experiment_accession, run.sample_accession, run.library_layout].filter(Boolean).join(' · '), mode: 'raw' as const, size: rows(run.files).length && rows(run.files).every(file => typeof file.size === 'number') ? rows(run.files).reduce((sum, file) => sum + Number(file.size), 0) : null })),
          ...rows(result.files).map(file => ({ id: str(file.url), label: str(file.original_name), mode: 'processed' as const, size: typeof file.size === 'number' ? file.size : null })),
        ]
      } else if (intent.type === 'dataset.prepare_import') {
        if (!current.project_id) throw { response: { status: 422 } }
        const result = await invoke('dataset.prepare_import', { request: { accession: intent.discoveryRef, mode: intent.mode, selected_ids: intent.selectedIds, max_bytes: intent.maxBytes, request_key: intent.requestKey, name: intent.discoveryRef } })
        if (!valid()) return
        proposal(result, 'import')
        if (!row(result).ingestion_id) view.error = str(row(result).error_code) || 'SOURCE_UNAVAILABLE'
      } else if (intent.type === 'dataset.list') {
        if (!current.project_id) return
        const result = rows(await invoke('dataset.list_project_assets'))
        if (!valid()) return
        Object.assign(view, { accession: undefined, versionId: undefined, datasetId: undefined, files: [], samples: [], relations: [], gaps: [], assets: [], workflows: [] })
        view.datasets = result.map(item => ({ id: str(item.id), name: str(item.name), versions: rows(item.versions).map(version => ({ id: str(version.version_id), label: `v${version.number} · ${version.status}` })) }))
        view.gaps = ['VERSION_LIST_BOUNDED_NOT_COMPLETE_HISTORY']
      } else if (intent.type === 'dataset.version') {
        const args = { dataset_id: intent.datasetId, version_id: intent.versionId }
        const manifest = row(await invoke('dataset.inspect', args))
        if (!valid()) return
        const compatible = view.allowedTools.includes('analysis.list_compatible_workflows') ? row(await invoke('analysis.list_compatible_workflows', args)) : {}
        if (!valid()) return
        view.datasetId = intent.datasetId; view.versionId = intent.versionId; view.accession = undefined
        view.manifestHash = manifest.handoff_frozen === true ? str(manifest.manifest_hash) : ''
        view.gaps = [...(manifest.handoff_frozen === true ? [] : ['HANDOFF_NOT_FROZEN']), ...list(row(manifest.validation).blocking_reasons), ...(row(manifest.validation).worker_paths_verified ? [] : ['WORKER_PATHS_NOT_VERIFIED'])]
        view.assets = rows(manifest.assets).map(asset => ({ id: str(asset.asset_id), type: str(asset.data_type), size: Number(asset.size) || 0, checksum: str(asset.sha256) || 'UNKNOWN', availability: str(asset.availability), fileRecordId: str(asset.file_record_id), role: str(asset.asset_role), checksumStatus: str(asset.checksum_status) }))
        view.workflows = rows(compatible.workflows).map(flow => ({ id: str(flow.flow_id), label: str(flow.name) || str(flow.flow_id) }))
      } else if (intent.type === 'analysis.prepare') {
        const parameters = intent.flowId === 'counts_deg' ? { ...intent.parameters, reference: intent.reference, treatment: intent.treatment } : intent.parameters
        const options = intent.flowId === 'rna_seq' ? { parameters, comparisons: [{ Control: intent.reference, Treat: intent.treatment }] } : { parameters }
        const result = row(await invoke('analysis.prepare_from_dataset', { dataset_id: intent.datasetId, version_id: intent.versionId, request: { flow_id: intent.flowId, options } }))
        if (!valid()) return
        proposal(result, 'analysis')
        if (result.analysis_proposal_id) proposalVersions.set(str(result.analysis_proposal_id), { dataset: intent.datasetId, version: intent.versionId })
        else view.error = [str(result.error_code), ...list(result.missing_fields), ...list(row(result.validation).blocking_reasons)].filter(Boolean).join(' · ') || 'INPUT_REVIEW_REQUIRED'
      } else if (intent.type === 'records.refresh') {
        if (!view.allowedTools.includes('tasks.list_related')) throw { response: { status: 403 } }
        const links = await agentToolsApi.related(current.session_id)
        if (!valid()) return
        view.proposals = []; view.tasks = []
        proposalVersions.clear(); sharedProposals.clear()
        for (const link of links) {
          const capability = link.capability_id
          const shared = link.proposal
          if (shared && (capability === 'downloads.prepare' || capability === 'analysis.prepare')
            && view.allowedTools.includes(capability)
            && shared.conversation_id === current.session_id && shared.project_id === (current.project_id || null)
            && shared.operation === (capability === 'downloads.prepare' ? 'downloads.submit' : 'analysis.submit')) {
            // The durable Gateway record determines both identity and approval
            // route; model output and UI kind cannot choose the endpoint.
            const details = Object.entries(row(shared.preview))
              .filter(([key]) => ['operation', 'accession', 'flow_id', 'flow_name', 'sample_count', 'comparison_count', 'bytes_estimate'].includes(key))
              .filter(([, value]) => typeof value === 'string' || typeof value === 'number')
              .map(([label, value]) => ({ label, value: String(value) }))
            view.proposals.push({ id: shared.proposal_id, kind: capability === 'downloads.prepare' ? 'import' : 'analysis',
              capabilityId: capability, state: shared.state, hash: shared.parameters_hash, expires: shared.expires_at, details })
            sharedProposals.set(shared.proposal_id, capability)
          }
          if (link.dataset_import) {
            proposal(link.dataset_import, 'import')
            for (const task of link.dataset_import.tasks ?? []) view.tasks.push({ id: task.task_id, status: task.status })
          }
          if (link.dataset_analysis) {
            proposal(link.dataset_analysis, 'analysis')
            const info = row(link.dataset_analysis)
            if (info.task_id) view.tasks.push({ id: str(info.task_id), status: str(info.state) || 'UNKNOWN' })
            if (info.dataset_id && info.dataset_version_id) proposalVersions.set(str(info.analysis_proposal_id), { dataset: str(info.dataset_id), version: str(info.dataset_version_id) })
          }
          if (link.task) view.tasks.push({ id: link.task.task_id, status: link.task.status })
        }
        const ids = [...new Set(view.tasks.map(task => task.id))]
        view.tasks = []
        if (view.allowedTools.includes('tasks.get_status')) {
          const statuses = await Promise.all(ids.map(async id => {
            try { const result = row(await invoke('tasks.get_status', { task_id: id })); return { id, status: str(result.status) || 'UNKNOWN' } }
            catch { return { id, status: 'UNAVAILABLE' } }
          }))
          if (!valid()) return
          view.tasks = statuses
        }
      } else if (intent.type === 'delivery.read') {
        if (!current.project_id) return
        const result = row(await invoke('research.project_delivery'))
        if (!valid()) return
        view.reports = []; view.tasks = []; view.deliveryStatus = 'NOT_GENERATED'
        for (const dataset of rows(result.datasets)) for (const graph of rows(dataset.analyses)) {
          const taskId = str(graph.task_id)
          if (taskId) view.tasks.push({ id: taskId, status: str(graph.compute_state) || 'UNKNOWN' })
          view.gaps = [...new Set([...view.gaps, ...list(graph.gaps)])]
          for (const report of rows(graph.reports)) {
            const id = str(report.report_id)
            if (id) view.reports.push({ id, kind: str(report.kind), state: str(report.state), integrity: str(report.integrity) })
          }
        }
        if (view.reports.length) view.deliveryStatus = 'RECORDED_REFERENCES'
      } else if (intent.type === 'proposal.decide') {
        if (!current.project_id) return
        const displayed = view.proposals.find(item => item.id === intent.proposalId && item.kind === intent.kind)
        if (!displayed) { view.error = 'REOPEN_PROPOSAL_REQUIRED'; return }
        const sharedCapability = sharedProposals.get(intent.proposalId)
        const capability = sharedCapability || (intent.kind === 'import' ? 'dataset.prepare_import' : 'analysis.prepare_from_dataset')
        if (!view.allowedTools.includes(capability)) throw { response: { status: 403 } }
        if (sharedCapability) {
          if (!['PENDING', 'pending', 'PREPARED'].includes(displayed.state)) return
          const expires = Date.parse(displayed.expires)
          if (!Number.isFinite(expires) || expires <= Date.now()) { view.error = 'CONFIRMATION_EXPIRED'; return }
          const result = await agentToolsApi.decide(current.session_id, intent.proposalId, intent.approve)
          if (valid()) view.proposals = view.proposals.map(item => item.id === intent.proposalId ? { ...item, state: result.state } : item)
        } else if (intent.kind === 'import') {
          const result = await datasetsApi.decide(current.project_id, intent.proposalId, intent.approve)
          if (valid()) proposal(result, 'import')
        } else {
          const binding = proposalVersions.get(intent.proposalId)
          if (!binding) { view.error = 'REOPEN_DATASET_VERSION_REQUIRED'; return }
          const result = await datasetsApi.decideAnalysis(current.project_id, binding.dataset, binding.version, intent.proposalId, intent.approve)
          if (valid()) view.proposals = view.proposals.map(item => item.id === intent.proposalId ? { ...item, state: str(row(result).state) } : item)
        }
      }
    } catch (error) {
      if (valid()) {
        // A failed authorization refresh invalidates every prior research projection.
        // Keep the panel visible so the failure remains actionable.
        Object.assign(view, empty(!!current.project_id), {
          open: !background, accession: undefined, versionId: undefined,
          datasetId: undefined, manifestHash: undefined, status: undefined,
          error: researchFailure(error), catalogStatus: 'UNAVAILABLE',
        })
        proposalVersions.clear()
        sharedProposals.clear()
      }
    }
    finally { if (valid()) view.busy = false }
  }
  return { view, action }
}
