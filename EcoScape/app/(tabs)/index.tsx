import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
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
type Region = 'CA' | 'Southwest' | 'PacificNW' | 'Southeast';

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
  plantTypeOptions?: { id: string; label: string }[];
  constraints?: {
    minGardenDimension?: number;
    maxGardenDimension?: number;
  };
  integrations?: {
    flora?: {
      enabled?: boolean;
      baseUrl?: string;
    };
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
  error?: string;
  detail?: string;
};

type ApiScoreResponse = {
  climate: ClimateProfile;
  metrics: SustainabilityMetrics;
};

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:5001';

const DEFAULT_CLIMATE_OPTIONS: ClimateProfile[] = [
  { id: 'irvine', label: 'Irvine, CA', zone: '10a', region: 'CA' },
  { id: 'santa-barbara', label: 'Santa Barbara, CA', zone: '9b', region: 'CA' },
  { id: 'phoenix', label: 'Phoenix, AZ', zone: '10b', region: 'Southwest' },
  { id: 'seattle', label: 'Seattle, WA', zone: '8b', region: 'PacificNW' },
];

const DEFAULT_PLANT_TYPE_OPTIONS: { id: string; label: string }[] = [
  { id: 'any', label: 'Any' },
  { id: 'flower', label: 'Flower' },
  { id: 'fruit', label: 'Fruit' },
  { id: 'bush', label: 'Bush' },
  { id: 'tree', label: 'Tree' },
  { id: 'vine', label: 'Vine' },
  { id: 'grass', label: 'Grass' },
  { id: 'succulent', label: 'Succulent' },
];

const DEFAULT_PLANT_LIBRARY: Plant[] = [
  {
    id: 'ceanothus',
    name: 'California Lilac',
    emoji: '🪻',
    zones: ['8b', '9b', '10a'],
    nativeRegions: ['CA'],
    waterUsage: 'Low',
    pollinatorValue: 'High',
    carbonSequestration: 'Medium',
    shadeCoverage: 'Medium',
    droughtResistance: 'High',
  },
  {
    id: 'toyon',
    name: 'Toyon',
    emoji: '🌿',
    zones: ['8b', '9b', '10a'],
    nativeRegions: ['CA'],
    waterUsage: 'Low',
    pollinatorValue: 'High',
    carbonSequestration: 'High',
    shadeCoverage: 'Medium',
    droughtResistance: 'High',
  },
  {
    id: 'manzanita',
    name: 'Manzanita',
    emoji: '🪴',
    zones: ['8b', '9b', '10a'],
    nativeRegions: ['CA'],
    waterUsage: 'Low',
    pollinatorValue: 'Medium',
    carbonSequestration: 'Medium',
    shadeCoverage: 'Low',
    droughtResistance: 'High',
  },
  {
    id: 'yarrow',
    name: 'Yarrow',
    emoji: '🌼',
    zones: ['8b', '9b', '10a', '10b'],
    nativeRegions: ['CA', 'PacificNW'],
    waterUsage: 'Low',
    pollinatorValue: 'High',
    carbonSequestration: 'Low',
    shadeCoverage: 'Low',
    droughtResistance: 'High',
  },
  {
    id: 'milkweed',
    name: 'Narrowleaf Milkweed',
    emoji: '🐝',
    zones: ['9b', '10a', '10b'],
    nativeRegions: ['CA', 'Southwest'],
    waterUsage: 'Medium',
    pollinatorValue: 'High',
    carbonSequestration: 'Medium',
    shadeCoverage: 'Low',
    droughtResistance: 'Medium',
  },
  {
    id: 'lavender',
    name: 'Lavender',
    emoji: '💜',
    zones: ['8b', '9b', '10a', '10b'],
    nativeRegions: ['CA', 'Southwest'],
    waterUsage: 'Low',
    pollinatorValue: 'High',
    carbonSequestration: 'Medium',
    shadeCoverage: 'Low',
    droughtResistance: 'High',
  },
  {
    id: 'sage',
    name: 'White Sage',
    emoji: '🌱',
    zones: ['8b', '9b', '10a', '10b'],
    nativeRegions: ['CA', 'Southwest'],
    waterUsage: 'Low',
    pollinatorValue: 'High',
    carbonSequestration: 'Low',
    shadeCoverage: 'Low',
    droughtResistance: 'High',
  },
  {
    id: 'oregon-grape',
    name: 'Oregon Grape',
    emoji: '🍃',
    zones: ['8b', '9b'],
    nativeRegions: ['PacificNW'],
    waterUsage: 'Medium',
    pollinatorValue: 'Medium',
    carbonSequestration: 'Medium',
    shadeCoverage: 'Medium',
    droughtResistance: 'Medium',
  },
  {
    id: 'dwarf-citrus',
    name: 'Dwarf Citrus',
    emoji: '🍋',
    zones: ['9b', '10a', '10b'],
    nativeRegions: ['Southeast'],
    waterUsage: 'High',
    pollinatorValue: 'Medium',
    carbonSequestration: 'High',
    shadeCoverage: 'Medium',
    droughtResistance: 'Low',
  },
];

const WATER_EFFICIENCY_POINTS: Record<Rating, number> = {
  Low: 100,
  Medium: 70,
  High: 35,
};

const RATING_POINTS: Record<Rating, number> = {
  Low: 40,
  Medium: 70,
  High: 100,
};

const WATER_UNITS: Record<Rating, number> = {
  Low: 1,
  Medium: 2,
  High: 3,
};

const EMPTY_METRICS: SustainabilityMetrics = {
  sustainabilityScore: 0,
  waterEfficiency: 0,
  pollinatorSupport: 0,
  nativePercent: 0,
  droughtResistance: 0,
  biodiversity: 0,
  carbonImpact: 0,
  weeklyWaterDemand: 0,
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function parseGardenDimension(rawValue: string): number {
  const parsed = Number.parseInt(rawValue, 10);
  if (Number.isNaN(parsed)) {
    return 10;
  }
  return Math.max(parsed, 1);
}

function normalizeZipCode(rawValue: string): string | null {
  const digitsOnly = rawValue.replace(/\D/g, '');
  if (digitsOnly.length < 5) {
    return null;
  }
  return digitsOnly.slice(0, 5);
}

function mergePlantLists(currentPlants: Plant[], incomingPlants: Plant[]): Plant[] {
  const merged = new Map<string, Plant>();
  for (const plant of currentPlants) {
    merged.set(plant.id, plant);
  }
  for (const plant of incomingPlants) {
    merged.set(plant.id, plant);
  }
  return Array.from(merged.values());
}

function describeScore(score: number): string {
  if (score >= 85) {
    return 'Excellent';
  }
  if (score >= 70) {
    return 'High';
  }
  if (score >= 55) {
    return 'Moderate';
  }
  return 'Needs work';
}

function scoreColor(score: number): string {
  if (score >= 85) {
    return '#0f8a5b';
  }
  if (score >= 70) {
    return '#1f9d6b';
  }
  if (score >= 55) {
    return '#c49320';
  }
  return '#c2410c';
}

function weightedAverage(values: number[], weights: number[]): number {
  if (values.length === 0 || weights.length === 0) {
    return 0;
  }
  const weightTotal = weights.reduce((sum, value) => sum + value, 0);
  if (weightTotal <= 0) {
    return 0;
  }
  return values.reduce((sum, value, index) => sum + value * (weights[index] ?? 0), 0) / weightTotal;
}

function computeMetrics(
  placedPlants: PlacedPlant[],
  plantsById: Record<string, Plant>,
  climate: ClimateProfile
): SustainabilityMetrics {
  const resolvedPlants = placedPlants
    .map((placedPlant) => {
      const plant = plantsById[placedPlant.plantId];
      if (!plant) {
        return null;
      }
      return {
        plant,
        weight: clamp(placedPlant.size / 56, 0.6, 2.4),
      };
    })
    .filter((entry): entry is { plant: Plant; weight: number } => Boolean(entry));

  if (resolvedPlants.length === 0) {
    return EMPTY_METRICS;
  }

  const plants = resolvedPlants.map((entry) => entry.plant);
  const weights = resolvedPlants.map((entry) => entry.weight);
  const weightTotal = weights.reduce((sum, value) => sum + value, 0);

  const waterEfficiency = Math.round(
    weightedAverage(plants.map((plant) => WATER_EFFICIENCY_POINTS[plant.waterUsage]), weights)
  );
  const pollinatorSupport = Math.round(
    weightedAverage(plants.map((plant) => RATING_POINTS[plant.pollinatorValue]), weights)
  );
  const droughtResistance = Math.round(
    weightedAverage(plants.map((plant) => RATING_POINTS[plant.droughtResistance]), weights)
  );
  const carbonImpact = Math.round(weightedAverage(plants.map((plant) => RATING_POINTS[plant.carbonSequestration]), weights));
  const nativeWeight = resolvedPlants
    .filter((entry) => entry.plant.nativeRegions.includes(climate.region))
    .reduce((sum, entry) => sum + entry.weight, 0);
  const nativePercent = weightTotal > 0 ? Math.round((nativeWeight / weightTotal) * 100) : 0;
  const uniqueSpecies = new Set(plants.map((plant) => plant.id)).size;
  const biodiversity = Math.round(
    clamp((uniqueSpecies / plants.length) * 70 + Math.min(uniqueSpecies, 6) * 5 + 25, 0, 100)
  );
  const weeklyWaterDemand = Math.round(
    resolvedPlants.reduce(
      (sum, entry) => sum + WATER_UNITS[entry.plant.waterUsage] * entry.weight,
      0
    )
  );
  const sustainabilityScore = Math.round(
    nativePercent * 0.28 +
      waterEfficiency * 0.24 +
      pollinatorSupport * 0.16 +
      droughtResistance * 0.14 +
      biodiversity * 0.1 +
      carbonImpact * 0.08
  );

  return {
    sustainabilityScore,
    waterEfficiency,
    pollinatorSupport,
    nativePercent,
    droughtResistance,
    biodiversity,
    carbonImpact,
    weeklyWaterDemand,
  };
}

function defaultClimate(options: ClimateProfile[]): ClimateProfile {
  return options[0] ?? DEFAULT_CLIMATE_OPTIONS[0];
}

type DraggablePlantProps = {
  item: PlacedPlant;
  plant: Plant;
  selected: boolean;
  canvasWidth: number;
  canvasHeight: number;
  onMove: (instanceId: string, x: number, y: number) => void;
  onSelect: (instanceId: string) => void;
};

function DraggablePlant({
  item,
  plant,
  selected,
  canvasWidth,
  canvasHeight,
  onMove,
  onSelect,
}: DraggablePlantProps) {
  const dragOrigin = useRef({ x: item.x, y: item.y });

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: () => {
          dragOrigin.current = { x: item.x, y: item.y };
          onSelect(item.instanceId);
        },
        onPanResponderMove: (_event, gestureState) => {
          const maxX = Math.max(0, canvasWidth - item.size);
          const maxY = Math.max(0, canvasHeight - item.size);
          const nextX = clamp(dragOrigin.current.x + gestureState.dx, 0, maxX);
          const nextY = clamp(dragOrigin.current.y + gestureState.dy, 0, maxY);
          onMove(item.instanceId, nextX, nextY);
        },
      }),
    [canvasHeight, canvasWidth, item.instanceId, item.size, item.x, item.y, onMove, onSelect]
  );

  return (
    <View
      {...panResponder.panHandlers}
      style={[
        styles.placedPlant,
        selected ? styles.placedPlantSelected : undefined,
        {
          left: item.x,
          top: item.y,
          width: item.size,
          height: item.size,
        },
      ]}>
      <Text style={styles.placedPlantEmoji}>{plant.emoji}</Text>
    </View>
  );
}

export default function HomeScreen() {
  const [widthInput, setWidthInput] = useState('10');
  const [heightInput, setHeightInput] = useState('10');
  const [selectedClimateId, setSelectedClimateId] = useState(defaultClimate(DEFAULT_CLIMATE_OPTIONS).id);
  const [placedPlants, setPlacedPlants] = useState<PlacedPlant[]>([]);
  const [selectedPlantId, setSelectedPlantId] = useState<string | null>(null);
  const [zipCodeInput, setZipCodeInput] = useState('');
  const [activeZipCode, setActiveZipCode] = useState<string | null>(null);
  const [selectedPlantType, setSelectedPlantType] = useState('any');
  const [plantTypeOptions, setPlantTypeOptions] = useState(DEFAULT_PLANT_TYPE_OPTIONS);
  const [zipLookupLoading, setZipLookupLoading] = useState(false);
  const [zipLookupMessage, setZipLookupMessage] = useState<string | null>(null);
  const [zipLookupError, setZipLookupError] = useState(false);
  const [canvasImageInput, setCanvasImageInput] = useState('');
  const [canvasImageUri, setCanvasImageUri] = useState<string | null>(null);
  const [canvasImageMessage, setCanvasImageMessage] = useState<string | null>(null);
  const [canvasImageHasError, setCanvasImageHasError] = useState(false);
  const uploadedObjectUrlRef = useRef<string | null>(null);
  const [climateOptions, setClimateOptions] = useState<ClimateProfile[]>(DEFAULT_CLIMATE_OPTIONS);
  const [plantLibrary, setPlantLibrary] = useState<Plant[]>(DEFAULT_PLANT_LIBRARY);
  const [recommendations, setRecommendations] = useState<Plant[]>([]);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'offline'>('checking');
  const [backendMessage, setBackendMessage] = useState('Connecting to Flask API...');
  const [apiMetrics, setApiMetrics] = useState<SustainabilityMetrics | null>(null);

  const selectedClimate = useMemo(
    () => climateOptions.find((profile) => profile.id === selectedClimateId) ?? defaultClimate(climateOptions),
    [climateOptions, selectedClimateId]
  );
  const selectedPlantTypeLabel = useMemo(
    () => plantTypeOptions.find((option) => option.id === selectedPlantType)?.label ?? 'Any',
    [plantTypeOptions, selectedPlantType]
  );

  const gardenWidthFeet = parseGardenDimension(widthInput);
  const gardenHeightFeet = parseGardenDimension(heightInput);
  const gardenAreaSqFt = gardenWidthFeet * gardenHeightFeet;
  const canvasWidthFeet = clamp(gardenWidthFeet, 6, 24);
  const canvasHeightFeet = clamp(gardenHeightFeet, 6, 24);
  const gridUnit = Math.max(12, Math.min(40, Math.floor(360 / Math.max(canvasWidthFeet, canvasHeightFeet))));
  const canvasWidth = canvasWidthFeet * gridUnit;
  const canvasHeight = canvasHeightFeet * gridUnit;

  const plantsById = useMemo(
    () =>
      plantLibrary.reduce<Record<string, Plant>>((accumulator, plant) => {
        accumulator[plant.id] = plant;
        return accumulator;
      }, {}),
    [plantLibrary]
  );
  const fallbackMetrics = useMemo(
    () => computeMetrics(placedPlants, plantsById, selectedClimate),
    [placedPlants, plantsById, selectedClimate]
  );
  const metrics = useMemo(() => apiMetrics ?? fallbackMetrics, [apiMetrics, fallbackMetrics]);
  const scoreSignature = useMemo(
    () => placedPlants.map((plant) => `${plant.plantId}:${Math.round(plant.size)}`).join('|'),
    [placedPlants]
  );

  const selectedPlant = placedPlants.find((plant) => plant.instanceId === selectedPlantId) ?? null;
  const selectedPlantDetails = selectedPlant ? plantsById[selectedPlant.plantId] : null;

  useEffect(() => {
    let cancelled = false;

    async function loadConfig() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/config`);
        if (!response.ok) {
          throw new Error(`Config request failed: ${response.status}`);
        }
        const payload = (await response.json()) as ApiConfigResponse;
        if (cancelled) {
          return;
        }

        const nextClimateOptions = payload.climateOptions?.length
          ? payload.climateOptions
          : DEFAULT_CLIMATE_OPTIONS;
        const nextPlantLibrary = payload.plantLibrary?.length ? payload.plantLibrary : DEFAULT_PLANT_LIBRARY;
        const serverPlantTypeOptions = payload.plantTypeOptions?.length
          ? payload.plantTypeOptions
          : DEFAULT_PLANT_TYPE_OPTIONS.filter((option) => option.id !== 'any');
        const nextPlantTypeOptions = [
          DEFAULT_PLANT_TYPE_OPTIONS[0],
          ...serverPlantTypeOptions.filter((option) => option.id !== 'any'),
        ];

        setClimateOptions(nextClimateOptions);
        setPlantLibrary(nextPlantLibrary);
        setPlantTypeOptions(nextPlantTypeOptions);
        setSelectedPlantType((currentType) =>
          nextPlantTypeOptions.some((option) => option.id === currentType) ? currentType : 'any'
        );
        setSelectedClimateId((currentId) =>
          nextClimateOptions.some((profile) => profile.id === currentId)
            ? currentId
            : defaultClimate(nextClimateOptions).id
        );
        setBackendStatus('connected');
        setBackendMessage(`Connected to Flask API (${API_BASE_URL})`);
      } catch {
        if (cancelled) {
          return;
        }
        setClimateOptions(DEFAULT_CLIMATE_OPTIONS);
        setPlantLibrary(DEFAULT_PLANT_LIBRARY);
        setPlantTypeOptions(DEFAULT_PLANT_TYPE_OPTIONS);
        setBackendStatus('offline');
        setBackendMessage('Flask API not reachable. Using local fallback model.');
      }
    }

    loadConfig();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (backendStatus !== 'connected') {
      setApiMetrics(null);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/score`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            climateId: selectedClimate.id,
            placedPlants: scoreSignature
              ? scoreSignature.split('|').map((entry) => {
                  const [plantId, sizeValue] = entry.split(':');
                  return {
                    plantId,
                    size: Number(sizeValue),
                  };
                })
              : [],
          }),
        });
        if (!response.ok) {
          throw new Error(`Score request failed: ${response.status}`);
        }
        const payload = (await response.json()) as ApiScoreResponse;
        if (cancelled) {
          return;
        }
        setApiMetrics(payload.metrics);
      } catch {
        if (cancelled) {
          return;
        }
        setApiMetrics(null);
        setBackendStatus('offline');
        setBackendMessage('Score API offline. Using local scoring model.');
      }
    }, 120);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [backendStatus, scoreSignature, selectedClimate.id]);

  useEffect(() => {
    setPlacedPlants((currentPlants) => {
      let hasChanges = false;
      const constrainedPlants = currentPlants.map((plant) => {
        const maxX = Math.max(0, canvasWidth - plant.size);
        const maxY = Math.max(0, canvasHeight - plant.size);
        const nextX = clamp(plant.x, 0, maxX);
        const nextY = clamp(plant.y, 0, maxY);
        if (nextX === plant.x && nextY === plant.y) {
          return plant;
        }
        hasChanges = true;
        return { ...plant, x: nextX, y: nextY };
      });
      return hasChanges ? constrainedPlants : currentPlants;
    });
  }, [canvasHeight, canvasWidth]);

  useEffect(() => {
    return () => {
      const objectUrl = uploadedObjectUrlRef.current;
      const globalUrl = (globalThis as { URL?: { revokeObjectURL?: (url: string) => void } }).URL;
      if (objectUrl && globalUrl?.revokeObjectURL) {
        globalUrl.revokeObjectURL(objectUrl);
      }
      uploadedObjectUrlRef.current = null;
    };
  }, []);

  function addPlantToCanvas(plant: Plant) {
    const size = 56;
    const instanceId = `${plant.id}-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

    setPlacedPlants((currentPlants) => {
      const stackIndex = currentPlants.length;
      const startX = clamp(16 + (stackIndex % 4) * (size + 12), 0, Math.max(0, canvasWidth - size));
      const startY = clamp(
        16 + Math.floor(stackIndex / 4) * (size + 12),
        0,
        Math.max(0, canvasHeight - size)
      );
      return [
        ...currentPlants,
        {
          instanceId,
          plantId: plant.id,
          x: startX,
          y: startY,
          size,
        },
      ];
    });
    setSelectedPlantId(instanceId);
  }

  function movePlant(instanceId: string, x: number, y: number) {
    setPlacedPlants((currentPlants) =>
      currentPlants.map((plant) => {
        if (plant.instanceId !== instanceId) {
          return plant;
        }
        if (plant.x === x && plant.y === y) {
          return plant;
        }
        return { ...plant, x, y };
      })
    );
  }

  function resizeSelectedPlant(delta: number) {
    if (!selectedPlantId) {
      return;
    }

    setPlacedPlants((currentPlants) =>
      currentPlants.map((plant) => {
        if (plant.instanceId !== selectedPlantId) {
          return plant;
        }

        const nextSize = clamp(plant.size + delta, 34, 120);
        const maxX = Math.max(0, canvasWidth - nextSize);
        const maxY = Math.max(0, canvasHeight - nextSize);

        return {
          ...plant,
          size: nextSize,
          x: clamp(plant.x, 0, maxX),
          y: clamp(plant.y, 0, maxY),
        };
      })
    );
  }

  function removeSelectedPlant() {
    if (!selectedPlantId) {
      return;
    }
    setPlacedPlants((currentPlants) => currentPlants.filter((plant) => plant.instanceId !== selectedPlantId));
    setSelectedPlantId(null);
  }

  function clearCanvas() {
    setPlacedPlants([]);
    setSelectedPlantId(null);
  }

  function clearUploadedObjectUrl() {
    const objectUrl = uploadedObjectUrlRef.current;
    const globalUrl = (globalThis as { URL?: { revokeObjectURL?: (url: string) => void } }).URL;
    if (objectUrl && globalUrl?.revokeObjectURL) {
      globalUrl.revokeObjectURL(objectUrl);
    }
    uploadedObjectUrlRef.current = null;
  }

  function applyCanvasImage() {
    const nextUri = canvasImageInput.trim();
    if (!nextUri) {
      setCanvasImageMessage('Enter an image URL first.');
      setCanvasImageHasError(true);
      return;
    }

    const isValidUri =
      nextUri.startsWith('https://') ||
      nextUri.startsWith('http://') ||
      nextUri.startsWith('data:image/') ||
      nextUri.startsWith('file://');

    if (!isValidUri) {
      setCanvasImageMessage('Use a valid URL (https://...) or data:image/... value.');
      setCanvasImageHasError(true);
      return;
    }

    clearUploadedObjectUrl();
    setCanvasImageUri(nextUri);
    setCanvasImageMessage('Loading backyard image...');
    setCanvasImageHasError(false);
  }

  function uploadCanvasImageFromDevice() {
    if (Platform.OS !== 'web') {
      setCanvasImageMessage('Device upload is available on web/laptop mode.');
      setCanvasImageHasError(true);
      return;
    }

    const doc = (globalThis as { document?: { createElement?: (tag: string) => any } }).document;
    const globalUrl = (globalThis as {
      URL?: { createObjectURL?: (file: any) => string; revokeObjectURL?: (url: string) => void };
    }).URL;
    const createObjectURL = globalUrl?.createObjectURL;

    if (!doc?.createElement || !createObjectURL) {
      setCanvasImageMessage('Upload is not available in this environment.');
      setCanvasImageHasError(true);
      return;
    }

    const fileInput = doc.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';
    fileInput.onchange = () => {
      const selectedFile = fileInput.files?.[0] as { name?: string } | undefined;
      if (!selectedFile) {
        return;
      }

      const nextObjectUrl = createObjectURL(selectedFile);
      clearUploadedObjectUrl();
      uploadedObjectUrlRef.current = nextObjectUrl;
      setCanvasImageInput(selectedFile.name ?? 'local-image');
      setCanvasImageUri(nextObjectUrl);
      setCanvasImageMessage(`Loaded local file: ${selectedFile.name ?? 'image'}`);
      setCanvasImageHasError(false);
    };

    fileInput.click();
  }

  function removeCanvasImage() {
    clearUploadedObjectUrl();
    setCanvasImageUri(null);
    setCanvasImageInput('');
    setCanvasImageMessage(null);
    setCanvasImageHasError(false);
  }

  async function lookupZipRecommendations() {
    const normalizedZipCode = normalizeZipCode(zipCodeInput);
    if (!normalizedZipCode) {
      setZipLookupMessage('Enter a valid 5-digit ZIP code.');
      setZipLookupError(true);
      return;
    }

    setZipLookupLoading(true);
    setZipLookupError(false);
    setZipLookupMessage(
      selectedPlantType === 'any'
        ? 'Looking up Flora recommendations by ZIP...'
        : `Looking up ${selectedPlantTypeLabel.toLowerCase()} recommendations by ZIP...`
    );

    try {
      const typeParam =
        selectedPlantType !== 'any' ? `&plantType=${encodeURIComponent(selectedPlantType)}` : '';
      const response = await fetch(
        `${API_BASE_URL}/api/recommendations/zipcode?zipCode=${encodeURIComponent(normalizedZipCode)}${typeParam}`
      );
      const payload = (await response.json()) as ApiRecommendationsResponse;
      if (!response.ok || payload.error) {
        throw new Error(payload.detail || payload.error || `ZIP lookup failed (${response.status}).`);
      }
      if (!payload.plants?.length) {
        throw new Error('No Flora recommendations were returned for this ZIP code.');
      }

      setPlantLibrary((currentPlants) => mergePlantLists(currentPlants, payload.plants));
      setClimateOptions((currentOptions) => {
        const filtered = currentOptions.filter((profile) => profile.id !== payload.climate.id);
        return [payload.climate, ...filtered];
      });
      setSelectedClimateId(payload.climate.id);
      setRecommendations(payload.plants);
      setActiveZipCode(normalizedZipCode);
      setZipCodeInput(normalizedZipCode);
      setZipLookupError(false);
      const baseMessage =
        selectedPlantType === 'any'
          ? `Loaded ${payload.plants.length} Flora recommendation${
              payload.plants.length === 1 ? '' : 's'
            } for ZIP ${normalizedZipCode}${payload.state ? ` (${payload.state})` : ''}.`
          : `Loaded ${payload.plants.length} ${selectedPlantTypeLabel.toLowerCase()} recommendation${
              payload.plants.length === 1 ? '' : 's'
            } for ZIP ${normalizedZipCode}${payload.state ? ` (${payload.state})` : ''}.`;
      const matchNote =
        selectedPlantType !== 'any' && payload.filterRelaxed
          ? ' Flora returned limited type metadata, so these are closest native matches.'
          : '';
      setZipLookupMessage(`${baseMessage}${matchNote}`);
      setBackendStatus('connected');
      setBackendMessage(`Connected to Flask API (${API_BASE_URL})`);
    } catch (error) {
      setRecommendations([]);
      setActiveZipCode(null);
      setZipLookupError(true);
      setZipLookupMessage(error instanceof Error ? error.message : 'ZIP lookup failed.');
    } finally {
      setZipLookupLoading(false);
    }
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.pageContent}>
      <View style={styles.heroCard}>
        <Text style={styles.heroKicker}>Ecoscape</Text>
        <Text style={styles.heroTitle}>Design your garden and optimize its eco impact!</Text>
        <Text style={styles.heroSubtitle}>
          Enter your ZIP code, drag plants onto the grid, resize coverage, and watch live scores update.
        </Text>
        <View
          style={[
            styles.backendBadge,
            backendStatus === 'connected'
              ? styles.backendBadgeConnected
              : backendStatus === 'checking'
                ? styles.backendBadgeChecking
                : styles.backendBadgeOffline,
          ]}>
          <Text style={styles.backendBadgeTitle}>
            Backend: {backendStatus === 'connected' ? 'Flask connected' : 'Local fallback'}
          </Text>
          <Text style={styles.backendBadgeText}>{backendMessage}</Text>
        </View>
      </View>

      <View style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>1. Garden Setup</Text>
        <View style={styles.dimensionRow}>
          <View style={styles.dimensionField}>
            <Text style={styles.dimensionLabel}>Width (ft)</Text>
            <TextInput
              value={widthInput}
              onChangeText={setWidthInput}
              keyboardType="number-pad"
              style={styles.dimensionInput}
              placeholder="10"
            />
          </View>
          <View style={styles.dimensionField}>
            <Text style={styles.dimensionLabel}>Height (ft)</Text>
            <TextInput
              value={heightInput}
              onChangeText={setHeightInput}
              keyboardType="number-pad"
              style={styles.dimensionInput}
              placeholder="10"
            />
          </View>
          <View style={styles.dimensionSummary}>
            <Text style={styles.dimensionSummaryLabel}>Area</Text>
            <Text style={styles.dimensionSummaryValue}>{gardenAreaSqFt} sq ft</Text>
          </View>
        </View>
        <Text style={styles.sectionHint}>Area is raw from your inputs. Canvas preview is capped at 24x24 ft.</Text>

        <View style={styles.plantTypeCard}>
          <Text style={styles.dimensionLabel}>Plant Type Preference</Text>
          <View style={styles.plantTypeRow}>
            {plantTypeOptions.map((option) => {
              const isSelected = option.id === selectedPlantType;
              return (
                <Pressable
                  key={option.id}
                  onPress={() => {
                    setSelectedPlantType(option.id);
                    if (activeZipCode) {
                      setZipLookupError(false);
                      setZipLookupMessage(
                        `Plant type set to ${option.label}. Click Use ZIP to refresh recommendations.`
                      );
                    }
                  }}
                  style={[styles.plantTypeChip, isSelected ? styles.plantTypeChipSelected : undefined]}>
                  <Text
                    style={[
                      styles.plantTypeChipText,
                      isSelected ? styles.plantTypeChipTextSelected : undefined,
                    ]}>
                    {option.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          <Text style={styles.sectionHint}>Choose what you want to plant before ZIP lookup.</Text>
        </View>

        <View style={styles.zipLookupCard}>
          <Text style={styles.dimensionLabel}>ZIP Code (Flora API)</Text>
          <View style={styles.zipLookupRow}>
            <TextInput
              value={zipCodeInput}
              onChangeText={setZipCodeInput}
              keyboardType="number-pad"
              maxLength={10}
              style={styles.zipLookupInput}
              placeholder="e.g. 94102"
            />
            <Pressable
              onPress={lookupZipRecommendations}
              style={[styles.zipLookupButton, zipLookupLoading ? styles.zipLookupButtonDisabled : undefined]}
              disabled={zipLookupLoading}>
              <Text style={styles.zipLookupButtonText}>{zipLookupLoading ? 'Looking...' : 'Use ZIP'}</Text>
            </Pressable>
          </View>
          {zipLookupMessage ? (
            <Text style={zipLookupError ? styles.zipLookupErrorText : styles.zipLookupInfoText}>
              {zipLookupMessage}
            </Text>
          ) : (
            <Text style={styles.sectionHint}>
              Enter ZIP to pull climate-aware native plants from Flora API through your backend.
            </Text>
          )}
        </View>
      </View>

      <View style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>2. Recommended Plants</Text>
        <Text style={styles.sectionHint}>
          {activeZipCode
            ? selectedPlantType === 'any'
              ? `ZIP-based Flora recommendations for ${selectedClimate.label}.`
              : `ZIP-based ${selectedPlantTypeLabel.toLowerCase()} recommendations for ${selectedClimate.label}.`
            : 'Set a plant type and enter a ZIP code above to load Flora recommendations.'}
        </Text>
        {recommendations.length === 0 ? (
          <View style={styles.emptyRecommendationsCard}>
            <Text style={styles.emptyRecommendationsText}>
              No recommendations loaded yet. Enter a ZIP code and click `Use ZIP`.
            </Text>
          </View>
        ) : (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.plantList}>
            {recommendations.map((plant) => {
              const isNative = plant.nativeRegions.includes(selectedClimate.region);
              return (
                <View key={plant.id} style={styles.plantCard}>
                  <Text style={styles.plantName}>
                    {plant.emoji} {plant.name}
                  </Text>
                  <Text style={styles.plantMeta}>
                    {isNative ? 'Native match' : 'Adaptive pick'} • Water {plant.waterUsage}
                  </Text>
                  <Text style={styles.plantMeta}>
                    Pollinators {plant.pollinatorValue} • Drought {plant.droughtResistance}
                  </Text>
                  <Pressable style={styles.addButton} onPress={() => addPlantToCanvas(plant)}>
                    <Text style={styles.addButtonText}>Add to Canvas</Text>
                  </Pressable>
                </View>
              );
            })}
          </ScrollView>
        )}
      </View>

      <View style={styles.sectionCard}>
        <View style={styles.canvasHeader}>
          <Text style={styles.sectionTitle}>3. Visual Layout Tool</Text>
          <Pressable style={styles.clearButton} onPress={clearCanvas}>
            <Text style={styles.clearButtonText}>Clear</Text>
          </Pressable>
        </View>
        <Text style={styles.sectionHint}>
          Drag plants to arrange them. Select one to resize or remove it from your design.
        </Text>
        <View style={styles.canvasImageBlock}>
          <Text style={styles.dimensionLabel}>Backyard Image URL</Text>
          <TextInput
            value={canvasImageInput}
            onChangeText={setCanvasImageInput}
            style={styles.canvasImageInput}
            placeholder="https://example.com/backyard.jpg"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <View style={styles.canvasImageButtonRow}>
            <Pressable style={styles.uploadImageButton} onPress={uploadCanvasImageFromDevice}>
              <Text style={styles.uploadImageButtonText}>Upload from Device</Text>
            </Pressable>
            <Pressable style={styles.applyImageButton} onPress={applyCanvasImage}>
              <Text style={styles.applyImageButtonText}>Use Image</Text>
            </Pressable>
            <Pressable style={styles.removeImageButton} onPress={removeCanvasImage}>
              <Text style={styles.removeImageButtonText}>Remove Image</Text>
            </Pressable>
          </View>
          {canvasImageMessage ? (
            <Text style={canvasImageHasError ? styles.canvasImageErrorText : styles.canvasImageInfoText}>
              {canvasImageMessage}
            </Text>
          ) : (
            <Text style={styles.sectionHint}>
              Upload from your laptop or paste a hosted image URL to use as the canvas background.
            </Text>
          )}
        </View>

        <View style={styles.canvasShell}>
          <View style={[styles.canvas, { width: canvasWidth, height: canvasHeight }]}>
            {canvasImageUri ? (
              <>
                <Image
                  source={{ uri: canvasImageUri }}
                  style={styles.canvasBackgroundImage}
                  resizeMode="cover"
                  onLoad={() => {
                    setCanvasImageMessage('Backyard image loaded.');
                    setCanvasImageHasError(false);
                  }}
                  onError={() => {
                    setCanvasImageMessage('Could not load image. Check the URL and try again.');
                    setCanvasImageHasError(true);
                  }}
                />
                <View pointerEvents="none" style={styles.canvasImageOverlay} />
              </>
            ) : null}

            {Array.from({ length: canvasWidthFeet + 1 }, (_, index) => (
              <View
                key={`vertical-${index}`}
                style={[
                  styles.gridLineVertical,
                  {
                    left: index * gridUnit,
                  },
                ]}
              />
            ))}
            {Array.from({ length: canvasHeightFeet + 1 }, (_, index) => (
              <View
                key={`horizontal-${index}`}
                style={[
                  styles.gridLineHorizontal,
                  {
                    top: index * gridUnit,
                  },
                ]}
              />
            ))}

            {placedPlants.map((item) => {
              const plant = plantsById[item.plantId];
              if (!plant) {
                return null;
              }
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

            {placedPlants.length === 0 ? (
              <View style={styles.canvasPlaceholder}>
                <Text style={styles.canvasPlaceholderText}>Add plants from the recommendation list.</Text>
              </View>
            ) : null}
          </View>
        </View>

        {selectedPlant && selectedPlantDetails ? (
          <View style={styles.selectionPanel}>
            <Text style={styles.selectionTitle}>
              Selected: {selectedPlantDetails.emoji} {selectedPlantDetails.name}
            </Text>
            <View style={styles.selectionControls}>
              <Pressable style={styles.adjustButton} onPress={() => resizeSelectedPlant(-8)}>
                <Text style={styles.adjustButtonText}>- Size</Text>
              </Pressable>
              <Text style={styles.selectionSize}>Diameter {selectedPlant.size}px</Text>
              <Pressable style={styles.adjustButton} onPress={() => resizeSelectedPlant(8)}>
                <Text style={styles.adjustButtonText}>+ Size</Text>
              </Pressable>
              <Pressable style={styles.removeButton} onPress={removeSelectedPlant}>
                <Text style={styles.removeButtonText}>Remove</Text>
              </Pressable>
            </View>
          </View>
        ) : (
          <Text style={styles.sectionHint}>Tap any placed plant to resize or remove it.</Text>
        )}
      </View>

      <View style={styles.scoreCard}>
        <Text style={styles.sectionTitle}>4. Sustainability Intelligence</Text>
        <View style={styles.scoreHero}>
          <Text style={styles.scoreHeroLabel}>Sustainability Score</Text>
          <Text style={styles.scoreHeroValue}>{metrics.sustainabilityScore}/100</Text>
          <Text style={[styles.scoreHeroPill, { backgroundColor: scoreColor(metrics.sustainabilityScore) }]}>
            {describeScore(metrics.sustainabilityScore)}
          </Text>
        </View>

        <View style={styles.metricGrid}>
          <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>💧 Water Efficiency</Text>
            <Text style={styles.metricValue}>
              {describeScore(metrics.waterEfficiency)} ({metrics.waterEfficiency})
            </Text>
          </View>
          <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>🐝 Pollinator Support</Text>
            <Text style={styles.metricValue}>
              {describeScore(metrics.pollinatorSupport)} ({metrics.pollinatorSupport})
            </Text>
          </View>
          <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>🌿 Native Plant %</Text>
            <Text style={styles.metricValue}>{metrics.nativePercent}%</Text>
          </View>
          <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>☀️ Drought Resistance</Text>
            <Text style={styles.metricValue}>
              {describeScore(metrics.droughtResistance)} ({metrics.droughtResistance})
            </Text>
          </View>
          <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>🌍 Biodiversity Mix</Text>
            <Text style={styles.metricValue}>
              {describeScore(metrics.biodiversity)} ({metrics.biodiversity})
            </Text>
          </View>
          <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>🌳 Carbon Impact</Text>
            <Text style={styles.metricValue}>
              {describeScore(metrics.carbonImpact)} ({metrics.carbonImpact})
            </Text>
          </View>
          <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>🚿 Weekly Water Demand</Text>
            <Text style={styles.metricValue}>{metrics.weeklyWaterDemand} units</Text>
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    backgroundColor: '#eef7ef',
  },
  pageContent: {
    paddingHorizontal: 16,
    paddingTop: 22,
    paddingBottom: 40,
    gap: 14,
  },
  heroCard: {
    backgroundColor: '#0f3d2d',
    borderRadius: 20,
    paddingHorizontal: 18,
    paddingVertical: 20,
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 4,
  },
  heroKicker: {
    color: '#9ce7b6',
    fontSize: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    fontWeight: '700',
    marginBottom: 6,
  },
  heroTitle: {
    color: '#f1fff5',
    fontSize: 26,
    fontWeight: '800',
    lineHeight: 32,
    marginBottom: 8,
  },
  heroSubtitle: {
    color: '#ccead7',
    fontSize: 14,
    lineHeight: 20,
  },
  backendBadge: {
    marginTop: 12,
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  backendBadgeConnected: {
    borderColor: '#45b57d',
    backgroundColor: '#0d5b3d',
  },
  backendBadgeChecking: {
    borderColor: '#a88f39',
    backgroundColor: '#5b4f17',
  },
  backendBadgeOffline: {
    borderColor: '#d18f6f',
    backgroundColor: '#5a2f20',
  },
  backendBadgeTitle: {
    color: '#f5fff8',
    fontSize: 12,
    fontWeight: '700',
  },
  backendBadgeText: {
    marginTop: 2,
    color: '#d7f0df',
    fontSize: 11,
    lineHeight: 16,
  },
  sectionCard: {
    backgroundColor: '#ffffff',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#d9e9dd',
    padding: 14,
    gap: 10,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#173a2b',
  },
  sectionHint: {
    color: '#4f6759',
    fontSize: 13,
    lineHeight: 18,
  },
  dimensionRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-end',
  },
  dimensionField: {
    flex: 1,
    gap: 6,
  },
  dimensionLabel: {
    color: '#304f3d',
    fontSize: 12,
    fontWeight: '600',
  },
  dimensionInput: {
    borderWidth: 1,
    borderColor: '#b8d5c1',
    borderRadius: 12,
    backgroundColor: '#f4fbf5',
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    color: '#12271d',
    fontWeight: '700',
  },
  dimensionSummary: {
    minWidth: 96,
    backgroundColor: '#e7f6ea',
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#c9e8d1',
  },
  dimensionSummaryLabel: {
    fontSize: 11,
    color: '#3f6a52',
    fontWeight: '600',
  },
  dimensionSummaryValue: {
    fontSize: 16,
    color: '#175337',
    fontWeight: '800',
    marginTop: 2,
  },
  plantTypeCard: {
    borderWidth: 1,
    borderColor: '#cde2d4',
    borderRadius: 12,
    backgroundColor: '#f6fcf7',
    padding: 10,
    gap: 8,
  },
  plantTypeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  plantTypeChip: {
    borderWidth: 1,
    borderColor: '#c6ddd0',
    backgroundColor: '#ffffff',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  plantTypeChipSelected: {
    borderColor: '#0f8a5b',
    backgroundColor: '#e6f9ee',
  },
  plantTypeChipText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#365747',
  },
  plantTypeChipTextSelected: {
    color: '#0f6845',
  },
  zipLookupCard: {
    borderWidth: 1,
    borderColor: '#cde2d4',
    borderRadius: 12,
    backgroundColor: '#f6fcf7',
    padding: 10,
    gap: 8,
  },
  zipLookupRow: {
    flexDirection: 'row',
    gap: 8,
  },
  zipLookupInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#b8d5c1',
    borderRadius: 10,
    backgroundColor: '#ffffff',
    paddingHorizontal: 10,
    paddingVertical: 9,
    color: '#173a2b',
    fontSize: 14,
    fontWeight: '600',
  },
  zipLookupButton: {
    minWidth: 98,
    borderRadius: 10,
    backgroundColor: '#145b7b',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
  },
  zipLookupButtonDisabled: {
    backgroundColor: '#6d8a98',
  },
  zipLookupButtonText: {
    color: '#ecf8ff',
    fontWeight: '700',
    fontSize: 12,
  },
  zipLookupInfoText: {
    color: '#2f5e47',
    fontSize: 12,
    lineHeight: 18,
  },
  zipLookupErrorText: {
    color: '#a53a1a',
    fontSize: 12,
    lineHeight: 18,
    fontWeight: '600',
  },
  plantList: {
    gap: 10,
    paddingRight: 8,
  },
  emptyRecommendationsCard: {
    borderWidth: 1,
    borderColor: '#d2e4d7',
    borderRadius: 12,
    backgroundColor: '#f7fcf8',
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  emptyRecommendationsText: {
    color: '#3d5f4c',
    fontSize: 13,
    lineHeight: 19,
  },
  plantCard: {
    width: 230,
    borderWidth: 1,
    borderColor: '#cfe5d5',
    borderRadius: 14,
    padding: 12,
    backgroundColor: '#f8fdf9',
    gap: 5,
  },
  plantName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#1a4733',
  },
  plantMeta: {
    fontSize: 12,
    color: '#4e6a59',
  },
  addButton: {
    marginTop: 6,
    borderRadius: 10,
    backgroundColor: '#116f49',
    paddingVertical: 9,
    alignItems: 'center',
  },
  addButtonText: {
    color: '#edfff4',
    fontWeight: '700',
    fontSize: 13,
  },
  canvasImageBlock: {
    borderWidth: 1,
    borderColor: '#d3e5d8',
    borderRadius: 12,
    backgroundColor: '#f6fcf7',
    padding: 10,
    gap: 8,
  },
  canvasImageInput: {
    borderWidth: 1,
    borderColor: '#b8d5c1',
    borderRadius: 10,
    backgroundColor: '#ffffff',
    paddingHorizontal: 10,
    paddingVertical: 9,
    color: '#173a2b',
    fontSize: 14,
  },
  canvasImageButtonRow: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  uploadImageButton: {
    flex: 1,
    minWidth: 120,
    borderRadius: 10,
    backgroundColor: '#0f5a79',
    alignItems: 'center',
    paddingVertical: 9,
  },
  uploadImageButtonText: {
    color: '#ecf8ff',
    fontSize: 12,
    fontWeight: '700',
  },
  applyImageButton: {
    flex: 1,
    minWidth: 92,
    borderRadius: 10,
    backgroundColor: '#146e48',
    alignItems: 'center',
    paddingVertical: 9,
  },
  applyImageButtonText: {
    color: '#ecfff3',
    fontSize: 12,
    fontWeight: '700',
  },
  removeImageButton: {
    flex: 1,
    minWidth: 92,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#d0dcd4',
    backgroundColor: '#ffffff',
    alignItems: 'center',
    paddingVertical: 9,
  },
  removeImageButtonText: {
    color: '#2e5340',
    fontSize: 12,
    fontWeight: '700',
  },
  canvasImageInfoText: {
    color: '#35694f',
    fontSize: 12,
    lineHeight: 18,
  },
  canvasImageErrorText: {
    color: '#a53a1a',
    fontSize: 12,
    lineHeight: 18,
    fontWeight: '600',
  },
  canvasHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  clearButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#d4e5d8',
    backgroundColor: '#f6fcf7',
  },
  clearButtonText: {
    fontSize: 12,
    color: '#2f5240',
    fontWeight: '700',
  },
  canvasShell: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#cbe2d1',
    backgroundColor: '#edf7ef',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 8,
  },
  canvas: {
    position: 'relative',
    borderWidth: 2,
    borderColor: '#95bba0',
    borderRadius: 12,
    backgroundColor: '#f8fff8',
    overflow: 'hidden',
  },
  canvasBackgroundImage: {
    ...StyleSheet.absoluteFillObject,
  },
  canvasImageOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(12, 27, 18, 0.24)',
  },
  gridLineVertical: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 1,
    backgroundColor: '#d8e9db',
  },
  gridLineHorizontal: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 1,
    backgroundColor: '#d8e9db',
  },
  canvasPlaceholder: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  canvasPlaceholderText: {
    color: '#64806d',
    textAlign: 'center',
    fontSize: 13,
  },
  placedPlant: {
    position: 'absolute',
    borderRadius: 999,
    borderWidth: 2,
    borderColor: '#315446',
    backgroundColor: '#d5f0de',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2,
  },
  placedPlantSelected: {
    borderColor: '#0a7e52',
    backgroundColor: '#c0efd0',
    transform: [{ scale: 1.03 }],
  },
  placedPlantEmoji: {
    fontSize: 22,
  },
  selectionPanel: {
    marginTop: 2,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#cfe4d4',
    backgroundColor: '#f4fbf6',
    padding: 10,
    gap: 8,
  },
  selectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1f4836',
  },
  selectionControls: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    alignItems: 'center',
  },
  adjustButton: {
    backgroundColor: '#166f4b',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  adjustButtonText: {
    color: '#effff4',
    fontWeight: '700',
    fontSize: 12,
  },
  selectionSize: {
    color: '#27513d',
    fontWeight: '600',
    fontSize: 13,
  },
  removeButton: {
    borderWidth: 1,
    borderColor: '#d9b0a2',
    backgroundColor: '#fff5f2',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  removeButtonText: {
    color: '#9f3412',
    fontWeight: '700',
    fontSize: 12,
  },
  scoreCard: {
    backgroundColor: '#153726',
    borderRadius: 18,
    padding: 16,
    gap: 12,
  },
  scoreHero: {
    backgroundColor: '#1f5138',
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: '#2c6a4b',
  },
  scoreHeroLabel: {
    color: '#c7ebd5',
    fontSize: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    fontWeight: '700',
  },
  scoreHeroValue: {
    marginTop: 6,
    color: '#effff4',
    fontSize: 36,
    fontWeight: '900',
  },
  scoreHeroPill: {
    marginTop: 8,
    alignSelf: 'flex-start',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
    color: '#ffffff',
    overflow: 'hidden',
    fontSize: 12,
    fontWeight: '700',
  },
  metricGrid: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#2b684a',
    backgroundColor: '#1c4632',
    overflow: 'hidden',
  },
  metricRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#275a42',
  },
  metricLabel: {
    color: '#cfe9d8',
    fontSize: 13,
    fontWeight: '600',
  },
  metricValue: {
    color: '#f3fff7',
    fontSize: 13,
    fontWeight: '700',
  },
});
