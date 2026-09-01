export interface Node {
  id: string
  name: string
  longitude: number
  latitude: number
  kind: 'depot' | 'town' | 'processor' | 'village'
  coordinate_system: 'gcj02'
  coordinate_source: 'seed' | 'imported' | 'geocoded' | 'manual'
  coordinate_status: 'unverified' | 'verified' | 'needs_review'
  wgs84_longitude?: number
  wgs84_latitude?: number
  coordinate_accuracy_m?: number
  calibrated_at?: string
}

export interface Vehicle {
  id: string
  plate: string
  capacity_kg: number
  cold_chain: boolean
  cost_per_km: number
}

export interface Order {
  id: string
  node_id: string
  weight_kg: number
  window_start: number
  window_end: number
  cold_chain: boolean
}

export interface Scenario {
  id: string
  name: string
  nodes: Node[]
  orders: Order[]
  vehicles: Vehicle[]
  spatial_snapshot_id?: string
  spatial_snapshot_at?: string
  spatial_verified_nodes: number
}

export interface RouteStop {
  node_id: string
  node_name: string
  order_id?: string
  arrival_minute: number
  load_kg: number
  longitude: number
  latitude: number
}

export interface Route {
  vehicle_id: string
  plate: string
  cold_chain: boolean
  distance_km: number
  duration_minutes: number
  load_kg: number
  stops: RouteStop[]
}

export interface Metrics {
  distance_km: number
  estimated_cost_cny: number
  on_time_rate: number
  empty_distance_rate: number
  vehicles_used: number
}

export interface DecisionScoreComponent {
  key: string
  name: string
  score: number
  weight: number
  detail: string
}

export interface DecisionScore {
  total: number
  grade: string
  formula_version: string
  components: DecisionScoreComponent[]
}

export interface CandidateSummary {
  strategy: string
  status: string
  score: number
  distance_km: number
  estimated_cost_cny: number
  vehicles_used: number
  unassigned_orders: number
  selected: boolean
}

export interface AIOrchestrationInfo {
  requested: boolean
  used: boolean
  provider?: string
  model_name?: string
  stages: string[]
  recommended_strategy?: string
  selection_reason?: string
  fallback_reason?: string
  candidate_count: number
}

export interface OptimizeResult {
  run_id: string
  status: string
  solver: string
  solve_time_ms: number
  routes: Route[]
  metrics: Metrics
  baseline_metrics: Metrics
  explanations: string[]
  unassigned_order_ids: string[]
  routing: RoutingMatrixInfo
  event_location?: EventLocation
  decision_score?: DecisionScore
  candidate_summaries: CandidateSummary[]
  ai_orchestration: AIOrchestrationInfo
}

export interface EventLocation {
  node_id?: string
  location_name: string
  longitude: number
  latitude: number
  coordinate_system: 'gcj02'
  source: 'request' | 'scenario_node' | 'route_stop'
}

export interface ScenarioSpatialStatus {
  scenario_id: string
  snapshot_id?: string
  snapshot_at?: string
  snapshot_verified_nodes: number
  scenario_node_count: number
  current_verified_nodes: number
  aligned: boolean
  changed_node_ids: string[]
  missing_node_ids: string[]
  unverified_node_ids: string[]
  message: string
}

export interface RoutingMatrixInfo {
  requested_provider: string
  source: 'osrm' | 'haversine'
  cache_hit: boolean
  fallback_used: boolean
  fallback_reason?: string
  data_version?: string
  coordinate_count: number
}

export interface RoutingStatus {
  requested_provider: string
  osrm_base_url?: string
  fallback_enabled: boolean
  cache_entries: number
  cache_capacity: number
}

export interface CurrentWeather {
  location: string
  temperature_c: number
  apparent_temperature_c: number
  humidity_percent: number
  weather_code: number
  weather_label: string
  wind_speed_kmh: number
  observed_at: string
  fetched_at: string
  source: string
  cached: boolean
  stale: boolean
}

export interface ForecastPoint {
  date: string
  actual_tons?: number | null
  forecast_tons?: number | null
  lower_tons?: number | null
  upper_tons?: number | null
}

export interface TownshipDemand {
  node_id: string
  node_name: string
  demand_tons: number
  share: number
}

export interface DemandForecast {
  scenario_id: string
  generated_at: string
  horizon_days: number
  method: string
  history_basis: string
  points: ForecastPoint[]
  township_ranking: TownshipDemand[]
  today_forecast_tons: number
  peak_forecast_tons: number
  peak_date: string
  cold_chain_tons: number
  recommended_vehicles: number
  risk_level: 'low' | 'medium' | 'high'
  notes: string[]
  model_family: string
  training_samples: number
  validation_mae_tons?: number | null
  fallback_used: boolean
  fallback_reason?: string
  feature_names: string[]
}

export interface RunSummary {
  run_id: string
  scenario_id: string
  status: string
  solver: string
  solve_time_ms: number
  distance_km: number
  estimated_cost_cny: number
  vehicles_used: number
  event_type?: string
  event_vehicle_id?: string
  created_at: string
}

export interface RunListResponse {
  items: RunSummary[]
  next_cursor?: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  role: string
  username: string
  display_name: string
  expires_in: number
}

export interface RegisterInput {
  username: string
  display_name: string
  password: string
  agreement_accepted: true
}

export type OrderRequestStatus =
  | 'pending_review'
  | 'needs_info'
  | 'rejected'
  | 'converted'
  | 'cancelled'

export interface OrderRequestNodeOption {
  id: string
  name: string
  address?: string
  kind: 'depot' | 'town' | 'village' | 'processor'
}

export interface OrderRequest {
  id: number
  request_code: string
  requester_username: string
  requester_name: string
  node_id: string
  node_name: string
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
  status: OrderRequestStatus
  review_note?: string
  reviewer_username?: string
  reviewed_at?: string
  operational_order_id?: string
  operational_status?: string
  created_at: string
  updated_at: string
}

export interface OrderRequestList {
  items: OrderRequest[]
  total: number
}

export interface AIConfigInput {
  name: string
  description?: string
  provider: string
  base_url: string
  model_name: string
  api_key?: string
  enabled: boolean
  temperature: number
}

export interface AIConfigView {
  id: number
  name: string
  description?: string
  provider: string
  base_url: string
  model_name: string
  enabled: boolean
  temperature: number
  has_api_key: boolean
  api_key_masked: string
  last_test_status: 'untested' | 'success' | 'failed'
  last_test_message?: string
  last_tested_at?: string
  created_by?: string
  updated_by?: string
  created_at: string
  updated_at: string
}

export interface AIConfigList {
  items: AIConfigView[]
}

export interface CurrentUser {
  username: string
  display_name: string
  role: string
  last_login_at?: string
}

export type UserRole = 'admin' | 'dispatcher' | 'driver' | 'viewer' | 'user'

export interface ManagedUser {
  id: number
  username: string
  display_name: string
  role: UserRole
  is_active: boolean
  is_locked: boolean
  locked_until?: string
  failed_login_count: number
  last_login_at?: string
  last_login_ip?: string
  password_changed_at?: string
  created_at: string
  updated_at: string
}

export interface ManagedUserList {
  items: ManagedUser[]
  total: number
  active_count: number
  admin_count: number
  locked_count: number
}

export interface UserCreateInput {
  username: string
  display_name: string
  role: UserRole
  password: string
  is_active: boolean
}

export interface UserUpdateInput {
  display_name: string
  role: UserRole
  is_active: boolean
  unlock?: boolean
}

export interface AuditLog {
  id: number
  category: string
  action: string
  outcome: 'success' | 'failed' | 'blocked'
  resource_type?: string
  resource_id?: string
  actor_username?: string
  ip_address?: string
  user_agent?: string
  detail: Record<string, unknown>
  created_at: string
}

export interface AuditLogList {
  items: AuditLog[]
  total: number
}

export interface MasterDataSummary {
  order_total: number
  pending_orders: number
  cold_chain_orders: number
  invalid_orders: number
  vehicle_total: number
  available_vehicles: number
  node_total: number
  active_nodes: number
}

export interface ReferenceWeight {
  code: string
  label: string
  weight: number
}

export interface ReferenceDemandPoint {
  town_name: string
  village_count: number
  demand_tons: number
  share_percent: number
}

export interface ReferenceCandidate {
  rank: number
  town_name: string
  score: number
  level: string
  candidate_type: 'core' | 'remote_safeguard'
  demand_tons?: number
  rationale: string
}

export interface ReferenceCoordinateQuality {
  total_nodes: number
  inside_bounds: number
  outside_bounds: number
  duplicate_nodes: number
  flagged_node_ids: string[]
  status: 'verified' | 'needs_review'
  note: string
}

export interface ReferenceFacility {
  level: string
  name: string
  count: number
  status: string
  function: string
  coverage_percent?: number
}

export interface QidongReferenceSummary {
  dataset_version: string
  source_scope: string
  service_circle_minutes: number
  township_count: number
  village_units: number
  town_logistics_stations: number
  township_ecommerce_stations: number
  field_cold_stores: number
  village_service_stations: number
  co_delivery_stations: number
  county_facility_count: number
  village_coverage_percent: number
  road_total_km: number
  road_density_km_per_sq_km: number
  demand_unit: string
  reference_demand_tons: number
  demo_load_ratio: number
  demo_order_count: number
  demo_order_weight_kg: number
  demo_mapped_town_count: number
  demand_summary: ReferenceDemandPoint[]
  ahp_weights: ReferenceWeight[]
  candidates: ReferenceCandidate[]
  facility_summary: ReferenceFacility[]
  facility_gaps: string[]
  coordinate_quality: ReferenceCoordinateQuality
  notes: string[]
}

export type DataImportStatus = 'validated' | 'rejected' | 'committed'

export interface DataImportError {
  row: number
  field: string
  message: string
}

export interface DataImportBatch {
  id: number
  batch_code: string
  import_type: string
  filename: string
  status: DataImportStatus
  total_rows: number
  valid_rows: number
  error_rows: number
  warning_rows: number
  errors: DataImportError[]
  created_by?: string
  committed_by?: string
  created_at: string
  committed_at?: string
}

export interface DataImportBatchList {
  items: DataImportBatch[]
  total: number
}

export type DataQualityStatus = 'passed' | 'warning' | 'blocked' | 'disabled'

export interface DataQualityRule {
  id: number
  rule_code: string
  name: string
  description: string
  entity_type: string
  severity: 'error' | 'warning'
  enabled: boolean
  config: Record<string, unknown>
  issue_count: number
  status: DataQualityStatus
  detail: string
  updated_at: string
}

export interface DataQualityReport {
  items: DataQualityRule[]
  blocked_count: number
  warning_count: number
  publish_ready: boolean
}

export interface MasterDataPublishResponse {
  scenario: ScenarioVersionView
  warnings: string[]
}

export type MasterOrderStatus = 'pending' | 'planned' | 'completed' | 'cancelled'
export type MasterPriority = 'normal' | 'urgent'

export interface MasterOrderInput {
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
  priority: MasterPriority
  status: MasterOrderStatus
}

export interface MasterOrder extends MasterOrderInput {
  id: string
  node_name: string
  created_at: string
  updated_at: string
}

export interface MasterOrderCreate extends MasterOrderInput {
  id: string
}

export interface MasterOrderList {
  items: MasterOrder[]
  total: number
}

export type MasterVehicleStatus = 'available' | 'assigned' | 'maintenance' | 'offline'
export type MasterVehicleType = 'van' | 'truck' | 'refrigerated'

export interface MasterVehicleInput {
  plate: string
  capacity_kg: number
  cold_chain: boolean
  vehicle_type: MasterVehicleType
  driver_name?: string
  driver_phone?: string
  status: MasterVehicleStatus
  cost_per_km: number
  shift_start: number
  shift_end: number
}

export interface MasterVehicle extends MasterVehicleInput {
  id: string
  available: boolean
  created_at: string
  updated_at: string
}

export interface MasterVehicleCreate extends MasterVehicleInput {
  id: string
}

export interface MasterVehicleList {
  items: MasterVehicle[]
  total: number
}

export type MasterNodeKind = 'depot' | 'town' | 'village' | 'processor'

export interface MasterNodeInput {
  name: string
  longitude: number
  latitude: number
  kind: MasterNodeKind
  address?: string
  contact_name?: string
  contact_phone?: string
  service_radius_km: number
  is_active: boolean
}

export interface MasterNode extends MasterNodeInput {
  id: string
  wgs84_longitude?: number
  wgs84_latitude?: number
  coordinate_system: 'gcj02'
  coordinate_source: 'seed' | 'imported' | 'geocoded' | 'manual'
  coordinate_status: 'unverified' | 'verified' | 'needs_review'
  coordinate_accuracy_m?: number
  calibrated_at?: string
  calibrated_by?: number
  spatial_issue: 'none' | 'outside_bounds' | 'duplicate'
  created_at: string
  updated_at: string
}

export interface MasterNodeCreate extends MasterNodeInput {
  id: string
}

export interface MasterNodeList {
  items: MasterNode[]
  total: number
}

export interface NodeCoordinateInput {
  longitude: number
  latitude: number
  address?: string
  coordinate_source: 'geocoded' | 'manual'
  coordinate_accuracy_m?: number
  coordinate_status: 'verified' | 'needs_review'
  note?: string
}

export interface NodeCoordinateRevision {
  id: number
  node_id: string
  before_longitude?: number
  before_latitude?: number
  longitude: number
  latitude: number
  wgs84_longitude: number
  wgs84_latitude: number
  coordinate_source: string
  coordinate_status: string
  coordinate_accuracy_m?: number
  address?: string
  note?: string
  actor_username?: string
  created_at: string
}

export interface NodeCoordinateRevisionList {
  items: NodeCoordinateRevision[]
}

export interface SpatialQualitySummary {
  total: number
  verified: number
  needs_review: number
  unverified: number
  outside_bounds: number
  duplicate: number
  missing_address: number
  display_coordinate_system: 'GCJ-02'
  storage_coordinate_system: 'WGS-84'
}

export interface AIConnectionTestResponse {
  success: boolean
  message: string
  latency_ms: number
}

export interface AIExplanationResponse {
  run_id: string
  provider: string
  model_name: string
  explanation: string
}

export interface ScenarioVersionView {
  id: number
  scenario_code: string
  version_no: number
  version_key: string
  name: string
  county_name: string
    status: ScenarioVersionStatus
  source_type: 'demo' | 'excel'
  source_filename?: string
  node_count: number
  order_count: number
  vehicle_count: number
    validation_summary: { warnings?: string[]; validated?: boolean }
    fingerprint?: string
    release_note?: string
    created_by?: string
    submitted_by?: string
    submitted_at?: string
    reviewed_by?: string
    reviewed_at?: string
    review_note?: string
    created_at: string
    activated_at?: string
  }

  export type ScenarioVersionStatus =
    | 'draft' | 'pending_review' | 'rejected' | 'active' | 'archived'

  export interface ScenarioGovernanceSummary {
    total: number
    active: number
    pending_review: number
    draft: number
    rejected: number
    archived: number
  }

  export interface ScenarioVersionList {
    items: ScenarioVersionView[]
    total: number
    summary: ScenarioGovernanceSummary
  }

  export interface ScenarioTransition {
    id: number
    from_status?: ScenarioVersionStatus
    to_status: ScenarioVersionStatus
    note?: string
    actor?: string
    created_at: string
  }

  export interface ScenarioVersionDetail extends ScenarioVersionView {
    transitions: ScenarioTransition[]
  }

  export interface ScenarioDiffItem {
    object_id: string
    change_type: 'added' | 'removed' | 'changed'
    description: string
  }

  export interface ScenarioDiffGroup {
    added: number
    removed: number
    changed: number
    details: ScenarioDiffItem[]
  }

  export interface ScenarioDiffMetrics {
    node_count: number
    order_count: number
    vehicle_count: number
    total_weight_kg: number
    cold_chain_capacity_kg: number
  }

  export interface ScenarioCompareResponse {
    base: ScenarioVersionView
    target: ScenarioVersionView
    base_metrics: ScenarioDiffMetrics
    target_metrics: ScenarioDiffMetrics
    deltas: ScenarioDiffMetrics
    nodes: ScenarioDiffGroup
    orders: ScenarioDiffGroup
    vehicles: ScenarioDiffGroup
  }

export interface ScenarioImportResponse {
  scenario: ScenarioVersionView
  warnings: string[]
}

export type DispatchPlanStatus =
  | 'pending_approval' | 'approved' | 'rejected' | 'dispatched'
  | 'accepted' | 'executing' | 'completed'

export type DriverAssignmentStatus = 'pending' | 'accepted' | 'executing' | 'completed'

export interface DriverNavigationStop {
  sequence: number
  order_id?: string
  node_id: string
  node_name: string
  longitude: number
  latitude: number
  arrival_minute: number
  load_kg: number
  status: 'planned' | 'completed'
}

export interface DriverAssignmentView {
  id: number
  plan_id: number
  route_index: number
  vehicle_id: string
  plate: string
  status: DriverAssignmentStatus
  driver_username?: string
  distance_km: number
  duration_minutes: number
  load_kg: number
  stop_count: number
  next_stop_name?: string
  next_stop?: DriverNavigationStop
  navigation_stops: DriverNavigationStop[]
  accepted_at?: string
  started_at?: string
  completed_at?: string
  completion_note?: string
  updated_at: string
}

export interface DispatchPlanView {
  id: number
  run_id: string
  scenario_id: string
  status: DispatchPlanStatus
  submitted_by?: string
  reviewed_by?: string
  rejection_reason?: string
  route_count: number
  distance_km: number
  estimated_cost_cny: number
  submitted_at: string
  reviewed_at?: string
  dispatched_at?: string
  completed_at?: string
  updated_at: string
  assignments: DriverAssignmentView[]
}

export interface DispatchPlanList {
  items: DispatchPlanView[]
}

export interface DriverAssignmentList {
  items: DriverAssignmentView[]
}

export interface ExperimentCaseResult {
  case_key: 'standard' | 'peak' | 'cold_chain'
  case_name: string
  description: string
  demand_multiplier: number
  demand_tons: number
  status: 'optimal' | 'feasible' | 'infeasible'
  solve_time_ms: number
  baseline_distance_km: number
  optimized_distance_km: number
  distance_reduction_pct: number
  baseline_cost_cny: number
  optimized_cost_cny: number
  cost_saving_cny: number
  cost_reduction_pct: number
  vehicles_used: number
  service_rate: number
  unassigned_orders: number
  routing_source: string
}

export interface ExperimentSummary {
  average_distance_reduction_pct: number
  total_cost_saving_cny: number
  average_cost_reduction_pct: number
  average_service_rate: number
  average_vehicles_used: number
  total_solve_time_ms: number
  completed_cases: number
}

export interface ExperimentView {
  id: number
  experiment_code: string
  name: string
  scenario_key: string
  scenario_fingerprint: string
  status: 'running' | 'completed' | 'failed'
  solver: string
  baseline: string
  time_limit_seconds: number
  case_count: number
  summary?: ExperimentSummary
  results: ExperimentCaseResult[]
  error_message?: string
  created_by?: string
  created_at: string
  completed_at?: string
}

export interface ExperimentList {
  items: ExperimentView[]
}

export interface OperationsReadinessDimension {
  key: string
  name: string
  score: number
  ready: boolean
  checks: string[]
  gaps: string[]
}

export interface OperationsWorkflowStep {
  step: number
  title: string
  duration_seconds: number
  description: string
  route: string
  ready: boolean
}

export interface OperationsKPI {
  key: string
  name: string
  value: number
  unit: string
  source_id?: string
}

export interface OperationsComparisonRow {
  key: string
  name: string
  baseline: number
  optimized: number
  unit: string
  improvement: number
}

export interface OperationsEvidenceItem {
  requirement: string
  capability: string
  evidence_id?: string
  status: 'verified' | 'attention'
  route: string
}

export interface OperationsReference {
  label: string
  value?: string
  detail: string
  route: string
  ready: boolean
}

export interface OperationsReadiness {
  generated_at: string
  overall_score: number
  dimensions: OperationsReadinessDimension[]
  script: OperationsWorkflowStep[]
  kpis: OperationsKPI[]
  comparison: OperationsComparisonRow[]
  evidence: OperationsEvidenceItem[]
  references: OperationsReference[]
  tips: string[]
  total_duration_seconds: number
}

export interface MapConfigInput {
  name: string
  provider: 'amap'
  web_key?: string
  security_code?: string
  map_style: 'normal' | 'whitesmoke' | 'fresh' | 'light'
  enabled: boolean
}

export interface MapConfigView {
  id: number
  name: string
  provider: 'amap'
  map_style: 'normal' | 'whitesmoke' | 'fresh' | 'light'
  enabled: boolean
  has_web_key: boolean
  web_key_masked: string
  has_security_code: boolean
  security_code_masked: string
  last_test_status: 'untested' | 'success' | 'failed'
  last_test_message?: string
  last_tested_at?: string
  created_by?: string
  updated_by?: string
  created_at: string
  updated_at: string
}

export interface MapConfigList {
  items: MapConfigView[]
}

export interface MapRuntimeConfig {
  provider: 'offline' | 'amap'
  mode: 'offline' | 'online'
  web_key?: string
  map_style: 'normal' | 'whitesmoke' | 'fresh' | 'light'
  service_host?: string
}
