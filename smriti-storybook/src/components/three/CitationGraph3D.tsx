import { useRef, useMemo, useState, Suspense, useCallback } from "react";
import { Canvas, useFrame, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Html, Float } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import * as THREE from "three";

const GOLD = "#C5A880";
const RED = "#FF4444";
const NODE_COUNT = 25;
const EDGE_COUNT = 40;

interface NodeData {
  id: number;
  position: THREE.Vector3;
  label: string;
  phase: number;
}

interface EdgeData {
  from: number;
  to: number;
  overruled: boolean;
}

const CASE_LABELS = [
  "Kesavananda v State",
  "Maneka Gandhi v UOI",
  "Minerva Mills v UOI",
  "Golaknath v Punjab",
  "IR Coelho v Tamil Nadu",
  "ADM Jabalpur v Shukla",
  "Vishaka v Rajasthan",
  "MC Mehta v UOI",
  "Olga Tellis v BMC",
  "KS Puttaswamy v UOI",
  "Navtej Johar v UOI",
  "Joseph Shine v UOI",
  "Indian Young Lawyers v UOI",
  "Shayara Bano v UOI",
  "Common Cause v UOI",
  "NALSA v UOI",
  "SR Bommai v UOI",
  "Indra Sawhney v UOI",
  "State of WB v SN Basak",
  "Bachan Singh v Punjab",
  "Hussainara Khatoon v Bihar",
  "Bandhua Mukti v UOI",
  "Khatri v State of Bihar",
  "Sunil Batra v Delhi",
  "DK Basu v State of WB",
];

function generateGraph(): { nodes: NodeData[]; edges: EdgeData[] } {
  const nodes: NodeData[] = [];
  for (let i = 0; i < NODE_COUNT; i++) {
    const phi = Math.acos(1 - (2 * (i + 0.5)) / NODE_COUNT);
    const theta = Math.PI * (1 + Math.sqrt(5)) * i;
    const r = 3;
    nodes.push({
      id: i,
      position: new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta),
        r * Math.cos(phi)
      ),
      label: CASE_LABELS[i],
      phase: Math.random() * Math.PI * 2,
    });
  }

  const edges: EdgeData[] = [];
  const edgeSet = new Set<string>();
  // Overruled edges
  const overruledPairs: [number, number][] = [
    [0, 3],
    [5, 1],
    [9, 5],
  ];
  for (const [from, to] of overruledPairs) {
    edges.push({ from, to, overruled: true });
    edgeSet.add(`${from}-${to}`);
  }

  // Regular edges
  let attempts = 0;
  while (edges.length < EDGE_COUNT && attempts < 200) {
    const from = Math.floor(Math.random() * NODE_COUNT);
    const to = Math.floor(Math.random() * NODE_COUNT);
    const key = `${from}-${to}`;
    if (from !== to && !edgeSet.has(key)) {
      edges.push({ from, to, overruled: false });
      edgeSet.add(key);
    }
    attempts++;
  }

  return { nodes, edges };
}

function GraphNode({
  data,
  onHover,
  onUnhover,
  isHovered,
}: {
  data: NodeData;
  onHover: (id: number) => void;
  onUnhover: () => void;
  isHovered: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!meshRef.current) return;
    const t = state.clock.elapsedTime;
    const wobble = Math.sin(t * 0.7 + data.phase) * 0.08;
    meshRef.current.position.set(
      data.position.x + wobble,
      data.position.y + Math.sin(t * 0.5 + data.phase) * 0.1,
      data.position.z + wobble * 0.5
    );
  });

  const handlePointerOver = useCallback(
    (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      onHover(data.id);
    },
    [data.id, onHover]
  );

  const handlePointerOut = useCallback(
    (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      onUnhover();
    },
    [onUnhover]
  );

  const goldColor = useMemo(() => new THREE.Color(GOLD), []);

  return (
    <Float speed={1} rotationIntensity={0} floatIntensity={0.3}>
      <mesh
        ref={meshRef}
        position={data.position}
        onPointerOver={handlePointerOver}
        onPointerOut={handlePointerOut}
      >
        <sphereGeometry args={[isHovered ? 0.18 : 0.13, 16, 16]} />
        <meshStandardMaterial
          color={GOLD}
          emissive={goldColor}
          emissiveIntensity={isHovered ? 1.2 : 0.5}
          toneMapped={false}
        />
      </mesh>
      {isHovered && (
        <Html
          position={[
            data.position.x,
            data.position.y + 0.35,
            data.position.z,
          ]}
          center
          style={{
            pointerEvents: "none",
            whiteSpace: "nowrap",
          }}
        >
          <div
            style={{
              background: "#1A1A1A",
              color: GOLD,
              padding: "4px 10px",
              borderRadius: "4px",
              fontSize: "11px",
              fontFamily: "monospace",
              border: `1px solid ${GOLD}`,
            }}
          >
            {data.label}
          </div>
        </Html>
      )}
    </Float>
  );
}

function GraphEdge({
  fromPos,
  toPos,
  overruled,
}: {
  fromPos: THREE.Vector3;
  toPos: THREE.Vector3;
  overruled: boolean;
}) {
  const lineRef = useRef<THREE.Line>(null);
  const phaseRef = useRef(Math.random() * Math.PI * 2);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry().setFromPoints([fromPos, toPos]);
    return geo;
  }, [fromPos, toPos]);

  const line = useMemo(() => {
    const mat = new THREE.LineBasicMaterial({
      color: overruled ? RED : GOLD,
      transparent: true,
      opacity: 0.5,
    });
    return new THREE.Line(geometry, mat);
  }, [geometry, overruled]);

  useFrame((state) => {
    const mat = line.material as THREE.LineBasicMaterial;
    const pulse =
      0.4 + Math.sin(state.clock.elapsedTime * 2 + phaseRef.current) * 0.3;
    mat.opacity = pulse;
  });

  return <primitive ref={lineRef} object={line} />;
}

function Scene() {
  const [hoveredNode, setHoveredNode] = useState<number | null>(null);
  const { nodes, edges } = useMemo(generateGraph, []);

  const handleHover = useCallback((id: number) => setHoveredNode(id), []);
  const handleUnhover = useCallback(() => setHoveredNode(null), []);

  return (
    <>
      <ambientLight intensity={0.3} />
      <pointLight position={[5, 5, 5]} intensity={0.8} color={GOLD} />
      <pointLight position={[-4, -3, 3]} intensity={0.4} />

      {nodes.map((node) => (
        <GraphNode
          key={node.id}
          data={node}
          onHover={handleHover}
          onUnhover={handleUnhover}
          isHovered={hoveredNode === node.id}
        />
      ))}

      {edges.map((edge, i) => (
        <GraphEdge
          key={i}
          fromPos={nodes[edge.from].position}
          toPos={nodes[edge.to].position}
          overruled={edge.overruled}
        />
      ))}

      <EffectComposer>
        <Bloom
          luminanceThreshold={0.4}
          luminanceSmoothing={0.4}
          intensity={1.2}
        />
      </EffectComposer>
    </>
  );
}

function LoadingFallback() {
  return (
    <mesh>
      <sphereGeometry args={[0.3, 16, 16]} />
      <meshBasicMaterial color={GOLD} wireframe />
    </mesh>
  );
}

export default function CitationGraph3D() {
  return (
    <Canvas
      camera={{ position: [0, 0, 7], fov: 55 }}
      style={{ width: "100%", height: "100%", background: "#0A0A0A" }}
      gl={{ antialias: true }}
    >
      <Suspense fallback={<LoadingFallback />}>
        <Scene />
        <OrbitControls
          enableZoom={true}
          enablePan={false}
          autoRotate
          autoRotateSpeed={0.4}
          minDistance={4}
          maxDistance={12}
        />
      </Suspense>
    </Canvas>
  );
}
