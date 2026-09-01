import type {
  AIConfigInput,
  AIConfigList,
  AIConfigView,
  AIConnectionTestResponse,
  AIExplanationResponse,
  DemandForecast,
  DispatchPlanList,
  DispatchPlanView,
  DriverAssignmentList,
  ExperimentList,
  ExperimentView,
  OptimizeResult,
  RunListResponse,
  RoutingStatus,
  CurrentWeather,
  Scenario,
  ScenarioSpatialStatus,
  ScenarioImportResponse,
  ScenarioCompareResponse,
  ScenarioVersionDetail,
  ScenarioVersionList,
  ScenarioVersionView,
  TokenResponse,
  RegisterInput,
  CurrentUser,
  ManagedUser,
  ManagedUserList,
  UserCreateInput,
  UserUpdateInput,
  AuditLogList,
  MasterDataSummary,
  DataImportBatch,
  DataImportBatchList,
  DataQualityReport,
  DataQualityRule,
  MasterDataPublishResponse,
  MasterNode,
  MasterNodeCreate,
  MasterNodeInput,
  MasterNodeList,
  NodeCoordinateInput,
  NodeCoordinateRevisionList,
  SpatialQualitySummary,
  MasterOrder,
  MasterOrderCreate,
  MasterOrderInput,
  MasterOrderList,
  MasterVehicle,
  MasterVehicleCreate,
  MasterVehicleInput,
  MasterVehicleList,
  QidongReferenceSummary,
  OperationsReadiness,
  MapConfigInput,
  MapConfigList,
  MapConfigView,
  MapRuntimeConfig,
  OrderRequest,
  OrderRequestList,
  OrderRequestNodeOption,
} from '../types/logistics'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000/api/v1'
const TOKEN_KEY = 'qizhi_access_token'
const ROLE_KEY = 'qizhi_session_role'
const USER_KEY = 'qizhi_session_user'

const sessionStores = [sessionStorage, localStorage]
const storedValue = (key: string) =>
  sessionStores.map(store => store.getItem(key)).find(value => Boolean(value)) ?? ''
const clearStoredSession = () => {
  sessionStores.forEach((store) => {
    store.removeItem(TOKEN_KEY)
    store.removeItem(ROLE_KEY)
    store.removeItem(USER_KEY)
  })
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    let message = `接口请求失败（${response.status}）`
    try {
      const body = await response.json() as {
        detail?: string | Array<string | { msg?: string }>
      }
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) {
        message = body.detail
          .map(item => typeof item === 'string' ? item : item.msg)
          .filter(Boolean)
          .join('；') || message
      }
    } catch {
      // Keep the HTTP status when a proxy returns a non-JSON error page.
    }
    if (response.status === 401 && path !== '/auth/login') {
      clearStoredSession()
      window.dispatchEvent(new CustomEvent('qizhi-session-expired'))
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

async function authenticatedRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = storedValue(TOKEN_KEY)
  if (!token) throw new Error('请先登录')
  return request<T>(path, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      Authorization: `Bearer ${token}`,
      ...init?.headers,
    },
  })
}

export const hasAdminSession = () =>
  Boolean(storedValue(TOKEN_KEY)) && storedValue(ROLE_KEY) === 'admin'
export const hasSession = () => Boolean(storedValue(TOKEN_KEY))
export const getSessionRole = () => storedValue(ROLE_KEY)
export const getSessionUser = () => storedValue(USER_KEY)
export const clearAdminSession = clearStoredSession
export async function login(username: string, password: string, remember = false) {
  const response = await request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  clearStoredSession()
  const store = remember ? localStorage : sessionStorage
  store.setItem(TOKEN_KEY, response.access_token)
  store.setItem(ROLE_KEY, response.role)
  store.setItem(USER_KEY, response.display_name || response.username)
  return response
}
export async function register(input: RegisterInput, remember = false) {
  const response = await request<TokenResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(input),
  })
  clearStoredSession()
  const store = remember ? localStorage : sessionStorage
  store.setItem(TOKEN_KEY, response.access_token)
  store.setItem(ROLE_KEY, response.role)
  store.setItem(USER_KEY, response.display_name || response.username)
  return response
}
export const getCurrentUser = () => authenticatedRequest<CurrentUser>('/auth/me')
export async function logout() {
  try {
    await authenticatedRequest<void>('/auth/logout', { method: 'POST' })
  } finally {
    clearStoredSession()
  }
}

export const getOrderRequestOptions = () =>
  authenticatedRequest<{ items: OrderRequestNodeOption[] }>('/order-requests/options')
export const createOrderRequest = (input: {
  node_id: string
  cargo_name: string
  customer_name: string
  customer_phone?: string
  delivery_address?: string
  weight_kg: number
  window_start: number
  window_end: number
  service_minutes: number
  cold_chain: boolean
  priority: 'normal' | 'urgent'
  flow_direction: 'upward' | 'downward'
  cargo_category: 'agricultural' | 'industrial'
  origin_node_id?: string
  destination_node_id?: string
}) =>
  authenticatedRequest<OrderRequest>('/order-requests', {
    method: 'POST',
    body: JSON.stringify(input),
  })
export const getMyOrderRequests = () =>
  authenticatedRequest<OrderRequestList>('/order-requests/mine?limit=50')
export const getOrderRequests = (status = '') =>
  authenticatedRequest<OrderRequestList>(
    `/order-requests?limit=100${status ? `&status=${encodeURIComponent(status)}` : ''}`,
  )
export const reviewOrderRequest = (
  id: number,
  action: 'approve' | 'reject' | 'needs_info',
  note?: string,
) =>
  authenticatedRequest<OrderRequest>(`/order-requests/${id}/review`, {
    method: 'POST',
    body: JSON.stringify({ action, note }),
  })
export const cancelOrderRequest = (id: number) =>
  authenticatedRequest<OrderRequest>(`/order-requests/${id}/cancel`, {
    method: 'POST',
  })

export const getUsers = (params = '') =>
  authenticatedRequest<ManagedUserList>(`/users${params ? `?${params}` : ''}`)
export const createUser = (input: UserCreateInput) =>
  authenticatedRequest<ManagedUser>('/users', {
    method: 'POST',
    body: JSON.stringify(input),
  })
export const updateUser = (id: number, input: UserUpdateInput) =>
  authenticatedRequest<ManagedUser>(`/users/${id}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
export const resetUserPassword = (id: number, password: string) =>
  authenticatedRequest<void>(`/users/${id}/reset-password`, {
    method: 'POST',
    body: JSON.stringify({ password }),
  })
export const getAuditLogs = (params = '') =>
  authenticatedRequest<AuditLogList>(`/audit-logs${params ? `?${params}` : ''}`)
export async function downloadAuditLogs(params = '') {
  const token = storedValue(TOKEN_KEY)
  if (!token) throw new Error('请先登录')
  const response = await fetch(
    `${API_BASE}/audit-logs/export${params ? `?${params}` : ''}`,
    { headers: { Authorization: `Bearer ${token}` } },
  )
  if (!response.ok) throw new Error(`审计日志导出失败（${response.status}）`)
  return response.blob()
}

export const getMasterDataSummary = () =>
  authenticatedRequest<MasterDataSummary>('/master-data/summary')

export const getQidongReferenceSummary = () =>
  authenticatedRequest<QidongReferenceSummary>('/reference/qidong-summary')

export const getMasterOrders = (params = '') =>
  authenticatedRequest<MasterOrderList>(`/master-data/orders${params ? `?${params}` : ''}`)
export const createMasterOrder = (input: MasterOrderCreate) =>
  authenticatedRequest<MasterOrder>('/master-data/orders', {
    method: 'POST',
    body: JSON.stringify(input),
  })
export const updateMasterOrder = (id: string, input: MasterOrderInput) =>
  authenticatedRequest<MasterOrder>(`/master-data/orders/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
export const deleteMasterOrder = (id: string) =>
  authenticatedRequest<void>(`/master-data/orders/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })

export async function downloadOrderImportTemplate() {
  const token = storedValue(TOKEN_KEY)
  if (!token) throw new Error('请先登录')
  const response = await fetch(`${API_BASE}/master-data/orders/import/template`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error(`模板下载失败（${response.status}）`)
  return response.blob()
}
export const previewOrderImport = (file: File) => {
  const body = new FormData()
  body.append('file', file)
  return authenticatedRequest<DataImportBatch>('/master-data/orders/import/preview', {
    method: 'POST',
    body,
  })
}
export const getDataImportBatches = () =>
  authenticatedRequest<DataImportBatchList>('/master-data/imports?limit=10')
export const commitDataImportBatch = (id: number) =>
  authenticatedRequest<DataImportBatch>(`/master-data/imports/${id}/commit`, {
    method: 'POST',
  })
export async function downloadDataImportErrors(id: number) {
  const token = storedValue(TOKEN_KEY)
  if (!token) throw new Error('请先登录')
  const response = await fetch(`${API_BASE}/master-data/imports/${id}/errors`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error(`错误回执下载失败（${response.status}）`)
  return response.blob()
}
export const getDataQualityReport = () =>
  authenticatedRequest<DataQualityReport>('/master-data/quality-report')
export const updateDataQualityRule = (
  id: number,
  input: { enabled: boolean; severity: 'error' | 'warning' },
) =>
  authenticatedRequest<DataQualityRule>(`/master-data/quality-rules/${id}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
export const publishMasterData = (name: string, activate: boolean) =>
  authenticatedRequest<MasterDataPublishResponse>('/master-data/publish', {
    method: 'POST',
    body: JSON.stringify({ name, activate }),
  })

export const getMasterVehicles = (params = '') =>
  authenticatedRequest<MasterVehicleList>(`/master-data/vehicles${params ? `?${params}` : ''}`)
export const createMasterVehicle = (input: MasterVehicleCreate) =>
  authenticatedRequest<MasterVehicle>('/master-data/vehicles', {
    method: 'POST',
    body: JSON.stringify(input),
  })
export const updateMasterVehicle = (id: string, input: MasterVehicleInput) =>
  authenticatedRequest<MasterVehicle>(`/master-data/vehicles/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
export const deleteMasterVehicle = (id: string) =>
  authenticatedRequest<void>(`/master-data/vehicles/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })

export const getMasterNodes = (params = '') =>
  authenticatedRequest<MasterNodeList>(`/master-data/nodes${params ? `?${params}` : ''}`)
export const createMasterNode = (input: MasterNodeCreate) =>
  authenticatedRequest<MasterNode>('/master-data/nodes', {
    method: 'POST',
    body: JSON.stringify(input),
  })
export const updateMasterNode = (id: string, input: MasterNodeInput) =>
  authenticatedRequest<MasterNode>(`/master-data/nodes/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
export const deleteMasterNode = (id: string) =>
  authenticatedRequest<void>(`/master-data/nodes/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
export const getSpatialQuality = () =>
  authenticatedRequest<SpatialQualitySummary>('/master-data/spatial-quality')
export const getNodeCoordinateRevisions = (id: string) =>
  authenticatedRequest<NodeCoordinateRevisionList>(
    `/master-data/nodes/${encodeURIComponent(id)}/coordinate-revisions`,
  )
export const calibrateNodeCoordinate = (id: string, input: NodeCoordinateInput) =>
  authenticatedRequest<MasterNode>(
    `/master-data/nodes/${encodeURIComponent(id)}/coordinate`,
    { method: 'PUT', body: JSON.stringify(input) },
  )

export const getScenario = (profile: 'standard-v1' | 'bidirectional-v2' = 'bidirectional-v2') =>
  authenticatedRequest<Scenario>(
    profile === 'bidirectional-v2'
      ? '/scenario?scenario_id=qidong-bidirectional-v2'
      : '/scenario',
  )
export const getScenarioSpatialStatus = (
  profile: 'standard-v1' | 'bidirectional-v2' = 'bidirectional-v2',
) =>
  authenticatedRequest<ScenarioSpatialStatus>(
    profile === 'bidirectional-v2'
      ? '/scenario/spatial-status?scenario_id=qidong-bidirectional-v2'
      : '/scenario/spatial-status',
  )
export const getDemandForecast = (days = 7) =>
  authenticatedRequest<DemandForecast>(`/analytics/forecast?days=${days}`)
export const getRoutingStatus = () => authenticatedRequest<RoutingStatus>('/routing/status')
export const getCurrentWeather = () => authenticatedRequest<CurrentWeather>('/weather/current')
export const optimizeScenario = (profile: 'standard-v1' | 'bidirectional-v2' = 'bidirectional-v2') =>
  authenticatedRequest<OptimizeResult>('/optimize', {
    method: 'POST',
    body: JSON.stringify({
      profile,
      strategy: 'balanced',
      ai_assisted: true,
      candidate_count: 1,
      time_limit_seconds: 5,
    }),
  })
export const reoptimizeScenario = (profile: 'standard-v1' | 'bidirectional-v2' = 'bidirectional-v2') =>
  authenticatedRequest<OptimizeResult>('/events/reoptimize', {
    method: 'POST',
    body: JSON.stringify({
      profile,
      event: {
        type: 'vehicle_breakdown',
        vehicle_id: 'V-COLD-01',
        occurred_at_minute: 90,
        node_id: profile === 'bidirectional-v2' ? 'V-007' : 'V-SHANGYI',
        longitude: profile === 'bidirectional-v2' ? 111.937461 : 111.842611,
        latitude: profile === 'bidirectional-v2' ? 26.776843 : 26.826567,
        location_name: profile === 'bidirectional-v2' ? '城连圩乡永隆村服务站' : '尚义村',
      },
      lock_completed: true,
      urgent_orders: ['O-URGENT-01'],
      ai_assisted: true,
      candidate_count: 1,
    }),
  })
export const getRunHistory = () => authenticatedRequest<RunListResponse>('/runs?limit=50')
export const getLatestRun = (scenarioId: string) =>
  authenticatedRequest<OptimizeResult | null>(
    `/runs/latest?scenario_id=${encodeURIComponent(scenarioId)}`,
  )
export const getAIConfig = () => authenticatedRequest<AIConfigView | null>('/ai/config')
export const saveAIConfig = (config: AIConfigInput) =>
  authenticatedRequest<AIConfigView>('/ai/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  })
export const testAIConfig = () =>
  authenticatedRequest<AIConnectionTestResponse>('/ai/config/test', { method: 'POST' })
export const getAIConfigs = () => authenticatedRequest<AIConfigList>('/ai/configs')
export const createAIConfig = (config: AIConfigInput) =>
  authenticatedRequest<AIConfigView>('/ai/configs', {
    method: 'POST',
    body: JSON.stringify(config),
  })
export const updateAIConfig = (id: number, config: AIConfigInput) =>
  authenticatedRequest<AIConfigView>(`/ai/configs/${id}`, {
    method: 'PUT',
    body: JSON.stringify(config),
  })
export const testAIConfigById = (id: number) =>
  authenticatedRequest<AIConnectionTestResponse>(`/ai/configs/${id}/test`, {
    method: 'POST',
  })
export const activateAIConfig = (id: number) =>
  authenticatedRequest<AIConfigView>(`/ai/configs/${id}/activate`, { method: 'POST' })
export const disableAIConfig = (id: number) =>
  authenticatedRequest<AIConfigView>(`/ai/configs/${id}/disable`, { method: 'POST' })
export const explainRun = (runId: string) =>
  authenticatedRequest<AIExplanationResponse>(`/ai/explain/${encodeURIComponent(runId)}`, {
    method: 'POST',
  })
export const getScenarioVersions = (params: { search?: string; status?: string } = {}) => {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.status) query.set('status', params.status)
  const suffix = query.size ? `?${query}` : ''
  return authenticatedRequest<ScenarioVersionList>(`/scenarios${suffix}`)
}
export const getScenarioVersionDetail = (scenarioId: number) =>
  authenticatedRequest<ScenarioVersionDetail>(`/scenarios/${scenarioId}`)
export const compareScenarioVersions = (baseId: number, targetId: number) =>
  authenticatedRequest<ScenarioCompareResponse>(
    `/scenarios/compare?base_id=${baseId}&target_id=${targetId}`,
  )
const scenarioAction = (scenarioId: number, action: string, note: string) =>
  authenticatedRequest<ScenarioVersionView>(`/scenarios/${scenarioId}/${action}`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
export const submitScenarioReview = (scenarioId: number, note: string) =>
  scenarioAction(scenarioId, 'submit', note)
export const approveScenarioReview = (scenarioId: number, note: string) =>
  scenarioAction(scenarioId, 'approve', note)
export const rejectScenarioReview = (scenarioId: number, note: string) =>
  scenarioAction(scenarioId, 'reject', note)
export const rollbackScenarioVersion = (scenarioId: number, note: string) =>
  scenarioAction(scenarioId, 'rollback', note)
export const uploadScenario = (file: File) => {
  const body = new FormData()
  body.append('file', file)
  return authenticatedRequest<ScenarioImportResponse>('/scenarios/import', {
    method: 'POST',
    body,
  })
}
export const activateScenario = (scenarioId: number) =>
  authenticatedRequest<ScenarioVersionView>(`/scenarios/${scenarioId}/activate`, {
    method: 'POST',
  })
export async function downloadScenarioTemplate() {
  const token = storedValue(TOKEN_KEY)
  if (!token) throw new Error('请先使用管理员账号登录')
  const response = await fetch(`${API_BASE}/scenarios/template`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error(`模板下载失败（${response.status}）`)
  return response.blob()
}

export const getDispatchPlans = () =>
  authenticatedRequest<DispatchPlanList>('/dispatch/plans')
export const submitDispatchPlan = (runId: string) =>
  authenticatedRequest<DispatchPlanView>('/dispatch/plans', {
    method: 'POST',
    body: JSON.stringify({ run_id: runId }),
  })
export const approveDispatchPlan = (planId: number) =>
  authenticatedRequest<DispatchPlanView>(`/dispatch/plans/${planId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ note: '运力、时间窗和冷链约束复核通过' }),
  })
export const issueDispatchPlan = (planId: number) =>
  authenticatedRequest<DispatchPlanView>(`/dispatch/plans/${planId}/dispatch`, {
    method: 'POST',
  })
export const getDriverAssignments = () =>
  authenticatedRequest<DriverAssignmentList>('/driver/assignments')
export const advanceDriverAssignment = (
  assignmentId: number,
  action: 'accept' | 'start' | 'complete',
) =>
  authenticatedRequest<DispatchPlanView>(`/driver/assignments/${assignmentId}/${action}`, {
    method: 'POST',
    body: JSON.stringify({
      note: action === 'complete' ? '货物送达，现场交接完成' : undefined,
    }),
  })
export async function downloadDispatchReport(planId: number) {
  const token = storedValue(TOKEN_KEY)
  if (!token) throw new Error('请先登录')
  const response = await fetch(`${API_BASE}/dispatch/plans/${planId}/report`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error(`报告导出失败（${response.status}）`)
  return response.blob()
}

export const getExperiments = () =>
  authenticatedRequest<ExperimentList>('/experiments?limit=20')
export const runAlgorithmExperiment = (
  name = '县域物流三压力算法对照实验',
  timeLimitSeconds = 1,
) =>
  authenticatedRequest<ExperimentView>('/experiments', {
    method: 'POST',
    body: JSON.stringify({
      name,
      time_limit_seconds: timeLimitSeconds,
    }),
  })
export async function downloadExperimentReport(experimentId: number) {
  const token = storedValue(TOKEN_KEY)
  if (!token) throw new Error('请先登录')
  const response = await fetch(`${API_BASE}/experiments/${experimentId}/report`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error(`实验报告导出失败（${response.status}）`)
  return response.blob()
}

export const getOperationsReadiness = () =>
  authenticatedRequest<OperationsReadiness>('/operations/readiness')

export async function downloadOperationsReport() {
  const token = storedValue(TOKEN_KEY)
  if (!token) throw new Error('请先登录')
  const response = await fetch(`${API_BASE}/operations/report`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error(`成果报告导出失败（${response.status}）`)
  return response.blob()
}

export const getMapRuntime = () =>
  authenticatedRequest<MapRuntimeConfig>('/map/runtime')
export const getMapConfigs = () =>
  authenticatedRequest<MapConfigList>('/map/configs')
export const createMapConfig = (payload: MapConfigInput) =>
  authenticatedRequest<MapConfigView>('/map/configs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
export const updateMapConfig = (id: number, payload: MapConfigInput) =>
  authenticatedRequest<MapConfigView>(`/map/configs/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
export const activateMapConfig = (id: number) =>
  authenticatedRequest<MapConfigView>(`/map/configs/${id}/activate`, { method: 'POST' })
export const disableMapConfig = (id: number) =>
  authenticatedRequest<MapConfigView>(`/map/configs/${id}/disable`, { method: 'POST' })
export const testMapConfig = (id: number) =>
  authenticatedRequest<AIConnectionTestResponse>(`/map/configs/${id}/test`, { method: 'POST' })
