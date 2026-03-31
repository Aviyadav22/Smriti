import { useRef, useMemo, useState, Suspense, useCallback } from "react";
import { Canvas, useFrame, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Text, Html } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import * as THREE from "three";

const GOLD = "#C5A880";

interface ServiceNode {
  name: string;
  role: string;
  position: [number, number, number];
  shape: "box" | "sphere";
  color: string;
}

const SERVICES: ServiceNode[] = [
  {
    name: "PostgreSQL",
    role: "Primary database for metadata, full-text search via tsvector",
    position: [-2.5, 1.5, 0],
    shape: "box",
    color: "#336791",
  },
  {
    name: "Pinecone",
    role: "Vector database for semantic search (1536-dim, 7 vector types)",
    position: [2.5, 1.5, 0],
    shape: "sphere",
    color: "#00B4AB",
  },
  {
    name: "Neo4j",
    role: "Graph database for citation relationships between judgments",
    position: [0, 2.5, -1],
    shape: "sphere",
    color: "#018BFF",
  },
  {
    name: "Gemini",
    role: "LLM for reasoning (3.1 Pro) and fast tasks (3 Flash)",
    position: [-2, -1.5, 0.5],
    shape: "box",
    color: "#886FBF",
  },
  {
    name: "Cloud Run",
    role: "Serverless container hosting for FastAPI backend",
    position: [2, -1.5, 0.5],
    shape: "box",
    color: "#4285F4",
  },
  {
    name: "Redis",
    role: "Cache layer for search results and rate limiting (Upstash)",
    position: [0, -0.5, 2],
    shape: "sphere",
    color: "#DC382D",
  },
];

const CONNECTIONS: [number, number][] = [
  [0, 4], // PostgreSQL <-> Cloud Run
  [1, 4], // Pinecone <-> Cloud Run
  [2, 4], // Neo4j <-> Cloud Run
  [3, 4], // Gemini <-> Cloud Run
  [5, 4], // Redis <-> Cloud Run
  [0, 2], // PostgreSQL <-> Neo4j
  [1, 3], // Pinecone <-> Gemini
  [0, 1], // PostgreSQL <-> Pinecone
];

function ServiceMesh({
  service,
  onSelect,
  isSelected,
}: {
  service: ServiceNode;
  onSelect: (name: string) => void;
  isSelected: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const phaseRef = useRef(Math.random() * Math.PI * 2);

  useFrame((state) => {
    if (!meshRef.current) return;
    const t = state.clock.elapsedTime;
    const bob = Math.sin(t * 0.6 + phaseRef.current) * 0.08;
    meshRef.current.position.set(
      service.position[0],
      service.position[1] + bob,
      service.position[2]
    );
    if (isSelected) {
      meshRef.current.scale.setScalar(1.15 + Math.sin(t * 3) * 0.05);
    } else {
      meshRef.current.scale.setScalar(1);
    }
  });

  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      onSelect(service.name);
    },
    [service.name, onSelect]
  );

  const emissiveColor = useMemo(
    () => new THREE.Color(service.color),
    [service.color]
  );

  return (
    <group>
      <mesh
        ref={meshRef}
        position={service.position}
        onClick={handleClick}
      >
        {service.shape === "box" ? (
          <boxGeometry args={[0.6, 0.6, 0.6]} />
        ) : (
          <sphereGeometry args={[0.35, 16, 16]} />
        )}
        <meshStandardMaterial
          color={service.color}
          emissive={emissiveColor}
          emissiveIntensity={isSelected ? 0.8 : 0.3}
          toneMapped={false}
        />
      </mesh>
      <Text
        position={[
          service.position[0],
          service.position[1] - (service.shape === "box" ? 0.55 : 0.5),
          service.position[2],
        ]}
        fontSize={0.18}
        color={GOLD}
        anchorX="center"
        anchorY="top"
        font={undefined}
      >
        {service.name}
      </Text>
    </group>
  );
}

function ConnectionLine({
  from,
  to,
  index,
}: {
  from: [number, number, number];
  to: [number, number, number];
  index: number;
}) {
  const lineRef = useRef<THREE.Line>(null);

  const line = useMemo(() => {
    const fromVec = new THREE.Vector3(...from);
    const toVec = new THREE.Vector3(...to);
    const geometry = new THREE.BufferGeometry().setFromPoints([fromVec, toVec]);
    const material = new THREE.LineBasicMaterial({
      color: GOLD,
      transparent: true,
      opacity: 0.4,
    });
    return new THREE.Line(geometry, material);
  }, [from, to]);

  useFrame((state) => {
    const mat = line.material as THREE.LineBasicMaterial;
    const pulse =
      0.2 + Math.sin(state.clock.elapsedTime * 1.5 + index * 0.8) * 0.25;
    mat.opacity = pulse;
  });

  return <primitive ref={lineRef} object={line} />;
}

function Scene() {
  const [selectedService, setSelectedService] = useState<string | null>(null);

  const handleSelect = useCallback((name: string) => {
    setSelectedService((prev) => (prev === name ? null : name));
  }, []);

  const handleMiss = useCallback(() => {
    setSelectedService(null);
  }, []);

  const selectedData = useMemo(
    () => SERVICES.find((s) => s.name === selectedService),
    [selectedService]
  );

  return (
    <>
      <ambientLight intensity={0.35} />
      <pointLight position={[4, 4, 4]} intensity={0.8} color={GOLD} />
      <pointLight position={[-3, -2, 3]} intensity={0.4} />

      <group onPointerMissed={handleMiss}>
        {SERVICES.map((service) => (
          <ServiceMesh
            key={service.name}
            service={service}
            onSelect={handleSelect}
            isSelected={selectedService === service.name}
          />
        ))}
      </group>

      {CONNECTIONS.map(([fromIdx, toIdx], i) => (
        <ConnectionLine
          key={i}
          from={SERVICES[fromIdx].position}
          to={SERVICES[toIdx].position}
          index={i}
        />
      ))}

      {selectedData && (
        <Html
          position={[
            selectedData.position[0],
            selectedData.position[1] + 0.7,
            selectedData.position[2],
          ]}
          center
          style={{ pointerEvents: "none" }}
        >
          <div
            style={{
              background: "#1A1A1A",
              color: "#E0E0E0",
              padding: "8px 14px",
              borderRadius: "6px",
              fontSize: "12px",
              fontFamily: "system-ui, sans-serif",
              border: `1px solid ${GOLD}`,
              maxWidth: "220px",
              textAlign: "center",
              lineHeight: "1.4",
            }}
          >
            <div
              style={{
                color: GOLD,
                fontWeight: 600,
                marginBottom: "4px",
                fontSize: "13px",
              }}
            >
              {selectedData.name}
            </div>
            {selectedData.role}
          </div>
        </Html>
      )}

      <EffectComposer>
        <Bloom
          luminanceThreshold={0.5}
          luminanceSmoothing={0.4}
          intensity={0.8}
        />
      </EffectComposer>
    </>
  );
}

function LoadingFallback() {
  return (
    <mesh>
      <boxGeometry args={[0.4, 0.4, 0.4]} />
      <meshBasicMaterial color={GOLD} wireframe />
    </mesh>
  );
}

export default function ArchitectureMap() {
  return (
    <Canvas
      camera={{ position: [0, 0, 7], fov: 50 }}
      style={{ width: "100%", height: "100%", background: "#0A0A0A" }}
      gl={{ antialias: true }}
    >
      <Suspense fallback={<LoadingFallback />}>
        <Scene />
        <OrbitControls
          enableZoom={true}
          enablePan={false}
          autoRotate
          autoRotateSpeed={0.3}
          minDistance={4}
          maxDistance={12}
        />
      </Suspense>
    </Canvas>
  );
}
