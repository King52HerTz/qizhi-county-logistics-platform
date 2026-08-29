<script setup lang="ts">
import { EffectScatterChart, LinesChart, ScatterChart } from "echarts/charts";
import {
  GeoComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { ECharts } from "echarts/core";
import {
  Check,
  CircleAlert,
  Crosshair,
  Layers3,
  Map as MapIcon,
  MapPin,
  Maximize2,
  Minimize2,
  Minus,
  Plus,
  RefreshCw,
  Route as RouteIcon,
  Settings2,
  Snowflake,
  X,
} from "@lucide/vue";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { getMapRuntime } from "../services/api";
import type {
  MapRuntimeConfig,
  Node,
  OptimizeResult,
  Route,
  Scenario,
  ScenarioSpatialStatus,
} from "../types/logistics";

declare global {
  interface Window {
    AMap?: any;
    _AMapSecurityConfig?: { serviceHost?: string };
  }
}

echarts.use([
  EffectScatterChart,
  GeoComponent,
  LinesChart,
  ScatterChart,
  TooltipComponent,
  CanvasRenderer,
]);

const props = withDefaults(
  defineProps<{
    scenario: Scenario;
    result?: OptimizeResult;
    eventMode?: boolean;
    selectedRoute?: number;
    compact?: boolean;
    spatialStatus?: ScenarioSpatialStatus;
  }>(),
  {
    eventMode: false,
    selectedRoute: 0,
    compact: false,
  },
);
const emit = defineEmits<{
  selectRoute: [index: number];
  openSettings: [];
}>();

const host = ref<HTMLDivElement>();
const source = ref<"offline" | "amap">("offline");
const sourceMessage = ref("离线运营地图");
const filter = ref<"all" | "ambient" | "cold">("all");
const showNodes = ref(true);
const selectedNodeId = ref<string>();
const currentZoom = ref(1.08);
const lastUpdated = ref(new Date());
const loading = ref(true);
const loadWarning = ref("");
const expanded = ref(false);
const palette = ["#2d6cdf", "#7b5bd6", "#ef8a19", "#168653", "#d85450"];
const nodeMap = computed(
  () => new Map(props.scenario.nodes.map((node) => [node.id, node])),
);
const orderMap = computed(() => {
  const grouped = new Map<string, typeof props.scenario.orders>();
  props.scenario.orders.forEach((order) => {
    const items = grouped.get(order.node_id) ?? [];
    items.push(order);
    grouped.set(order.node_id, items);
  });
  return grouped;
});
const visibleRoutes = computed(() =>
  (props.result?.routes ?? [])
    .map((route, index) => ({ route, index }))
    .filter(
      ({ route }) =>
        filter.value === "all" ||
        (filter.value === "cold" ? route.cold_chain : !route.cold_chain),
    ),
);
const activeRoute = computed(
  () => props.result?.routes[props.selectedRoute] ?? props.result?.routes[0],
);
const activeVehicle = computed(() =>
  props.scenario.vehicles.find(
    (vehicle) => vehicle.id === activeRoute.value?.vehicle_id,
  ),
);
const activeLoadRate = computed(() =>
  activeVehicle.value && activeRoute.value
    ? Math.round(
        (activeRoute.value.load_kg / activeVehicle.value.capacity_kg) * 100,
      )
    : 0,
);
const selectedNode = computed(() =>
  nodeMap.value.get(selectedNodeId.value ?? ""),
);
const selectedNodeOrders = computed(
  () => orderMap.value.get(selectedNodeId.value ?? "") ?? [],
);
const spatialStateLabel = computed(() => {
  if (!props.spatialStatus) return "";
  if (props.spatialStatus.aligned) return "坐标快照已同步";
  const publishCount = new Set([
    ...props.spatialStatus.changed_node_ids,
    ...props.spatialStatus.missing_node_ids,
  ]).size;
  if (publishCount) return `${publishCount} 个网点待重新发布`;
  return `${props.spatialStatus.unverified_node_ids.length} 个坐标待核验`;
});

let chart: ECharts | undefined;
let amap: any;
let observer: ResizeObserver | undefined;
let geoData: any;
let drawToken = 0;
let routeOverlays: any[] = [];
let activeRouteOverlays: any[] = [];

function coordinatesForNode(node: Node): [number, number] {
  return [node.longitude, node.latitude];
}

function routeCoordinates(route: Route): [number, number][] {
  return route.stops
    .map((stop) => nodeMap.value.get(stop.node_id))
    .filter((node): node is Node => Boolean(node))
    .map(coordinatesForNode);
}

function stopSequence(nodeId: string) {
  const index =
    activeRoute.value?.stops.findIndex((stop) => stop.node_id === nodeId) ?? -1;
  return index > 0 && index < (activeRoute.value?.stops.length ?? 0) - 1
    ? index
    : undefined;
}

function eventCoordinates(): [number, number] {
  if (props.result?.event_location) {
    return [
      props.result.event_location.longitude,
      props.result.event_location.latitude,
    ];
  }
  const routeStop =
    activeRoute.value?.stops.find((stop) => Boolean(stop.order_id)) ??
    activeRoute.value?.stops[1] ??
    activeRoute.value?.stops[0];
  const fallbackNode =
    (routeStop ? nodeMap.value.get(routeStop.node_id) : undefined) ??
    props.scenario.nodes.find((node) => node.kind === "depot") ??
    props.scenario.nodes[0];
  return fallbackNode ? coordinatesForNode(fallbackNode) : [0, 0];
}

function drawOffline() {
  if (!chart) return;
  const routeSeries = visibleRoutes.value.map(({ route, index }) => ({
    name: route.plate,
    type: "lines",
    coordinateSystem: "geo",
    zlevel: index === props.selectedRoute ? 4 : 2,
    data: [{ coords: routeCoordinates(route), routeIndex: index }],
    effect:
      index === props.selectedRoute
        ? {
            show: true,
            period: 5,
            trailLength: 0.12,
            symbol: "arrow",
            symbolSize: 7,
            color: palette[index % palette.length],
          }
        : { show: false },
    lineStyle: {
      color: palette[index % palette.length],
      width: index === props.selectedRoute ? 4 : 2.4,
      opacity: index === props.selectedRoute ? 0.95 : 0.42,
      curveness: 0.08,
    },
    emphasis: { lineStyle: { width: 5, opacity: 1 } },
  }));
  const nodes = props.scenario.nodes.map((node) => ({
    id: node.id,
    name: node.name,
    value: [
      node.longitude,
      node.latitude,
      node.kind === "depot" ? 19 : node.kind === "village" ? 9 : 12,
    ],
    sequence: stopSequence(node.id),
    itemStyle: {
      color:
        node.kind === "depot"
          ? "#0d5c3b"
          : node.kind === "village"
            ? "#fff"
            : "#eaf5ef",
      borderColor: node.kind === "village" ? "#168653" : "#0d6944",
      borderWidth: node.kind === "depot" ? 3 : 2,
    },
  }));
  chart.setOption(
    {
      animationDurationUpdate: 300,
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(17,47,34,.96)",
        borderWidth: 0,
        padding: [9, 11],
        textStyle: { color: "#fff", fontSize: 12 },
        formatter: (params: any) => params.data?.name ?? params.seriesName,
      },
      geo: {
        map: "qidong",
        roam: true,
        zoom: currentZoom.value,
        layoutCenter: ["50%", "50%"],
        layoutSize: "96%",
        itemStyle: {
          areaColor: "#f3f6f4",
          borderColor: "#168653",
          borderWidth: 1.8,
          shadowColor: "rgba(20,84,54,.08)",
          shadowBlur: 10,
        },
        emphasis: {
          itemStyle: { areaColor: "#edf4ef" },
          label: { show: false },
        },
        select: { disabled: true },
      },
      series: [
        ...routeSeries,
        ...(showNodes.value
          ? [
              {
                name: "业务节点",
                type: "scatter",
                coordinateSystem: "geo",
                zlevel: 6,
                data: nodes,
                symbolSize: (value: number[]) => value[2],
                label: {
                  show: true,
                  formatter: (params: any) =>
                    params.data.sequence
                      ? String(params.data.sequence)
                      : params.data.name,
                  position: (params: any) =>
                    params.data.sequence ? "inside" : "right",
                  color: (params: any) =>
                    params.data.sequence ? "#fff" : "#34483d",
                  fontSize: (params: any) => (params.data.sequence ? 10 : 9),
                  fontWeight: 700,
                  backgroundColor: (params: any) =>
                    params.data.sequence ? "#2d6cdf" : "rgba(255,255,255,.88)",
                  padding: (params: any) =>
                    params.data.sequence ? [3, 5] : [3, 5],
                  borderRadius: 5,
                },
              },
            ]
          : []),
        ...(props.eventMode
          ? [
              {
                name: "车辆异常",
                type: "effectScatter",
                coordinateSystem: "geo",
                zlevel: 12,
                data: [
                  { name: "冷链车辆故障", value: [...eventCoordinates(), 18] },
                ],
                symbol:
                  "path://M12 2 1 21h22L12 2zm0 6.2c.6 0 1 .4 1 1v5.2a1 1 0 0 1-2 0V9.2c0-.6.4-1 1-1zm0 9.1a1.25 1.25 0 1 1 0 2.5 1.25 1.25 0 0 1 0-2.5z",
                symbolSize: 34,
                itemStyle: { color: "#d94f48" },
                label: {
                  show: true,
                  formatter: "车辆故障",
                  position: "top",
                  distance: 8,
                  color: "#fff",
                  fontSize: 10,
                  fontWeight: 800,
                  backgroundColor: "#b83e39",
                  borderColor: "#fff",
                  borderWidth: 1,
                  borderRadius: 5,
                  padding: [5, 7],
                },
                rippleEffect: { scale: 4, brushType: "stroke" },
              },
            ]
          : []),
      ],
    },
    true,
  );
}

function markerContent(node: Node, sequence?: number) {
  const className =
    node.kind === "depot" ? "amap-depot" : sequence ? "amap-stop" : "amap-node";
  return `<button class="qz-map-marker ${className}" aria-label="${node.name}">${sequence ?? ""}</button>`;
}

function faultMarkerContent() {
  return `
    <div class="qz-fault-marker" role="img" aria-label="冷链车辆故障">
      <span class="qz-fault-marker__pulse"></span>
      <span class="qz-fault-marker__pin">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3 2.6 20h18.8L12 3Z"></path>
          <path d="M12 8.5v5.3"></path>
          <path d="M12 17.2h.01"></path>
        </svg>
      </span>
      <strong>车辆故障</strong>
    </div>`;
}

function loadAmapPlugin(name: string) {
  return new Promise<void>((resolve) => window.AMap.plugin(name, resolve));
}

async function resolveRoadSegment(
  origin: [number, number],
  destination: [number, number],
) {
  const AMap = window.AMap;
  const driving = new AMap.Driving({
    policy: AMap.DrivingPolicy?.LEAST_TIME,
    hideMarkers: true,
    showTraffic: false,
    autoFitView: false,
  });
  return new Promise<[number, number][]>((resolve, reject) => {
    const timeout = window.setTimeout(
      () => reject(new Error("道路路径规划超时")),
      6500,
    );
    driving.search(origin, destination, (status: string, result: any) => {
      window.clearTimeout(timeout);
      const path =
        status === "complete"
          ? result?.routes?.[0]?.steps?.flatMap((step: any) =>
              (step.path ?? []).map(
                (point: any) =>
                  [Number(point.lng), Number(point.lat)] as [number, number],
              ),
            )
          : undefined;
      if (path?.length) resolve(path);
      else reject(new Error("道路路径规划失败"));
    });
  });
}

async function resolveRoadPath(coordinates: [number, number][]) {
  if (coordinates.length < 2 || !window.AMap) return coordinates;
  await loadAmapPlugin("AMap.Driving");
  const segments: [number, number][][] = [];
  for (let index = 0; index < coordinates.length - 1; index += 1) {
    segments.push(
      await resolveRoadSegment(coordinates[index], coordinates[index + 1]),
    );
  }
  return segments.flatMap((segment, index) =>
    index === 0 ? segment : segment.slice(1),
  );
}

async function drawAmap(fitMode: "preserve" | "all" | "active" = "preserve") {
  if (!amap || !window.AMap) return;
  const token = ++drawToken;
  amap.clearMap();
  const AMap = window.AMap;
  routeOverlays = [];
  activeRouteOverlays = [];
  const polygons = geoData.features.flatMap((feature: any) => {
    const coordinates =
      feature.geometry.type === "MultiPolygon"
        ? feature.geometry.coordinates.flat()
        : feature.geometry.coordinates;
    return coordinates.map(
      (path: number[][]) =>
        new AMap.Polygon({
          path,
          strokeColor: "#168653",
          strokeWeight: 2,
          strokeOpacity: 0.9,
          fillColor: "#eaf3ed",
          fillOpacity: 0.08,
          zIndex: 9,
        }),
    );
  });
  amap.add(polygons);
  visibleRoutes.value.forEach(({ route, index }) => {
    const directPath = routeCoordinates(route);
    const line = new AMap.Polyline({
      path: directPath,
      strokeColor: palette[index % palette.length],
      strokeWeight: index === props.selectedRoute ? 6 : 3,
      strokeOpacity: index === props.selectedRoute ? 0.96 : 0.46,
      showDir: true,
      lineJoin: "round",
      zIndex: index === props.selectedRoute ? 55 : 35,
    });
    line.on("click", () => emit("selectRoute", index));
    amap.add(line);
    routeOverlays.push(line);
    if (index === props.selectedRoute) activeRouteOverlays.push(line);
    void resolveRoadPath(directPath)
      .then((path) => {
        if (token !== drawToken) return;
        line.setPath(path);
        if (fitMode === "active" && index === props.selectedRoute)
          fitActiveRoute();
        if (fitMode === "all") fitAllRoutes();
      })
      .catch(() => {
        /* straight-line fallback stays visible */
      });
  });
  if (showNodes.value) {
    props.scenario.nodes.forEach((node) => {
      const marker = new AMap.Marker({
        position: coordinatesForNode(node),
        content: markerContent(node, stopSequence(node.id)),
        offset: new AMap.Pixel(-12, -12),
        zIndex: node.kind === "depot" ? 80 : 70,
      });
      marker.on("click", () => {
        selectedNodeId.value = node.id;
      });
      amap.add(marker);
    });
  }
  if (props.eventMode) {
    amap.add(
      new AMap.Marker({
        position: eventCoordinates(),
        content: faultMarkerContent(),
        offset: new AMap.Pixel(-44, -54),
        zIndex: 160,
      }),
    );
  }
  if (fitMode === "active") fitActiveRoute();
  if (fitMode === "all") fitAllRoutes();
}

function loadAmapScript(runtime: MapRuntimeConfig) {
  if (window.AMap) return Promise.resolve();
  window._AMapSecurityConfig = {
    serviceHost: runtime.service_host
      ? `${window.location.origin}${runtime.service_host}`
      : undefined,
  };
  return new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    const timeout = window.setTimeout(() => {
      script.remove();
      reject(new Error("高德地图脚本加载超时"));
    }, 8000);
    const finish = (callback: () => void) => {
      window.clearTimeout(timeout);
      script.onload = null;
      script.onerror = null;
      callback();
    };
    script.id = "qizhi-amap-js";
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(runtime.web_key ?? "")}`;
    script.async = true;
    script.onload = () => finish(resolve);
    script.onerror = () =>
      finish(() => reject(new Error("高德地图脚本加载失败")));
    document.head.appendChild(script);
  });
}

async function initialize() {
  loading.value = true;
  loadWarning.value = "";
  const geoResponse = await fetch("/qidong.json");
  geoData = await geoResponse.json();
  if (geoData.features?.[0]?.properties)
    geoData.features[0].properties.name = "祁东县";
  let runtime: MapRuntimeConfig = {
    provider: "offline",
    mode: "offline",
    map_style: "whitesmoke",
  };
  try {
    runtime = await getMapRuntime();
  } catch {
    /* permission/network fallback */
  }
  if (
    runtime.mode === "online" &&
    runtime.provider === "amap" &&
    runtime.web_key
  ) {
    try {
      await loadAmapScript(runtime);
      await nextTick();
      amap = new window.AMap.Map(host.value, {
        zoom: 10,
        center: [112.08, 26.78],
        viewMode: "2D",
        mapStyle: `amap://styles/${runtime.map_style}`,
        showLabel: true,
      });
      source.value = "amap";
      sourceMessage.value = "高德道路地图";
      await drawAmap("all");
    } catch {
      loadWarning.value = "道路地图连接失败，已自动切换到离线地图";
    }
  }
  if (source.value === "offline") {
    echarts.registerMap("qidong", geoData);
    await nextTick();
    chart = echarts.init(host.value);
    chart.on("click", (params: any) => {
      if (
        params.seriesType === "lines" &&
        typeof params.data?.routeIndex === "number"
      ) {
        emit("selectRoute", params.data.routeIndex);
      }
      if (params.seriesName === "业务节点" && params.data?.id)
        selectedNodeId.value = params.data.id;
    });
    drawOffline();
  }
  observer = new ResizeObserver(() => {
    chart?.resize();
    amap?.resize?.();
  });
  if (host.value) observer.observe(host.value);
  loading.value = false;
  lastUpdated.value = new Date();
}

function redraw() {
  if (source.value === "amap") void drawAmap();
  else drawOffline();
  lastUpdated.value = new Date();
}

function changeZoom(delta: number) {
  if (source.value === "amap") {
    amap?.setZoom(Math.max(5, Math.min(18, amap.getZoom() + delta)));
  } else {
    currentZoom.value = Math.max(
      0.85,
      Math.min(2.4, currentZoom.value + delta * 0.15),
    );
    drawOffline();
  }
}

function resetView() {
  selectedNodeId.value = undefined;
  if (source.value === "amap") {
    fitAllRoutes();
  } else {
    currentZoom.value = 1.08;
    chart?.setOption({ geo: { center: undefined, zoom: currentZoom.value } });
  }
}

function fitActiveRoute() {
  if (source.value === "amap") {
    if (activeRouteOverlays.length) {
      amap?.setFitView(activeRouteOverlays, false, [64, 350, 64, 72], 14);
    } else {
      const coordinates = activeRoute.value
        ? routeCoordinates(activeRoute.value)
        : [];
      if (coordinates.length)
        amap?.setBounds(
          new window.AMap.Bounds(
            coordinates[0],
            coordinates[coordinates.length - 1],
          ),
        );
    }
  } else {
    currentZoom.value = 1.5;
    drawOffline();
  }
}

function fitAllRoutes() {
  if (source.value === "amap") {
    if (routeOverlays.length)
      amap?.setFitView(routeOverlays, false, [58, 70, 58, 70], 13);
    else amap?.setZoomAndCenter(10, [112.08, 26.78]);
  } else resetView();
}

function toggleExpanded() {
  expanded.value = !expanded.value;
  document.body.style.overflow = expanded.value ? "hidden" : "";
  nextTick(() => {
    chart?.resize();
    amap?.resize?.();
    fitActiveRoute();
  });
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === "Escape" && expanded.value) toggleExpanded();
}

watch(() => [props.result, props.eventMode], redraw, { deep: true });
watch(
  () => props.selectedRoute,
  () => {
    if (source.value === "amap") void drawAmap("active");
    else redraw();
  },
);
watch(filter, () => {
  const firstVisible = visibleRoutes.value[0];
  if (
    firstVisible &&
    !visibleRoutes.value.some((item) => item.index === props.selectedRoute)
  ) {
    emit("selectRoute", firstVisible.index);
  }
  redraw();
});
watch(showNodes, redraw);
onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
  void initialize();
});
onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
  document.body.style.overflow = "";
  observer?.disconnect();
  chart?.dispose();
  amap?.destroy?.();
});
</script>

<template>
  <section class="professional-map" :class="{ compact, expanded }">
    <header v-if="!compact" class="map-toolbar">
      <div class="map-heading">
        <h2>
          <MapIcon :size="17" />{{
            eventMode ? "事件态势地图" : "实时调度地图"
          }}
        </h2>
        <p>
          {{
            eventMode
              ? "车辆状态、受影响订单与重调度路线统一监控"
              : "祁东县城乡配送网络 · 路线、车辆与订单统一监控"
          }}
        </p>
      </div>
      <div class="map-filters">
        <button :class="{ active: filter === 'all' }" @click="filter = 'all'">
          <RouteIcon :size="14" />全部路线
        </button>
        <button
          :class="{ active: filter === 'ambient' }"
          @click="filter = 'ambient'"
        >
          <Check :size="14" />常温
        </button>
        <button :class="{ active: filter === 'cold' }" @click="filter = 'cold'">
          <Snowflake :size="14" />冷链
        </button>
        <button :class="{ active: showNodes }" @click="showNodes = !showNodes">
          <MapPin :size="14" />节点
        </button>
      </div>
      <div class="map-source">
        <span :class="source"><i />{{ sourceMessage }}</span>
        <span
          v-if="spatialStatus"
          class="calibration-state"
          :class="{ warning: !spatialStatus.aligned }"
          :title="spatialStatus.message"
        >
          {{ spatialStateLabel }}
        </span>
        <button
          title="地图服务设置"
          aria-label="地图服务设置"
          @click="emit('openSettings')"
        >
          <Settings2 :size="16" />
        </button>
      </div>
    </header>

    <div class="map-canvas">
      <div ref="host" class="map-host" />
      <div v-if="loading" class="map-loading">
        <RefreshCw class="spin" :size="22" /><span>正在加载地图</span>
      </div>
      <div v-if="loadWarning" class="map-warning">
        <CircleAlert :size="14" />{{ loadWarning }}
      </div>

      <div v-if="!compact" class="map-controls">
        <button title="放大" aria-label="放大地图" @click="changeZoom(1)">
          <Plus :size="17" />
        </button>
        <button title="缩小" aria-label="缩小地图" @click="changeZoom(-1)">
          <Minus :size="17" />
        </button>
        <button
          title="查看全部路线"
          aria-label="查看全部路线"
          @click="fitAllRoutes"
        >
          <Crosshair :size="17" />
        </button>
        <button
          title="查看当前路线"
          aria-label="查看当前路线"
          @click="fitActiveRoute"
        >
          <Layers3 :size="17" />
        </button>
        <button
          :title="expanded ? '退出专注模式' : '进入专注模式'"
          :aria-label="expanded ? '退出专注模式' : '进入专注模式'"
          @click="toggleExpanded"
        >
          <Minimize2 v-if="expanded" :size="17" />
          <Maximize2 v-else :size="17" />
        </button>
      </div>

      <div v-if="!compact" class="map-legend">
        <span><i class="depot" />配送中心</span>
        <span><i class="town" />乡镇节点</span>
        <span><i class="village" />村级订单</span>
        <span><i class="line" />优化路线</span>
      </div>

      <aside v-if="!compact && selectedNode" class="node-inspector">
        <button aria-label="关闭节点详情" @click="selectedNodeId = undefined">
          <X :size="16" />
        </button>
        <small>{{
          selectedNode.kind === "depot"
            ? "配送中心"
            : selectedNode.kind === "village"
              ? "村级节点"
              : "乡镇节点"
        }}</small>
        <h3>{{ selectedNode.name }}</h3>
        <dl>
          <div>
            <dt>关联订单</dt>
            <dd>{{ selectedNodeOrders.length }} 单</dd>
          </div>
          <div>
            <dt>货量</dt>
            <dd>
              {{
                selectedNodeOrders
                  .reduce((sum, item) => sum + item.weight_kg, 0)
                  .toLocaleString("zh-CN")
              }}
              kg
            </dd>
          </div>
          <div>
            <dt>冷链订单</dt>
            <dd>
              {{
                selectedNodeOrders.filter((item) => item.cold_chain).length
              }}
              单
            </dd>
          </div>
          <div>
            <dt>坐标状态</dt>
            <dd>
              {{
                selectedNode.coordinate_status === "verified"
                  ? "已核验快照"
                  : selectedNode.coordinate_status === "needs_review"
                    ? "待复核快照"
                    : "未核验快照"
              }}
            </dd>
          </div>
          <div>
            <dt>地图坐标</dt>
            <dd>
              {{ coordinatesForNode(selectedNode)[0].toFixed(4) }},
              {{ coordinatesForNode(selectedNode)[1].toFixed(4) }}
            </dd>
          </div>
        </dl>
      </aside>

      <aside v-else-if="!compact && activeRoute" class="route-inspector">
        <div class="route-inspector-title">
          <i :style="{ background: palette[selectedRoute % palette.length] }" />
          <div>
            <small>当前路线</small>
            <h3>{{ activeRoute.plate }}</h3>
          </div>
          <span>{{ activeRoute.cold_chain ? "冷链运输" : "常温运输" }}</span>
        </div>
        <div class="route-inspector-metrics">
          <div>
            <span>节点</span
            ><b>{{ Math.max(0, activeRoute.stops.length - 2) }}</b>
          </div>
          <div>
            <span>装载率</span><b>{{ activeLoadRate }}%</b>
          </div>
          <div>
            <span>里程</span><b>{{ activeRoute.distance_km }} km</b>
          </div>
        </div>
        <div class="route-sequence">
          <span
            v-for="(stop, index) in activeRoute.stops.slice(1, -1)"
            :key="`${stop.node_id}-${index}`"
          >
            <i>{{ index + 1 }}</i
            >{{ stop.node_name }}
          </span>
        </div>
      </aside>

      <footer v-if="!compact" class="map-status">
        <span
          ><i />{{
            source === "amap" ? "道路底图在线" : "边界与业务数据离线可用"
          }}</span
        >
        <span v-if="source === 'amap'">道路级路线 · GCJ-02</span>
        <span
          >数据更新
          {{
            lastUpdated.toLocaleTimeString("zh-CN", {
              hour: "2-digit",
              minute: "2-digit",
            })
          }}</span
        >
        <span
          >{{ scenario.nodes.length }} 个节点 ·
          {{ result?.routes.length ?? 0 }} 条路线</span
        >
      </footer>
    </div>
  </section>
</template>

<style scoped>
.professional-map {
  height: 100%;
  min-height: 680px;
  display: grid;
  grid-template-rows: auto 1fr;
  color: #243a2f;
  background: #fff;
}
.professional-map.expanded {
  position: fixed;
  inset: 14px;
  z-index: 1200;
  min-height: 0;
  border: 1px solid #dbe4de;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 24px 80px rgba(9, 37, 24, 0.28);
}
.professional-map.compact {
  min-height: 0;
  display: block;
}
.professional-map.compact .map-canvas {
  height: 100%;
  min-height: 0;
}
.professional-map.compact .map-host {
  inset: 0;
}
.map-toolbar {
  min-height: 60px;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto auto;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  border-bottom: 1px solid #e1e7e3;
}
.map-heading h2 {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  font-size: 16px;
  color: #17382a;
}
.map-heading h2 svg {
  color: #16784d;
}
.map-heading p {
  margin: 4px 0 0;
  color: #7a8780;
  font-size: 10px;
}
.map-filters {
  display: flex;
  gap: 5px;
  flex: 0 0 auto;
  min-width: max-content;
}
.map-filters button,
.map-source button {
  height: 34px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid #dbe3de;
  border-radius: 7px;
  background: #fff;
  color: #53675b;
  font: 700 10px/1 inherit;
  cursor: pointer;
}
.map-filters button {
  flex: 0 0 auto;
  min-width: 58px;
  justify-content: center;
  white-space: nowrap;
  word-break: keep-all;
}
.map-filters button:first-child {
  min-width: 82px;
}
.map-filters button svg {
  flex: 0 0 auto;
}
.map-filters button:hover,
.map-filters button.active {
  border-color: #a9d0bb;
  background: #edf7f1;
  color: #126f48;
}
.map-source {
  display: flex;
  align-items: center;
  gap: 8px;
}
.map-source > span {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #5e7066;
  font-size: 10px;
  font-weight: 750;
  white-space: nowrap;
}
.map-source > span.calibration-state {
  padding-left: 8px;
  border-left: 1px solid #dfe6e1;
  color: #19784d;
  font-size: 9px;
}
.map-source > span.calibration-state.warning {
  color: #b66b12;
}
.map-source > span i,
.map-status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #87938c;
}
.map-source > span.amap i {
  background: #20a366;
  box-shadow: 0 0 0 3px #e2f3e9;
}
.map-source button {
  width: 34px;
  padding: 0;
  justify-content: center;
}
.map-canvas {
  position: relative;
  min-height: 600px;
  overflow: hidden;
  background: #eef2f0;
}
.map-host {
  position: absolute;
  inset: 0 0 28px;
}
.map-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  background: rgba(246, 249, 247, 0.92);
  color: #176f49;
  font-size: 12px;
}
.map-warning {
  position: absolute;
  left: 14px;
  top: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid #efd8b0;
  border-radius: 7px;
  background: #fff9ea;
  color: #986812;
  font-size: 10px;
}
.map-controls {
  position: absolute;
  right: 12px;
  top: 12px;
  display: flex;
  flex-direction: column;
  border: 1px solid #dce4df;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 4px 14px rgba(24, 54, 38, 0.09);
}
.map-controls button {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 0;
  border-bottom: 1px solid #e4e9e6;
  background: #fff;
  color: #3b5848;
  cursor: pointer;
}
.map-controls button:last-child {
  border: 0;
}
.map-controls button:hover {
  background: #eef6f1;
  color: #126e47;
}
.map-legend {
  position: absolute;
  left: 13px;
  bottom: 42px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 11px 12px;
  border: 1px solid #dbe3de;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 4px 14px rgba(24, 54, 38, 0.07);
  font-size: 9px;
  color: #596b61;
}
.map-legend span {
  display: flex;
  align-items: center;
  gap: 7px;
}
.map-legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.map-legend .depot {
  background: #0d5c3b;
  border-radius: 2px;
}
.map-legend .town {
  background: #168653;
}
.map-legend .village {
  background: #fff;
  border: 2px solid #168653;
}
.map-legend .line {
  width: 17px;
  height: 3px;
  border-radius: 2px;
  background: #2d6cdf;
}
.route-inspector,
.node-inspector {
  position: absolute;
  right: 58px;
  top: 13px;
  width: 275px;
  padding: 14px;
  border: 1px solid #dce4df;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 10px 28px rgba(22, 52, 36, 0.12);
  backdrop-filter: blur(8px);
}
.route-inspector-title {
  display: grid;
  grid-template-columns: 4px 1fr auto;
  gap: 10px;
  align-items: center;
}
.route-inspector-title > i {
  align-self: stretch;
  border-radius: 3px;
}
.route-inspector-title small,
.route-inspector-title h3 {
  display: block;
  margin: 0;
}
.route-inspector-title small {
  color: #87928c;
  font-size: 9px;
}
.route-inspector-title h3 {
  margin-top: 3px;
  font-size: 15px;
}
.route-inspector-title > span {
  padding: 4px 6px;
  border-radius: 5px;
  background: #eaf4ef;
  color: #176f49;
  font-size: 9px;
}
.route-inspector-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin: 12px 0;
  padding: 10px 0;
  border-top: 1px solid #e5eae7;
  border-bottom: 1px solid #e5eae7;
}
.route-inspector-metrics div {
  text-align: center;
  border-right: 1px solid #e6ebe8;
}
.route-inspector-metrics div:last-child {
  border: 0;
}
.route-inspector-metrics span,
.route-inspector-metrics b {
  display: block;
}
.route-inspector-metrics span {
  font-size: 8px;
  color: #89928d;
}
.route-inspector-metrics b {
  margin-top: 4px;
  font-size: 11px;
  color: #214434;
}
.route-sequence {
  max-height: 145px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.route-sequence span {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 9px;
  color: #586a60;
}
.route-sequence i {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #2d6cdf;
  color: #fff;
  font-style: normal;
  font-size: 8px;
}
.node-inspector > button {
  position: absolute;
  right: 8px;
  top: 8px;
  width: 27px;
  height: 27px;
  border: 0;
  background: transparent;
  color: #77847d;
  cursor: pointer;
}
.node-inspector > small {
  color: #17734b;
  font-size: 9px;
  font-weight: 750;
}
.node-inspector h3 {
  margin: 5px 0 12px;
  font-size: 16px;
}
.node-inspector dl {
  margin: 0;
}
.node-inspector dl > div {
  display: flex;
  justify-content: space-between;
  padding: 7px 0;
  border-top: 1px solid #e8ece9;
  font-size: 9px;
}
.node-inspector dt {
  color: #819087;
}
.node-inspector dd {
  margin: 0;
  color: #294737;
  font-weight: 700;
}
.map-status {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 28px;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 13px;
  border-top: 1px solid #dde5e0;
  background: rgba(255, 255, 255, 0.96);
  color: #7a8880;
  font-size: 8px;
}
.map-status span:first-child {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-right: auto;
}
.map-status span:first-child i {
  background: #20a366;
}
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
:global(.qz-map-marker) {
  width: 24px;
  height: 24px;
  border: 2px solid #fff;
  border-radius: 50%;
  background: #168653;
  color: #fff;
  font: 800 10px/20px Arial;
  box-shadow: 0 2px 7px rgba(17, 66, 42, 0.28);
  cursor: pointer;
}
:global(.qz-map-marker.amap-depot) {
  border-radius: 5px;
  background: #0c5738;
}
:global(.qz-map-marker.amap-node) {
  width: 15px;
  height: 15px;
  border: 3px solid #168653;
  background: #fff;
}
:global(.qz-fault-marker) {
  position: relative;
  width: 88px;
  height: 54px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  pointer-events: none;
}
:global(.qz-fault-marker__pulse) {
  position: absolute;
  left: 28px;
  top: 2px;
  width: 32px;
  height: 32px;
  border: 2px solid rgba(216, 78, 72, 0.72);
  border-radius: 50%;
  animation: qz-fault-pulse 1.8s ease-out infinite;
}
:global(.qz-fault-marker__pin) {
  position: relative;
  z-index: 2;
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border: 3px solid #fff;
  border-radius: 50%;
  background: #d84e48;
  box-shadow: 0 5px 15px rgba(113, 28, 25, 0.38);
}
:global(.qz-fault-marker__pin::after) {
  content: "";
  position: absolute;
  left: 10px;
  bottom: -8px;
  width: 7px;
  height: 10px;
  background: #d84e48;
  clip-path: polygon(0 0, 100% 0, 50% 100%);
}
:global(.qz-fault-marker svg) {
  width: 20px;
  height: 20px;
  overflow: visible;
  fill: none;
  stroke: #fff;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
:global(.qz-fault-marker strong) {
  position: absolute;
  z-index: 3;
  left: 8px;
  top: 39px;
  min-width: 72px;
  padding: 4px 7px;
  border: 1px solid rgba(255, 255, 255, 0.92);
  border-radius: 5px;
  background: #b83e39;
  color: #fff;
  box-shadow: 0 3px 10px rgba(113, 28, 25, 0.24);
  font: 800 10px/1 "Microsoft YaHei", sans-serif;
  text-align: center;
  white-space: nowrap;
}
@keyframes qz-fault-pulse {
  0% {
    transform: scale(0.7);
    opacity: 0.9;
  }
  70%,
  100% {
    transform: scale(1.65);
    opacity: 0;
  }
}
@media (max-width: 1000px) {
  .map-toolbar {
    grid-template-columns: 1fr auto;
  }
  .map-heading {
    grid-column: 1/-1;
  }
  .map-filters {
    min-width: 0;
    max-width: 100%;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .map-filters::-webkit-scrollbar {
    display: none;
  }
  .route-inspector {
    width: 225px;
  }
}
@media (max-width: 760px) {
  .professional-map:not(.compact) {
    min-height: 720px;
  }
  .professional-map.expanded {
    inset: 6px;
  }
  .map-toolbar {
    display: flex;
    align-items: stretch;
    flex-direction: column;
    padding: 11px;
  }
  .map-filters {
    display: grid;
    grid-template-columns: 1fr 1fr;
    width: 100%;
    overflow: visible;
  }
  .map-filters button {
    min-width: 0;
    justify-content: center;
    white-space: nowrap;
  }
  .map-source {
    justify-content: space-between;
    flex-wrap: wrap;
  }
  .professional-map:not(.compact) .map-canvas {
    min-height: 520px;
  }
  .route-inspector,
  .node-inspector {
    left: 12px;
    right: 56px;
    top: 12px;
    width: auto;
  }
  .map-legend {
    display: none;
  }
  .map-status span:nth-child(2),
  .map-status span:nth-child(3) {
    display: none;
  }
}
</style>
