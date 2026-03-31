import { useRef, useMemo, useEffect, useCallback, Suspense } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Instances, Instance, OrbitControls } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import * as THREE from "three";

const PAGE_COUNT = 50;
const GOLD = "#C5A880";

interface PageData {
  stackPos: [number, number, number];
  scatterPos: [number, number, number];
  scatterRot: [number, number, number];
  gridPos: [number, number, number];
}

function generatePageData(): PageData[] {
  const pages: PageData[] = [];
  const cols = 10;
  for (let i = 0; i < PAGE_COUNT; i++) {
    const stackY = i * 0.06 - (PAGE_COUNT * 0.06) / 2;
    const angle = Math.random() * Math.PI * 2;
    const radius = 2 + Math.random() * 3;
    const scatterX = Math.cos(angle) * radius;
    const scatterY = (Math.random() - 0.5) * 4;
    const scatterZ = Math.sin(angle) * radius;
    const gridRow = Math.floor(i / cols);
    const gridCol = i % cols;
    const gridX = (gridCol - cols / 2) * 0.55;
    const gridY = (gridRow - Math.floor(PAGE_COUNT / cols) / 2) * 0.75;
    pages.push({
      stackPos: [0, stackY, 0],
      scatterPos: [scatterX, scatterY, scatterZ],
      scatterRot: [
        Math.random() * Math.PI,
        Math.random() * Math.PI,
        Math.random() * Math.PI,
      ],
      gridPos: [gridX, gridY, 0],
    });
  }
  return pages;
}

function lerp3(
  a: [number, number, number],
  b: [number, number, number],
  t: number
): [number, number, number] {
  return [
    a[0] + (b[0] - a[0]) * t,
    a[1] + (b[1] - a[1]) * t,
    a[2] + (b[2] - a[2]) * t,
  ];
}

function PageInstance({
  data,
  scrollProgress,
}: {
  data: PageData;
  scrollProgress: React.RefObject<number>;
}) {
  const ref = useRef<THREE.Group>(null);

  useFrame(() => {
    if (!ref.current) return;
    const s = scrollProgress.current;
    let pos: [number, number, number];
    let rotX = 0,
      rotY = 0,
      rotZ = 0;

    if (s < 0.5) {
      const t = Math.min(s * 2, 1);
      const eased = t * t * (3 - 2 * t);
      pos = lerp3(data.stackPos, data.scatterPos, eased);
      rotX = data.scatterRot[0] * eased;
      rotY = data.scatterRot[1] * eased;
      rotZ = data.scatterRot[2] * eased;
    } else {
      const t = Math.min((s - 0.5) * 2, 1);
      const eased = t * t * (3 - 2 * t);
      pos = lerp3(data.scatterPos, data.gridPos, eased);
      rotX = data.scatterRot[0] * (1 - eased);
      rotY = data.scatterRot[1] * (1 - eased);
      rotZ = data.scatterRot[2] * (1 - eased);
    }

    ref.current.position.set(pos[0], pos[1], pos[2]);
    ref.current.rotation.set(rotX, rotY, rotZ);
  });

  return <Instance ref={ref} />;
}

function Scene() {
  const scrollProgress = useRef(0);
  const groupRef = useRef<THREE.Group>(null);
  const pageData = useMemo(generatePageData, []);

  const handleScroll = useCallback(() => {
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    scrollProgress.current = maxScroll > 0 ? window.scrollY / maxScroll : 0;
  }, []);

  useEffect(() => {
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  useFrame((_state, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.08;
    }
  });

  const edgeColor = useMemo(() => new THREE.Color(GOLD), []);

  return (
    <group ref={groupRef}>
      <ambientLight intensity={0.4} />
      <pointLight position={[5, 5, 5]} intensity={1} color={GOLD} />
      <pointLight position={[-5, -3, -5]} intensity={0.5} />

      <Instances limit={PAGE_COUNT}>
        <boxGeometry args={[0.4, 0.55, 0.015]} />
        <meshStandardMaterial
          color="#F5F0E8"
          emissive={edgeColor}
          emissiveIntensity={0.15}
        />
        {pageData.map((data, i) => (
          <PageInstance
            key={i}
            data={data}
            scrollProgress={scrollProgress}
          />
        ))}
      </Instances>

      <EffectComposer>
        <Bloom
          luminanceThreshold={0.6}
          luminanceSmoothing={0.4}
          intensity={0.8}
        />
      </EffectComposer>
    </group>
  );
}

function LoadingFallback() {
  return (
    <mesh>
      <boxGeometry args={[0.5, 0.5, 0.5]} />
      <meshBasicMaterial color={GOLD} wireframe />
    </mesh>
  );
}

export default function JudgmentExplode() {
  return (
    <Canvas
      camera={{ position: [0, 0, 6], fov: 50 }}
      style={{ width: "100%", height: "100%", background: "#0A0A0A" }}
      gl={{ antialias: true }}
    >
      <Suspense fallback={<LoadingFallback />}>
        <Scene />
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          autoRotate
          autoRotateSpeed={0.3}
        />
      </Suspense>
    </Canvas>
  );
}
