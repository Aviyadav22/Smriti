import { useRef, useMemo, useState, useEffect, useCallback, Suspense } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import * as THREE from "three";

const SPHERE_COUNT = 200;
const GROUP_COUNT = 7;

const GROUP_COLORS = [
  "#C5A880", // chunk - gold
  "#D4B896", // proposition - light gold
  "#B89A6E", // ratio - deeper gold
  "#E0C9A6", // headnote - pale gold
  "#A88D5E", // statute - bronze gold
  "#CFBA94", // summary - warm gold
  "#9B8050", // community - dark gold
];

const GROUP_CENTERS: [number, number, number][] = [
  [0, 2, 0],
  [2.5, 0.7, 1],
  [-2.5, 0.7, 1],
  [1.5, -1.5, -1],
  [-1.5, -1.5, -1],
  [0, -0.5, 2.5],
  [0, 0.5, -2.5],
];

interface SphereData {
  randomPos: THREE.Vector3;
  group: number;
  clusterPos: THREE.Vector3;
  color: THREE.Color;
}

function generateSpheres(): SphereData[] {
  const spheres: SphereData[] = [];
  for (let i = 0; i < SPHERE_COUNT; i++) {
    const group = i % GROUP_COUNT;
    const center = GROUP_CENTERS[group];
    const clusterOffset = new THREE.Vector3(
      (Math.random() - 0.5) * 1.2,
      (Math.random() - 0.5) * 1.2,
      (Math.random() - 0.5) * 1.2
    );
    spheres.push({
      randomPos: new THREE.Vector3(
        (Math.random() - 0.5) * 10,
        (Math.random() - 0.5) * 10,
        (Math.random() - 0.5) * 10
      ),
      group,
      clusterPos: new THREE.Vector3(
        center[0] + clusterOffset.x,
        center[1] + clusterOffset.y,
        center[2] + clusterOffset.z
      ),
      color: new THREE.Color(GROUP_COLORS[group]),
    });
  }
  return spheres;
}

function VectorSphere({
  data,
  scrollProgress,
}: {
  data: SphereData;
  scrollProgress: React.RefObject<number>;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const phaseOffset = useMemo(() => Math.random() * Math.PI * 2, []);

  useFrame((state) => {
    if (!meshRef.current) return;
    const s = scrollProgress.current;
    const eased = s * s * (3 - 2 * s);

    const x = THREE.MathUtils.lerp(data.randomPos.x, data.clusterPos.x, eased);
    const y = THREE.MathUtils.lerp(data.randomPos.y, data.clusterPos.y, eased);
    const z = THREE.MathUtils.lerp(data.randomPos.z, data.clusterPos.z, eased);

    const wobble = Math.sin(state.clock.elapsedTime * 0.5 + phaseOffset) * 0.05;
    meshRef.current.position.set(x + wobble, y + wobble, z + wobble);

    const scale = 0.04 + eased * 0.02;
    meshRef.current.scale.setScalar(scale);
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshStandardMaterial
        color={data.color}
        emissive={data.color}
        emissiveIntensity={0.8}
        toneMapped={false}
      />
    </mesh>
  );
}

function Scene() {
  const scrollProgress = useRef(0);
  const sphereData = useMemo(generateSpheres, []);
  const [mounted, setMounted] = useState(false);

  const handleScroll = useCallback(() => {
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    scrollProgress.current = maxScroll > 0 ? window.scrollY / maxScroll : 0;
  }, []);

  useEffect(() => {
    setMounted(true);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  if (!mounted) return null;

  return (
    <>
      <ambientLight intensity={0.2} />
      <pointLight position={[5, 5, 5]} intensity={0.6} color="#C5A880" />
      <pointLight position={[-5, -5, -5]} intensity={0.3} color="#C5A880" />

      {sphereData.map((data, i) => (
        <VectorSphere key={i} data={data} scrollProgress={scrollProgress} />
      ))}

      <EffectComposer>
        <Bloom
          luminanceThreshold={0.3}
          luminanceSmoothing={0.5}
          intensity={1.5}
        />
      </EffectComposer>
    </>
  );
}

function LoadingFallback() {
  return (
    <mesh>
      <sphereGeometry args={[0.3, 16, 16]} />
      <meshBasicMaterial color="#C5A880" wireframe />
    </mesh>
  );
}

export default function VectorCloud() {
  return (
    <Canvas
      camera={{ position: [0, 0, 8], fov: 60 }}
      style={{ width: "100%", height: "100%", background: "#0A0A0A" }}
      gl={{ antialias: true }}
    >
      <Suspense fallback={<LoadingFallback />}>
        <Scene />
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          autoRotate
          autoRotateSpeed={0.5}
        />
      </Suspense>
    </Canvas>
  );
}
