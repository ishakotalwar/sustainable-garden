import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Dimensions,
  Image,
  PanResponder,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

type Rating = 'Low' | 'Medium' | 'High';
type Region = string;

type ClimateProfile = {
  id: string;
  label: string;
  zone: string;
  region: Region;
};

type Plant = {
  id: string;
  name: string;
  emoji: string;
  zones: string[];
  nativeRegions: Region[];
  waterUsage: Rating;
  pollinatorValue: Rating;
  carbonSequestration: Rating;
  shadeCoverage: Rating;
  droughtResistance: Rating;
};

type PlacedPlant = {
  instanceId: string;
  plantId: string;
  x: number;
  y: number;
  size: number;
};

type SustainabilityMetrics = {
  sustainabilityScore: number;
  waterEfficiency: number;
  pollinatorSupport: number;
  nativePercent: number;
  droughtResistance: number;
  biodiversity: number;
  carbonImpact: number;
  weeklyWaterDemand: number;
};

type ApiConfigResponse = {
  climateOptions: ClimateProfile[];
  plantLibrary: Plant[];
  integrations?: {
    flora?: { enabled?: boolean; baseUrl?: string };
    llm?: { enabled?: boolean; provider?: string; model?: string | null };
  };
};

type ApiRecommendationsResponse = {
  climate: ClimateProfile;
  plants: Plant[];
  zipCode?: string;
  state?: string;
  source?: 'flora' | 'local';
  floraEnabled?: boolean;
  plantType?: string | null;
  filterRelaxed?: boolean;
  strictMatchCount?: number;
  selectionMethod?: 'llm' | 'heuristic' | string;
  candidateCount?: number;
  candidatePoolCount?: number;
  curatedCount?: number;
  llmEnabled?: boolean;
  llmModel?: string | null;
  llmError?: string | null;
  error?: string;
  detail?: string;
};

type ApiScoreResponse = {
  climate: ClimateProfile;
  metrics: SustainabilityMetrics;
};

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:5001';
const SCREEN_HEIGHT = Dimensions.get('window').height;
const SCREEN_WIDTH = Dimensions.get('window').width;
const MIN_CANVAS_SIZE = 220;
const MAX_CANVAS_HEIGHT = Math.max(MIN_CANVAS_SIZE, Math.min(640, SCREEN_HEIGHT * 0.62));
const DEFAULT_CANVAS_SIZE = Math.max(MIN_CANVAS_SIZE, Math.min(420, SCREEN_WIDTH - 28));

const DEFAULT_CLIMATE_OPTIONS: ClimateProfile[] = [
  { id: 'irvine', label: 'Irvine, CA', zone: '10a', region: 'CA' },
  { id: 'santa-barbara', label: 'Santa Barbara, CA', zone: '9b', region: 'CA' },
  { id: 'phoenix', label: 'Phoenix, AZ', zone: '10b', region: 'Southwest' },
  { id: 'seattle', label: 'Seattle, WA', zone: '8b', region: 'PacificNW' },
];

const DEFAULT_PLANT_LIBRARY: Plant[] = [
  { id: 'ceanothus', name: 'California Lilac', emoji: '🪻', zones: ['8b','9b','10a'], nativeRegions: ['CA'], waterUsage: 'Low', pollinatorValue: 'High', carbonSequestration: 'Medium', shadeCoverage: 'Medium', droughtResistance: 'High' },
  { id: 'toyon', name: 'Toyon', emoji: '🌿', zones: ['8b','9b','10a'], nativeRegions: ['CA'], waterUsage: 'Low', pollinatorValue: 'High', carbonSequestration: 'High', shadeCoverage: 'Medium', droughtResistance: 'High' },
  { id: 'manzanita', name: 'Manzanita', emoji: '🪴', zones: ['8b','9b','10a'], nativeRegions: ['CA'], waterUsage: 'Low', pollinatorValue: 'Medium', carbonSequestration: 'Medium', shadeCoverage: 'Low', droughtResistance: 'High' },
  { id: 'yarrow', name: 'Yarrow', emoji: '🌼', zones: ['8b','9b','10a','10b'], nativeRegions: ['CA','PacificNW'], waterUsage: 'Low', pollinatorValue: 'High', carbonSequestration: 'Low', shadeCoverage: 'Low', droughtResistance: 'High' },
  { id: 'milkweed', name: 'Narrowleaf Milkweed', emoji: '🐝', zones: ['9b','10a','10b'], nativeRegions: ['CA','Southwest'], waterUsage: 'Medium', pollinatorValue: 'High', carbonSequestration: 'Medium', shadeCoverage: 'Low', droughtResistance: 'Medium' },
  { id: 'lavender', name: 'Lavender', emoji: '💜', zones: ['8b','9b','10a','10b'], nativeRegions: ['CA','Southwest'], waterUsage: 'Low', pollinatorValue: 'High', carbonSequestration: 'Medium', shadeCoverage: 'Low', droughtResistance: 'High' },
  { id: 'sage', name: 'White Sage', emoji: '🌱', zones: ['8b','9b','10a','10b'], nativeRegions: ['CA','Southwest'], waterUsage: 'Low', pollinatorValue: 'High', carbonSequestration: 'Low', shadeCoverage: 'Low', droughtResistance: 'High' },
  { id: 'oregon-grape', name: 'Oregon Grape', emoji: '🍃', zones: ['8b','9b'], nativeRegions: ['PacificNW'], waterUsage: 'Medium', pollinatorValue: 'Medium', carbonSequestration: 'Medium', shadeCoverage: 'Medium', droughtResistance: 'Medium' },
  { id: 'dwarf-citrus', name: 'Dwarf Citrus', emoji: '🍋', zones: ['9b','10a','10b'], nativeRegions: ['Southeast'], waterUsage: 'High', pollinatorValue: 'Medium', carbonSequestration: 'High', shadeCoverage: 'Medium', droughtResistance: 'Low' },
];

const WATER_EFFICIENCY_POINTS: Record<Rating, number> = { Low: 100, Medium: 70, High: 35 };
const RATING_POINTS: Record<Rating, number> = { Low: 40, Medium: 70, High: 100 };
const WATER_UNITS: Record<Rating, number> = { Low: 1, Medium: 2, High: 3 };

const EMPTY_METRICS: SustainabilityMetrics = {
  sustainabilityScore: 0, waterEfficiency: 0, pollinatorSupport: 0,
  nativePercent: 0, droughtResistance: 0, biodiversity: 0,
  carbonImpact: 0, weeklyWaterDemand: 0,
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function normalizeZipCode(rawValue: string): string | null {
  const digitsOnly = rawValue.replace(/\D/g, '');
  return digitsOnly.length < 5 ? null : digitsOnly.slice(0, 5);
}

function mergePlantLists(currentPlants: Plant[], incomingPlants: Plant[]): Plant[] {
  const merged = new Map<string, Plant>();
  for (const plant of currentPlants) merged.set(plant.id, plant);
  for (const plant of incomingPlants) merged.set(plant.id, plant);
  return Array.from(merged.values());
}

function describeScore(score: number): string {
  if (score >= 85) return 'Excellent';
  if (score >= 70) return 'High';
  if (score >= 55) return 'Moderate';
  return 'Needs work';
}

function scoreColor(score: number): string {
  if (score >= 85) return '#4a7c3f';
  if (score >= 70) return '#6a9e55';
  if (score >= 55) return '#b8860b';
  return '#b5451b';
}

function weightedAverage(values: number[], weights: number[]): number {
  if (values.length === 0) return 0;
  const weightTotal = weights.reduce((s, v) => s + v, 0);
  if (weightTotal <= 0) return 0;
  return values.reduce((s, v, i) => s + v * (weights[i] ?? 0), 0) / weightTotal;
}

function computeMetrics(
  placedPlants: PlacedPlant[],
  plantsById: Record<string, Plant>,
  climate: ClimateProfile
): SustainabilityMetrics {
  const resolved = placedPlants
    .map(pp => { const p = plantsById[pp.plantId]; return p ? { plant: p, weight: clamp(pp.size / 56, 0.6, 2.4) } : null; })
    .filter((e): e is { plant: Plant; weight: number } => Boolean(e));
  if (resolved.length === 0) return EMPTY_METRICS;
  const plants = resolved.map(e => e.plant);
  const weights = resolved.map(e => e.weight);
  const weightTotal = weights.reduce((s, v) => s + v, 0);
  const waterEfficiency = Math.round(weightedAverage(plants.map(p => WATER_EFFICIENCY_POINTS[p.waterUsage]), weights));
  const pollinatorSupport = Math.round(weightedAverage(plants.map(p => RATING_POINTS[p.pollinatorValue]), weights));
  const droughtResistance = Math.round(weightedAverage(plants.map(p => RATING_POINTS[p.droughtResistance]), weights));
  const carbonImpact = Math.round(weightedAverage(plants.map(p => RATING_POINTS[p.carbonSequestration]), weights));
  const nativeWeight = resolved
    .filter(e => e.plant.nativeRegions.includes(climate.region) || e.plant.nativeRegions.includes('native'))
    .reduce((s, e) => s + e.weight, 0);
  const nativePercent = weightTotal > 0 ? Math.round((nativeWeight / weightTotal) * 100) : 0;
  const uniqueSpecies = new Set(plants.map(p => p.id)).size;
  const biodiversity = Math.round(clamp((uniqueSpecies / plants.length) * 70 + Math.min(uniqueSpecies, 6) * 5 + 25, 0, 100));
  const weeklyWaterDemand = Math.round(resolved.reduce((s, e) => s + WATER_UNITS[e.plant.waterUsage] * e.weight, 0));
  const sustainabilityScore = Math.round(
    nativePercent * 0.28 + waterEfficiency * 0.24 + pollinatorSupport * 0.16 +
    droughtResistance * 0.14 + biodiversity * 0.1 + carbonImpact * 0.08
  );
  return { sustainabilityScore, waterEfficiency, pollinatorSupport, nativePercent, droughtResistance, biodiversity, carbonImpact, weeklyWaterDemand };
}

function defaultClimate(options: ClimateProfile[]): ClimateProfile {
  return options[0] ?? DEFAULT_CLIMATE_OPTIONS[0];
}

// type DraggablePlantProps = {
//   item: PlacedPlant; plant: Plant; selected: boolean;
//   canvasWidth: number; canvasHeight: number;
//   onMove: (id: string, x: number, y: number) => void;
//   onSelect: (id: string) => void;
// };

// function DraggablePlant({ item, plant, selected, canvasWidth, canvasHeight, onMove, onSelect }: DraggablePlantProps) {
//   const dragOrigin = useRef({ x: item.x, y: item.y });
//   const panResponder = useMemo(() =>
//     PanResponder.create({
//       onStartShouldSetPanResponder: () => true,
//       onMoveShouldSetPanResponder: () => true,
//       onPanResponderGrant: () => { dragOrigin.current = { x: item.x, y: item.y }; onSelect(item.instanceId); },
//       onPanResponderMove: (_e, g) => {
//         onMove(item.instanceId,
//           clamp(dragOrigin.current.x + g.dx, 0, Math.max(0, canvasWidth - item.size)),
//           clamp(dragOrigin.current.y + g.dy, 0, Math.max(0, canvasHeight - item.size)));
//       },
//     }), [canvasHeight, canvasWidth, item.instanceId, item.size, item.x, item.y, onMove, onSelect]);

//   return (
//     <View {...panResponder.panHandlers}
//       style={[styles.placedPlant, selected && styles.placedPlantSelected,
//         { left: item.x, top: item.y, width: item.size, height: item.size }]}>
//       <Text style={{ fontSize: item.size * 0.42 }}>{plant.emoji}</Text>
//     </View>
//   );
// }
type DraggablePlantProps = {
  item: PlacedPlant; plant: Plant; selected: boolean;
  canvasWidth: number; canvasHeight: number;
  onMove: (id: string, x: number, y: number) => void;
  onSelect: (id: string) => void;
};

function DraggablePlant({ item, plant, selected, canvasWidth, canvasHeight, onMove, onSelect }: DraggablePlantProps) {
  const sizeRef = useRef(item.size);
  const canvasRef = useRef({ width: canvasWidth, height: canvasHeight });
  const dragState = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);
  const viewRef = useRef<any>(null);

  useEffect(() => { sizeRef.current = item.size; }, [item.size]);
  useEffect(() => { canvasRef.current = { width: canvasWidth, height: canvasHeight }; }, [canvasWidth, canvasHeight]);

  // Web: use pointer events with capture so mouseup always fires
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const el = viewRef.current as HTMLElement | null;
    if (!el) return;

    function onPointerDown(e: PointerEvent) {
      e.preventDefault();
      el!.setPointerCapture(e.pointerId); // 👈 this is the key — captures all pointer events including mouseup anywhere on screen
      dragState.current = { startX: e.clientX, startY: e.clientY, originX: item.x, originY: item.y };
      onSelect(item.instanceId);
      el!.style.cursor = 'grabbing';
    }

    function onPointerMove(e: PointerEvent) {
      if (!dragState.current) return;
      const dx = e.clientX - dragState.current.startX;
      const dy = e.clientY - dragState.current.startY;
      const { width, height } = canvasRef.current;
      const size = sizeRef.current;
      onMove(
        item.instanceId,
        clamp(dragState.current.originX + dx, 0, Math.max(0, width - size)),
        clamp(dragState.current.originY + dy, 0, Math.max(0, height - size)),
      );
    }

    function onPointerUp(e: PointerEvent) {
      dragState.current = null;
      el!.style.cursor = 'grab';
    }

    el.style.cursor = 'grab';
    el.addEventListener('pointerdown', onPointerDown);
    el.addEventListener('pointermove', onPointerMove);
    el.addEventListener('pointerup', onPointerUp);
    el.addEventListener('pointercancel', onPointerUp);

    return () => {
      el.removeEventListener('pointerdown', onPointerDown);
      el.removeEventListener('pointermove', onPointerMove);
      el.removeEventListener('pointerup', onPointerUp);
      el.removeEventListener('pointercancel', onPointerUp);
    };
  }, [item.instanceId, item.x, item.y, onMove, onSelect]); // x/y here is fine — we only read them on pointerdown

  // Native: keep PanResponder for iOS/Android
  const panResponder = useMemo(() => {
    if (Platform.OS === 'web') return { panHandlers: {} };
    return PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        dragState.current = { startX: 0, startY: 0, originX: item.x, originY: item.y };
        onSelect(item.instanceId);
      },
      onPanResponderMove: (_e, g) => {
        if (!dragState.current) return;
        const { width, height } = canvasRef.current;
        const size = sizeRef.current;
        onMove(
          item.instanceId,
          clamp(dragState.current.originX + g.dx, 0, Math.max(0, width - size)),
          clamp(dragState.current.originY + g.dy, 0, Math.max(0, height - size)),
        );
      },
      onPanResponderRelease: () => { dragState.current = null; },
      onPanResponderTerminate: () => { dragState.current = null; },
    });
  }, [item.instanceId, item.x, item.y, onMove, onSelect]);

  return (
    <View
      ref={viewRef}
      {...panResponder.panHandlers}
      style={[
        styles.placedPlant,
        selected && styles.placedPlantSelected,
        { left: item.x, top: item.y, width: item.size, height: item.size },
      ]}
    >
      <Text style={{ fontSize: item.size * 0.42 }}>{plant.emoji}</Text>
    </View>
  );
}
export default function HomeScreen() {
  const [selectedClimateId, setSelectedClimateId] = useState(defaultClimate(DEFAULT_CLIMATE_OPTIONS).id);
  const [placedPlants, setPlacedPlants] = useState<PlacedPlant[]>([]);
  const [selectedPlantId, setSelectedPlantId] = useState<string | null>(null);
  const [zipCodeInput, setZipCodeInput] = useState('');
  const [activeZipCode, setActiveZipCode] = useState<string | null>(null);
  const [zipLookupLoading, setZipLookupLoading] = useState(false);
  const [zipLookupMessage, setZipLookupMessage] = useState<string | null>(null);
  const [zipLookupError, setZipLookupError] = useState(false);
  const [canvasImageInput, setCanvasImageInput] = useState('');
  const [canvasImageUri, setCanvasImageUri] = useState<string | null>(null);
  const [canvasImageMessage, setCanvasImageMessage] = useState<string | null>(null);
  const [canvasImageHasError, setCanvasImageHasError] = useState(false);
  const [canvasDimensions, setCanvasDimensions] = useState({ width: DEFAULT_CANVAS_SIZE, height: DEFAULT_CANVAS_SIZE });
  const [canvasShellWidth, setCanvasShellWidth] = useState<number | null>(null);
  const uploadedObjectUrlRef = useRef<string | null>(null);
  const scrollRef = useRef<ScrollView>(null);
  const [climateOptions, setClimateOptions] = useState<ClimateProfile[]>(DEFAULT_CLIMATE_OPTIONS);
  const [plantLibrary, setPlantLibrary] = useState<Plant[]>(DEFAULT_PLANT_LIBRARY);
  const [recommendations, setRecommendations] = useState<Plant[]>([]);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'offline'>('checking');
  const [backendMessage, setBackendMessage] = useState('Connecting to Flask API...');
  const [apiMetrics, setApiMetrics] = useState<SustainabilityMetrics | null>(null);

  const selectedClimate = useMemo(
    () => climateOptions.find(p => p.id === selectedClimateId) ?? defaultClimate(climateOptions),
    [climateOptions, selectedClimateId]
  );
  const canvasWidth = canvasDimensions.width;
  const canvasHeight = canvasDimensions.height;
  const plantsById = useMemo(() =>
    plantLibrary.reduce<Record<string, Plant>>((acc, p) => { acc[p.id] = p; return acc; }, {}), [plantLibrary]);
  const fallbackMetrics = useMemo(() =>
    computeMetrics(placedPlants, plantsById, selectedClimate), [placedPlants, plantsById, selectedClimate]);
  const metrics = useMemo(() => apiMetrics ?? fallbackMetrics, [apiMetrics, fallbackMetrics]);
  const scoreSignature = useMemo(() =>
    placedPlants.map(p => `${p.plantId}:${Math.round(p.size)}`).join('|'), [placedPlants]);
  const selectedPlant = placedPlants.find(p => p.instanceId === selectedPlantId) ?? null;
  const selectedPlantDetails = selectedPlant ? plantsById[selectedPlant.plantId] : null;
  const shouldShowCanvas = Boolean(canvasImageUri) || placedPlants.length > 0;

  useEffect(() => {
    let cancelled = false;
    async function loadConfig() {
      try {
        const res = await fetch(`${API_BASE_URL}/api/config`);
        if (!res.ok) throw new Error();
        const payload = await res.json() as ApiConfigResponse;
        if (cancelled) return;
        const nextClimate = payload.climateOptions?.length ? payload.climateOptions : DEFAULT_CLIMATE_OPTIONS;
        const nextPlants = payload.plantLibrary?.length ? payload.plantLibrary : DEFAULT_PLANT_LIBRARY;
        setClimateOptions(nextClimate); setPlantLibrary(nextPlants);
        setSelectedClimateId(id => nextClimate.some(p => p.id === id) ? id : defaultClimate(nextClimate).id);
        setBackendStatus('connected'); setBackendMessage(`Connected to Flask API (${API_BASE_URL})`);
      } catch {
        if (cancelled) return;
        setClimateOptions(DEFAULT_CLIMATE_OPTIONS); setPlantLibrary(DEFAULT_PLANT_LIBRARY);
        setBackendStatus('offline'); setBackendMessage('Flask API not reachable. Using local fallback model.');
      }
    }
    loadConfig();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (backendStatus !== 'connected') { setApiMetrics(null); return; }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/score`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            climateId: selectedClimate.id,
            placedPlants: scoreSignature
              ? scoreSignature.split('|').map(e => { const [plantId, sizeValue] = e.split(':'); return { plantId, size: Number(sizeValue) }; })
              : [],
          }),
        });
        if (!res.ok) throw new Error();
        const payload = await res.json() as ApiScoreResponse;
        if (cancelled) return;
        setApiMetrics(payload.metrics);
      } catch {
        if (cancelled) return;
        setApiMetrics(null); setBackendStatus('offline'); setBackendMessage('Score API offline. Using local scoring model.');
      }
    }, 120);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [backendStatus, scoreSignature, selectedClimate.id]);

  useEffect(() => {
    setPlacedPlants(curr => {
      let changed = false;
      const next = curr.map(p => {
        const nx = clamp(p.x, 0, Math.max(0, canvasWidth - p.size));
        const ny = clamp(p.y, 0, Math.max(0, canvasHeight - p.size));
        if (nx === p.x && ny === p.y) return p;
        changed = true; return { ...p, x: nx, y: ny };
      });
      return changed ? next : curr;
    });
  }, [canvasHeight, canvasWidth]);

  useEffect(() => {
    return () => {
      const url = uploadedObjectUrlRef.current;
      const g = globalThis as { URL?: { revokeObjectURL?: (u: string) => void } };
      if (url && g.URL?.revokeObjectURL) g.URL.revokeObjectURL(url);
      uploadedObjectUrlRef.current = null;
    };
  }, []);

  function addPlantToCanvas(plant: Plant) {
    const size = 56;
    const instanceId = `${plant.id}-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
    setPlacedPlants(curr => {
      const i = curr.length;
      return [...curr, {
        instanceId, plantId: plant.id,
        x: clamp(16 + (i % 4) * (size + 12), 0, Math.max(0, canvasWidth - size)),
        y: clamp(16 + Math.floor(i / 4) * (size + 12), 0, Math.max(0, canvasHeight - size)),
        size,
      }];
    });
    setSelectedPlantId(instanceId);
  }

  function movePlant(instanceId: string, x: number, y: number) {
    setPlacedPlants(curr => curr.map(p => (p.instanceId !== instanceId || (p.x === x && p.y === y)) ? p : { ...p, x, y }));
  }

  function resizeSelectedPlant(delta: number) {
    if (!selectedPlantId) return;
    setPlacedPlants(curr => curr.map(p => {
      if (p.instanceId !== selectedPlantId) return p;
      const ns = clamp(p.size + delta, 34, 120);
      return { ...p, size: ns, x: clamp(p.x, 0, Math.max(0, canvasWidth - ns)), y: clamp(p.y, 0, Math.max(0, canvasHeight - ns)) };
    }));
  }

  function removeSelectedPlant() {
    if (!selectedPlantId) return;
    setPlacedPlants(c => c.filter(p => p.instanceId !== selectedPlantId));
    setSelectedPlantId(null);
  }

  function clearCanvas() { setPlacedPlants([]); setSelectedPlantId(null); }

  function clearUploadedObjectUrl() {
    const url = uploadedObjectUrlRef.current;
    const g = globalThis as { URL?: { revokeObjectURL?: (u: string) => void } };
    if (url && g.URL?.revokeObjectURL) g.URL.revokeObjectURL(url);
    uploadedObjectUrlRef.current = null;
  }

  const getMaxCanvasWidth = useCallback((): number => {
    const shellWidth = canvasShellWidth ?? Math.min(900, SCREEN_WIDTH - 32);
    return Math.max(120, Math.floor(shellWidth - 18));
  }, [canvasShellWidth]);

  function fitCanvasToImage(sourceWidth: number, sourceHeight: number) {
    if (!Number.isFinite(sourceWidth) || !Number.isFinite(sourceHeight) || sourceWidth <= 0 || sourceHeight <= 0) {
      return;
    }
    const maxCanvasWidth = getMaxCanvasWidth();
    const scale = Math.min(1, maxCanvasWidth / sourceWidth, MAX_CANVAS_HEIGHT / sourceHeight);

    const width = Math.round(sourceWidth * scale);
    const height = Math.round(sourceHeight * scale);

    setCanvasDimensions({
      width: Math.max(1, width),
      height: Math.max(1, height),
    });
  }

  useEffect(() => {
    const maxCanvasWidth = getMaxCanvasWidth();
    setCanvasDimensions(current => {
      if (current.width <= maxCanvasWidth) {
        return current;
      }
      const scale = maxCanvasWidth / current.width;
      return {
        width: Math.max(1, Math.round(current.width * scale)),
        height: Math.max(1, Math.round(current.height * scale)),
      };
    });
  }, [getMaxCanvasWidth]);

  useEffect(() => {
    if (canvasImageUri || placedPlants.length > 0) {
      return;
    }
    const expandedWidth = getMaxCanvasWidth();
    setCanvasDimensions(current => {
      if (current.width === expandedWidth && current.height === MAX_CANVAS_HEIGHT) {
        return current;
      }
      return { width: expandedWidth, height: MAX_CANVAS_HEIGHT };
    });
  }, [canvasImageUri, placedPlants.length, getMaxCanvasWidth]);

  async function probeImageDimensions(uri: string): Promise<{ width: number; height: number } | null> {
    if (!uri) {
      return null;
    }

    if (Platform.OS === 'web') {
      const browserImageCtor = (globalThis as { Image?: new () => any }).Image;
      if (!browserImageCtor) {
        return null;
      }
      return new Promise(resolve => {
        const browserImage = new browserImageCtor();
        browserImage.onload = () => {
          const width = Number(browserImage.naturalWidth || browserImage.width);
          const height = Number(browserImage.naturalHeight || browserImage.height);
          if (Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0) {
            resolve({ width, height });
            return;
          }
          resolve(null);
        };
        browserImage.onerror = () => resolve(null);
        browserImage.src = uri;
      });
    }

    return new Promise(resolve => {
      Image.getSize(
        uri,
        (width, height) => resolve({ width, height }),
        () => resolve(null)
      );
    });
  }

  async function syncCanvasToImage(uri: string) {
    const dimensions = await probeImageDimensions(uri);
    if (!dimensions) {
      return;
    }
    fitCanvasToImage(dimensions.width, dimensions.height);
  }

  function applyCanvasImage() {
    const nextUri = canvasImageInput.trim();
    if (!nextUri) { setCanvasImageMessage('Enter an image URL first.'); setCanvasImageHasError(true); return; }
    const valid = nextUri.startsWith('https://') || nextUri.startsWith('http://') || nextUri.startsWith('data:image/') || nextUri.startsWith('file://');
    if (!valid) { setCanvasImageMessage('Use a valid URL (https://...) or data:image/... value.'); setCanvasImageHasError(true); return; }
    clearUploadedObjectUrl();
    setCanvasImageUri(nextUri);
    setCanvasImageMessage('Loading backyard image...');
    setCanvasImageHasError(false);
    void syncCanvasToImage(nextUri);
  }

  function uploadCanvasImageFromDevice() {
    if (Platform.OS !== 'web') { setCanvasImageMessage('Device upload is available on web/laptop mode.'); setCanvasImageHasError(true); return; }
    const doc = (globalThis as { document?: { createElement?: (tag: string) => any } }).document;
    const g = globalThis as { URL?: { createObjectURL?: (f: any) => string; revokeObjectURL?: (u: string) => void } };
    if (!doc?.createElement || !g.URL?.createObjectURL) { setCanvasImageMessage('Upload not available in this environment.'); setCanvasImageHasError(true); return; }
    const fi = doc.createElement('input');
    fi.type = 'file'; fi.accept = 'image/*';
    fi.onchange = () => {
      const f = fi.files?.[0] as { name?: string } | undefined;
      if (!f) return;
      const url = g.URL!.createObjectURL!(f);
      clearUploadedObjectUrl(); uploadedObjectUrlRef.current = url;
      setCanvasImageInput(f.name ?? 'local-image'); setCanvasImageUri(url);
      setCanvasImageMessage(`Loaded: ${f.name ?? 'image'}`); setCanvasImageHasError(false);
      void syncCanvasToImage(url);
    };
    fi.click();
  }

  function removeCanvasImage() {
    clearUploadedObjectUrl();
    setCanvasImageUri(null);
    setCanvasImageInput('');
    setCanvasImageMessage(null);
    setCanvasImageHasError(false);
    setCanvasDimensions({ width: getMaxCanvasWidth(), height: MAX_CANVAS_HEIGHT });
  }

  async function lookupZipRecommendations() {
    const zip = normalizeZipCode(zipCodeInput);
    if (!zip) { setZipLookupMessage('Enter a valid 5-digit ZIP code.'); setZipLookupError(true); return; }
    setZipLookupLoading(true); setZipLookupError(false);
    setZipLookupMessage('Looking up Flora recommendations...');
    try {
      const res = await fetch(`${API_BASE_URL}/api/recommendations/zipcode?zipCode=${encodeURIComponent(zip)}`);
      const payload = await res.json() as ApiRecommendationsResponse;
      if (!res.ok || payload.error) throw new Error(payload.detail || payload.error || `ZIP lookup failed (${res.status}).`);
      if (!payload.plants?.length) throw new Error('No Flora recommendations returned for this ZIP code.');
      setPlantLibrary(curr => mergePlantLists(curr, payload.plants));
      setClimateOptions(curr => { const f = curr.filter(p => p.id !== payload.climate.id); return [payload.climate, ...f]; });
      setSelectedClimateId(payload.climate.id); setRecommendations(payload.plants); setActiveZipCode(zip); setZipCodeInput(zip);
      setZipLookupError(false);
      setZipLookupMessage(null);
      setBackendStatus('connected'); setBackendMessage(`Connected to Flask API (${API_BASE_URL})`);
    } catch (err) {
      setRecommendations([]); setActiveZipCode(null); setZipLookupError(true);
      setZipLookupMessage(err instanceof Error ? err.message : 'ZIP lookup failed.');
    } finally { setZipLookupLoading(false); }
  }

  const statusDotColor = backendStatus === 'connected' ? '#86c966' : backendStatus === 'checking' ? '#e8c96a' : '#e07a5f';

  return (
    <ScrollView ref={scrollRef} style={styles.page} contentContainerStyle={styles.pageContent} showsVerticalScrollIndicator={false}>

      {/* HERO — full screen height */}
      <View style={styles.hero}>
        <Image
          source={{ uri: 'https://cdn.prod.website-files.com/640b68693c13566914b5f6aa/661d4e6c1d53dc6ff89f734a_ladnscaping.jpg' }}
          style={styles.heroBgImage}
          resizeMode="cover"
        />
        <View style={styles.heroOverlay} />
        <View style={[styles.heroDot, { backgroundColor: statusDotColor }]} />
        <View style={styles.heroCenter}>
          <Text style={styles.heroEyebrow}>EcoScape</Text>
          <Text style={styles.heroTitle}>Design Your{'\n'}Dream Garden</Text>
          <Text style={styles.heroSub}>
            Build a sustainable garden and see your eco impact!
          </Text>
        </View>
        <Pressable style={styles.getStartedBtn} onPress={() => scrollRef.current?.scrollTo({ y: SCREEN_HEIGHT, animated: true })}>
          <Text style={styles.getStartedText}>Get Started ↓</Text>
        </Pressable>
      </View>

      {/* 1. GARDEN SETUP */}
      <View style={styles.sectionCard}>
        <View style={styles.sectionTitleRow}>
          <View style={styles.sectionNumBadge}><Text style={styles.sectionNum}>1</Text></View>
          <Text style={styles.sectionTitle}>Garden Setup</Text>
        </View>
        <Text style={styles.hint}>Enter ZIP code to fetch plant recommendations based on your climate.</Text>
        <Text style={styles.fieldLabel}>ZIP Code  <Text style={styles.fieldLabelMuted}>(Flora API)</Text></Text>
        <View style={styles.zipRow}>
          <TextInput
            value={zipCodeInput}
            onChangeText={setZipCodeInput}
            keyboardType="number-pad"
            maxLength={10}
            style={styles.zipInput}
            placeholder="e.g. 94102"
          />
          <Pressable onPress={lookupZipRecommendations} style={[styles.zipBtn, zipLookupLoading && styles.zipBtnDisabled]} disabled={zipLookupLoading}>
            <Text style={styles.zipBtnText}>{zipLookupLoading ? 'Loading…' : 'Use ZIP'}</Text>
          </Pressable>
        </View>
        {zipLookupMessage
          ? <Text style={zipLookupError ? styles.msgError : styles.msgInfo}>{zipLookupMessage}</Text>
          : <Text style={styles.hint}></Text>}
      </View>

      {/* 2. GARDEN STUDIO */}
      <View style={styles.sectionCard}>
        <View style={styles.sectionTitleRow}>
          <View style={styles.sectionNumBadge}><Text style={styles.sectionNum}>2</Text></View>
          <View style={{ flex: 1, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={styles.sectionTitle}>Garden Studio</Text>
            <Pressable onPress={clearCanvas} style={styles.clearBtn}>
              <Text style={styles.clearBtnText}>Clear canvas</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.workspaceRow}>
          <View style={[styles.workspacePanel, styles.workspacePlantsPanel]}>
            <Text style={styles.workspacePanelTitle}>Pick Plants</Text>
            <Text style={styles.hint}>
              {activeZipCode
                ? `Top picks for ZIP ${activeZipCode}.`
                : 'Load ZIP recommendations, then add plants to canvas.'}
            </Text>
            {recommendations.length === 0 ? (
              <View style={styles.emptyCard}>
                <Text style={styles.emptyEmoji}>🌾</Text>
                <Text style={styles.emptyText}>No recommendations yet.{'\n'}Enter a ZIP and tap Use ZIP.</Text>
              </View>
            ) : (
              <ScrollView
                style={[styles.sidePlantScroll, { maxHeight: Math.max(320, canvasHeight + 10) }]}
                contentContainerStyle={styles.sidePlantList}
                showsVerticalScrollIndicator={false}>
                {recommendations.map(plant => {
                  const isNative = plant.nativeRegions.length > 0;
                  return (
                    <View key={plant.id} style={styles.sidePlantCard}>
                      <View style={[styles.nativeBadge, isNative ? styles.nativeBadgeYes : styles.nativeBadgeNo]}>
                        <Text style={styles.nativeBadgeText}>{isNative ? 'Native' : 'Adaptive'}</Text>
                      </View>
                      <Text style={styles.plantEmoji}>{plant.emoji}</Text>
                      <Text style={styles.plantName}>{plant.name}</Text>
                      <View style={styles.plantTags}>
                        <Text style={styles.plantTag}>💧 {plant.waterUsage}</Text>
                        <Text style={styles.plantTag}>🐝 {plant.pollinatorValue}</Text>
                        <Text style={styles.plantTag}>☀️ {plant.droughtResistance}</Text>
                      </View>
                      <Pressable style={styles.addBtn} onPress={() => addPlantToCanvas(plant)}>
                        <Text style={styles.addBtnText}>+ Add to Canvas</Text>
                      </Pressable>
                    </View>
                  );
                })}
              </ScrollView>
            )}
          </View>

          <View style={[styles.workspacePanel, styles.workspaceCanvasPanel]}>
            <View style={styles.imageBlock}>
              <Text style={styles.fieldLabel}>Backyard Photo  <Text style={styles.fieldLabelMuted}></Text></Text>
              <TextInput
                value={canvasImageInput}
                onChangeText={setCanvasImageInput}
                style={styles.imageInput}
                placeholder="Backyard photo URL"
                autoCapitalize="none"
                autoCorrect={false}
              />
              <View style={styles.imageButtonRow}>
                <Pressable style={styles.imgBtnSecondary} onPress={uploadCanvasImageFromDevice}><Text style={styles.imgBtnSecondaryText}>Upload</Text></Pressable>
                <Pressable style={styles.imgBtnPrimary} onPress={applyCanvasImage}><Text style={styles.imgBtnPrimaryText}>Use Image</Text></Pressable>
                <Pressable style={styles.imgBtnDanger} onPress={removeCanvasImage}><Text style={styles.imgBtnDangerText}>Remove</Text></Pressable>
              </View>
              {canvasImageMessage
                ? <Text style={canvasImageHasError ? styles.msgError : styles.msgInfo}>{canvasImageMessage}</Text>
                : <Text style={styles.hint}>Upload from device or paste a hosted URL.</Text>}
            </View>

            <View
              style={styles.canvasShell}
              onLayout={(event) => {
                const measuredWidth = Math.max(1, Math.round(event.nativeEvent.layout.width));
                setCanvasShellWidth(previous => (previous === measuredWidth ? previous : measuredWidth));
              }}>
              {shouldShowCanvas ? (
                <View style={[styles.canvas, { width: canvasWidth, height: canvasHeight }]}>
                  {canvasImageUri ? (
                    <>
                      <Image
                        source={{ uri: canvasImageUri }}
                        style={StyleSheet.absoluteFillObject}
                        resizeMode="cover"
                        onLoad={(event) => {
                          const source = event.nativeEvent?.source;
                          const sourceWidth = Number(source?.width);
                          const sourceHeight = Number(source?.height);
                          if (Number.isFinite(sourceWidth) && Number.isFinite(sourceHeight) && sourceWidth > 0 && sourceHeight > 0) {
                            fitCanvasToImage(sourceWidth, sourceHeight);
                          }
                          setCanvasImageHasError(false);
                        }}
                        onError={() => {
                          setCanvasImageMessage('Could not load image. Check the URL.');
                          setCanvasImageHasError(true);
                        }}
                      />
                      <View pointerEvents="none" style={styles.canvasOverlay} />
                    </>
                  ) : null}

                  {placedPlants.map(item => {
                    const plant = plantsById[item.plantId];
                    if (!plant) return null;
                    return (
                      <DraggablePlant
                        key={item.instanceId}
                        item={item}
                        plant={plant}
                        selected={selectedPlantId === item.instanceId}
                        canvasWidth={canvasWidth}
                        canvasHeight={canvasHeight}
                        onMove={movePlant}
                        onSelect={setSelectedPlantId}
                      />
                    );
                  })}
                </View>
              ) : (
                <View style={[styles.canvasPrompt, { width: getMaxCanvasWidth(), height: MAX_CANVAS_HEIGHT }]}>
                  <Text style={styles.canvasEmptyText}>Upload a backyard image to start your layout.</Text>
                </View>
              )}
            </View>

            {selectedPlant && selectedPlantDetails ? (
              <View style={styles.selPanel}>
                <Text style={styles.selTitle}>{selectedPlantDetails.emoji} {selectedPlantDetails.name}</Text>
                <View style={styles.selControls}>
                  <Pressable style={styles.selBtn} onPress={() => resizeSelectedPlant(-8)}><Text style={styles.selBtnText}>− Shrink</Text></Pressable>
                  <Text style={styles.selSize}>{selectedPlant.size}px</Text>
                  <Pressable style={styles.selBtn} onPress={() => resizeSelectedPlant(8)}><Text style={styles.selBtnText}>+ Grow</Text></Pressable>
                  <Pressable style={styles.selRemove} onPress={removeSelectedPlant}><Text style={styles.selRemoveText}>Remove</Text></Pressable>
                </View>
              </View>
            ) : (
              <Text style={styles.hint}>Tap a placed plant to resize or remove it.</Text>
            )}
          </View>

          <View style={[styles.workspacePanel, styles.workspaceDashboardPanel]}>
            <Text style={styles.workspacePanelTitle}>Sustainability Dashboard</Text>
            <View style={styles.dashboardHero}>
              <View style={[styles.scoreRing, { borderColor: scoreColor(metrics.sustainabilityScore) }]}>
                <Text style={[styles.scoreRingNum, { color: scoreColor(metrics.sustainabilityScore) }]}>{metrics.sustainabilityScore}</Text>
                <Text style={styles.scoreRingDenom}>/100</Text>
              </View>
              <View style={styles.scoreHeroRight}>
                <Text style={[styles.scorePill, { backgroundColor: scoreColor(metrics.sustainabilityScore) }]}>
                  {describeScore(metrics.sustainabilityScore)}
                </Text>
                <View style={styles.scoreMiniStats}>
                  <View style={styles.scoreMiniStat}>
                    <Text style={styles.scoreMiniNum}>{metrics.nativePercent}%</Text>
                    <Text style={styles.scoreMiniLabel}>Native</Text>
                  </View>
                  <View style={styles.scoreMiniStat}>
                    <Text style={styles.scoreMiniNum}>{metrics.weeklyWaterDemand}</Text>
                    <Text style={styles.scoreMiniLabel}>Water/wk</Text>
                  </View>
                </View>
              </View>
            </View>
            {[
              { icon: '💧', label: 'Water Efficiency', value: metrics.waterEfficiency },
              { icon: '🐝', label: 'Pollinator Support', value: metrics.pollinatorSupport },
              { icon: '☀️', label: 'Drought Resistance', value: metrics.droughtResistance },
              { icon: '🌍', label: 'Biodiversity', value: metrics.biodiversity },
              { icon: '🌳', label: 'Carbon Impact', value: metrics.carbonImpact },
            ].map(m => (
              <View key={m.label} style={styles.metricRowLight}>
                <Text style={styles.metricIcon}>{m.icon}</Text>
                <View style={styles.metricBody}>
                  <View style={styles.metricTop}>
                    <Text style={styles.metricLabelLight}>{m.label}</Text>
                    <Text style={styles.metricValueLight}>{describeScore(m.value)} · {m.value}</Text>
                  </View>
                  <View style={styles.metricTrackLight}>
                    <View style={[styles.metricFill, { width: `${m.value}%` as any, backgroundColor: m.value >= 70 ? '#6a9e55' : m.value >= 50 ? '#b8860b' : '#b5451b' }]} />
                  </View>
                </View>
              </View>
            ))}
            <Text style={styles.dashboardFooter}>
              {backendStatus === 'connected' ? '🟢' : backendStatus === 'checking' ? '🟡' : '🔴'} {backendMessage}
            </Text>
          </View>
        </View>
      </View>

    </ScrollView>
  );
}

const CREAM = '#faf7f0';
const WARM_WHITE = '#ffffff';
const BROWN = '#3a2d1c';
const MID_BROWN = '#6b5237';
const SOFT = '#e4d9c8';
const FOREST = '#2c3b24';
const FOREST_MID = '#3d5230';
const ACCENT_GREEN = '#5a8040';

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: CREAM },
  pageContent: { paddingBottom: 48, gap: 16 },

  hero: { height: SCREEN_HEIGHT, position: 'relative', overflow: 'hidden' },
  heroBgImage: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, width: '100%', height: '100%' },
  heroOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 25, 10, 0.52)' },
  heroDot: { position: 'absolute', top: 52, right: 20, width: 9, height: 9, borderRadius: 5 },
  heroCenter: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 28, paddingTop: 60 },
  heroEyebrow: { color: '#b8dfa0', fontSize: 30, fontWeight: '700', letterSpacing: 1.4, textTransform: 'uppercase', marginBottom: 16 },
  heroTitle: { color: '#f5ede0', fontSize: 70, fontWeight: '900', lineHeight: 75, textAlign: 'center', letterSpacing: -1, marginBottom: 18, fontFamily: 'Georgia'},
  heroSub: { color: '#c8dfc0', fontSize: 16, lineHeight: 24, textAlign: 'center', fontWeight: '400' },
 getStartedBtn: {
  marginBottom: 100,
  backgroundColor: 'rgba(255,255,255,0.15)',
  borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.4)',
  borderRadius: 999, paddingVertical: 14, paddingHorizontal: 40,
  alignSelf: 'center',
},
getStartedText: {
  color: '#f5ede0', fontSize: 15, fontWeight: '700', letterSpacing: 0.5,
},

  sectionCard: { backgroundColor: WARM_WHITE, borderRadius: 22, marginHorizontal: 14, padding: 18, gap: 12, shadowColor: '#8a7060', shadowOpacity: 0.09, shadowRadius: 10, shadowOffset: { width: 0, height: 4 }, elevation: 2 },
  sectionTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  sectionNumBadge: { width: 28, height: 28, borderRadius: 14, backgroundColor: FOREST, alignItems: 'center', justifyContent: 'center' },
  sectionNumBadgeDark: { backgroundColor: 'rgba(255,255,255,0.15)' },
  sectionNum: { color: '#c8e8b0', fontSize: 13, fontWeight: '900' },
  sectionNumDark: { color: '#c8e8b0' },
  sectionTitle: { fontSize: 19, fontWeight: '800', color: BROWN, letterSpacing: -0.3 },
  fieldLabel: { fontSize: 12, fontWeight: '700', color: MID_BROWN, textTransform: 'uppercase', letterSpacing: 0.6 },
  fieldLabelMuted: { fontWeight: '500', color: '#b0a090', textTransform: 'none', letterSpacing: 0 },
  hint: { fontSize: 12, color: '#9c8b72', lineHeight: 17 },
  msgInfo: { fontSize: 12, color: '#3a6040', lineHeight: 17 },
  msgError: { fontSize: 12, color: '#9f3412', lineHeight: 17, fontWeight: '600' },
  workspaceRow: { flexDirection: Platform.OS === 'web' ? 'row' : 'column', gap: 12, alignItems: 'stretch' },
  workspacePanel: { borderRadius: 16, borderWidth: 1.5, borderColor: SOFT, backgroundColor: '#fdfaf4', padding: 12, gap: 8 },
  workspacePlantsPanel: Platform.OS === 'web' ? { width: 250 } : { width: '100%' },
  workspaceCanvasPanel: { flex: 1, minWidth: 0 },
  workspaceDashboardPanel: Platform.OS === 'web' ? { width: 300 } : { width: '100%' },
  workspacePanelTitle: { fontSize: 16, fontWeight: '800', color: BROWN },
  sidePlantScroll: { flexGrow: 0 },
  sidePlantList: { gap: 10, paddingBottom: 4 },
  sidePlantCard: { borderRadius: 14, borderWidth: 1.5, borderColor: SOFT, backgroundColor: WARM_WHITE, padding: 10, gap: 6 },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1.5, borderColor: SOFT, backgroundColor: '#fdfaf4', borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7 },
  chipActive: { borderColor: ACCENT_GREEN, backgroundColor: '#eaf2e4' },
  chipText: { fontSize: 12, fontWeight: '700', color: MID_BROWN },
  chipTextActive: { color: ACCENT_GREEN },

  zipRow: { flexDirection: 'row', gap: 8 },
  zipInput: { flex: 1, borderWidth: 1.5, borderColor: SOFT, borderRadius: 12, backgroundColor: '#fdfaf4', paddingHorizontal: 12, paddingVertical: 11, color: BROWN, fontSize: 15, fontWeight: '600' },
  zipBtn: { minWidth: 90, borderRadius: 12, backgroundColor: '#1a4e6e', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 10 },
  zipBtnDisabled: { backgroundColor: '#6d8a98' },
  zipBtnText: { color: '#e8f6ff', fontWeight: '800', fontSize: 13 },

  plantScroll: { paddingBottom: 4, gap: 10 },
  plantCard: { width: 155, borderRadius: 18, borderWidth: 1.5, borderColor: SOFT, backgroundColor: '#fdfaf4', padding: 12, gap: 6 },
  nativeBadge: { alignSelf: 'flex-start', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 3 },
  nativeBadgeYes: { backgroundColor: '#ddeedd' },
  nativeBadgeNo: { backgroundColor: '#f0e8d8' },
  nativeBadgeText: { fontSize: 10, fontWeight: '800', color: '#3a6040' },
  plantEmoji: { fontSize: 38, marginVertical: 4 },
  plantName: { fontSize: 13, fontWeight: '800', color: BROWN, lineHeight: 17 },
  plantTags: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  plantTag: { fontSize: 10, color: MID_BROWN, backgroundColor: '#f0ebe0', borderRadius: 6, paddingHorizontal: 5, paddingVertical: 2 },
  addBtn: { marginTop: 4, backgroundColor: FOREST, borderRadius: 10, paddingVertical: 9, alignItems: 'center' },
  addBtnText: { color: '#c8e8b0', fontSize: 12, fontWeight: '800' },
  emptyCard: { borderWidth: 1.5, borderColor: SOFT, borderRadius: 14, backgroundColor: '#fdfaf4', padding: 24, alignItems: 'center', gap: 8 },
  emptyEmoji: { fontSize: 32, opacity: 0.5 },
  emptyText: { color: '#9c8b72', fontSize: 13, textAlign: 'center', lineHeight: 19 },

  clearBtn: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 10, borderWidth: 1.5, borderColor: SOFT },
  clearBtnText: { fontSize: 12, color: MID_BROWN, fontWeight: '700' },
  imageBlock: { borderWidth: 1.5, borderColor: SOFT, borderRadius: 14, backgroundColor: '#fdfaf4', padding: 12, gap: 8 },
  imageInput: { borderWidth: 1, borderColor: SOFT, borderRadius: 10, backgroundColor: WARM_WHITE, paddingHorizontal: 10, paddingVertical: 9, color: BROWN, fontSize: 13 },
  imageButtonRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  imgBtnSecondary: { flex: 1, minWidth: 80, borderRadius: 10, backgroundColor: '#1a4e6e', alignItems: 'center', paddingVertical: 9 },
  imgBtnSecondaryText: { color: '#e8f6ff', fontSize: 12, fontWeight: '700' },
  imgBtnPrimary: { flex: 1, minWidth: 80, borderRadius: 10, backgroundColor: FOREST_MID, alignItems: 'center', paddingVertical: 9 },
  imgBtnPrimaryText: { color: '#c8e8b0', fontSize: 12, fontWeight: '700' },
  imgBtnDanger: { flex: 1, minWidth: 80, borderRadius: 10, borderWidth: 1.5, borderColor: SOFT, backgroundColor: WARM_WHITE, alignItems: 'center', paddingVertical: 9 },
  imgBtnDangerText: { color: MID_BROWN, fontSize: 12, fontWeight: '700' },

  canvasShell: { borderRadius: 16, borderWidth: 1.5, borderColor: SOFT, backgroundColor: '#f5f0e8', alignItems: 'center', padding: 8 },
  canvas: { position: 'relative', borderWidth: 2, borderColor: '#c4b498', borderRadius: 10, backgroundColor: '#fdfaf4', overflow: 'hidden' },
  canvasOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(10, 18, 6, 0.22)' },
  canvasPrompt: { width: '100%', minHeight: 96, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12 },
  gridV: { position: 'absolute', top: 0, bottom: 0, width: 1, backgroundColor: '#ede4d4' },
  gridH: { position: 'absolute', left: 0, right: 0, height: 1, backgroundColor: '#ede4d4' },
  canvasEmpty: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center', gap: 6 },
  canvasEmptyIcon: { fontSize: 32, opacity: 0.35 },
  canvasEmptyText: { color: '#b0a080', fontSize: 13 },
  canvasPlantOverlay: {
  position: 'absolute', bottom: 0, left: 0, right: 0,
  backgroundColor: 'rgba(20, 30, 15, 0.55)',
  paddingVertical: 8, zIndex: 10,
},
canvasPlantOverlayScroll: { paddingHorizontal: 10, gap: 8 },
canvasPlantChip: {
  alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.15)',
  borderRadius: 12, paddingHorizontal: 10, paddingVertical: 6,
  borderWidth: 1, borderColor: 'rgba(255,255,255,0.25)', gap: 2,
},
canvasPlantChipEmoji: { fontSize: 22 },
canvasPlantChipName: { color: '#f0ede0', fontSize: 9, fontWeight: '700', textAlign: 'center', maxWidth: 60 },
  placedPlant: { position: 'absolute', borderRadius: 999, borderWidth: 2, borderColor: '#7a6848', backgroundColor: 'rgba(170,210,140,0.45)', alignItems: 'center', justifyContent: 'center', zIndex: 2 },
  placedPlantSelected: { borderColor: ACCENT_GREEN, backgroundColor: 'rgba(140,200,110,0.6)', borderWidth: 2.5 },

  selPanel: { borderRadius: 12, borderWidth: 1.5, borderColor: SOFT, backgroundColor: '#fdfaf4', padding: 12, gap: 8 },
  selTitle: { fontSize: 14, fontWeight: '800', color: BROWN },
  selControls: { flexDirection: 'row', gap: 8, alignItems: 'center', flexWrap: 'wrap' },
  selBtn: { backgroundColor: FOREST, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8 },
  selBtnText: { color: '#c8e8b0', fontWeight: '700', fontSize: 12 },
  selSize: { color: MID_BROWN, fontWeight: '700', fontSize: 13 },
  selRemove: { marginLeft: 'auto', borderWidth: 1.5, borderColor: '#e0c0b0', backgroundColor: '#fff5f0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8 },
  selRemoveText: { color: '#8f3010', fontWeight: '700', fontSize: 12 },

  dashboardHero: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  scoreCard: { backgroundColor: FOREST, borderRadius: 22, marginHorizontal: 14, padding: 18, gap: 12 },
  scoreHeroBlock: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  scoreRing: { width: 94, height: 94, borderRadius: 47, borderWidth: 5, alignItems: 'center', justifyContent: 'center', backgroundColor: '#f3ece0' },
  scoreRingNum: { fontSize: 30, fontWeight: '900' },
  scoreRingDenom: { fontSize: 11, color: '#8f7a5d', fontWeight: '600' },
  scoreHeroRight: { flex: 1, gap: 10 },
  scorePill: { alignSelf: 'flex-start', borderRadius: 999, paddingHorizontal: 12, paddingVertical: 5, color: '#fff', fontSize: 12, fontWeight: '800', overflow: 'hidden' },
  scoreMiniStats: { flexDirection: 'row', gap: 10 },
  scoreMiniStat: { backgroundColor: '#f2ebdf', borderRadius: 10, padding: 10, flex: 1 },
  scoreMiniNum: { color: BROWN, fontSize: 18, fontWeight: '900' },
  scoreMiniLabel: { color: '#7f705a', fontSize: 10, fontWeight: '600', marginTop: 2 },

  metricRow: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  metricRowLight: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  metricIcon: { fontSize: 18, width: 26, textAlign: 'center' },
  metricBody: { flex: 1, gap: 4 },
  metricTop: { flexDirection: 'row', justifyContent: 'space-between' },
  metricLabel: { color: '#c8d8b8', fontSize: 13, fontWeight: '600' },
  metricLabelLight: { color: MID_BROWN, fontSize: 13, fontWeight: '600' },
  metricValue: { color: '#f0e8d0', fontSize: 12, fontWeight: '700' },
  metricValueLight: { color: BROWN, fontSize: 12, fontWeight: '700' },
  metricTrack: { height: 5, backgroundColor: 'rgba(255,255,255,0.12)', borderRadius: 3, overflow: 'hidden' },
  metricTrackLight: { height: 5, backgroundColor: '#e4d7c4', borderRadius: 3, overflow: 'hidden' },
  metricFill: { height: 5, borderRadius: 3 },
  scoreFooter: { fontSize: 11, color: 'rgba(180,200,160,0.6)', textAlign: 'center', marginTop: 4 },
  dashboardFooter: { fontSize: 11, color: '#7d6a55', textAlign: 'center', marginTop: 6 },
});