import React, { useRef, useMemo, useState, useEffect } from 'react';
import { Canvas, useFrame, ThreeElements } from '@react-three/fiber';

// Declare Three.js elements as valid JSX intrinsic elements
declare global {
    namespace JSX {
        interface IntrinsicElements extends ThreeElements { }
    }
}
import { OrbitControls, Html, Stars } from '@react-three/drei';
import * as THREE from 'three';



// =============================================================================
// Types
// =============================================================================

interface EntropySource {
    id: string;
    name: string;
    icon: string;
    color: string;
    available: boolean;
    quality: number;
    latitude?: number;
    longitude?: number;
    activity?: any;
}

interface EntropyGlobeProps {
    sources: EntropySource[];
    onSourceClick?: (source: EntropySource) => void;
    autoRotate?: boolean;
    showParticles?: boolean;
}

interface EntropyParticle {
    position: [number, number, number];
    velocity: [number, number, number];
    color: string;
    source: string;
    age: number;
}

// =============================================================================
// 3D Globe Component
// =============================================================================

// Convert lat/lng to 3D position on sphere
function latLngToPosition(lat: number, lng: number, radius: number): [number, number, number] {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lng + 180) * (Math.PI / 180);

    const x = -(radius * Math.sin(phi) * Math.cos(theta));
    const y = radius * Math.cos(phi);
    const z = radius * Math.sin(phi) * Math.sin(theta);

    return [x, y, z];
}

// Animated marker for entropy sources
function SourceMarker({ source, radius, onClick }: {
    source: EntropySource;
    radius: number;
    onClick?: () => void
}) {
    const meshRef = useRef<THREE.Mesh>(null);
    const [hovered, setHovered] = useState(false);

    // Memoize position to prevent it from changing on every render
    const position = useMemo(() => {
        const lat = source.latitude ?? Math.random() * 180 - 90;
        const lng = source.longitude ?? Math.random() * 360 - 180;
        return latLngToPosition(lat, lng, radius + 0.05);
    }, [source.latitude, source.longitude, radius]);

    useFrame((state) => {
        if (meshRef.current) {
            // Pulsing effect based on quality
            const scale = 1 + Math.sin(state.clock.elapsedTime * 3) * 0.1 * source.quality;
            meshRef.current.scale.setScalar(scale * (hovered ? 1.3 : 1));
        }
    });

    return (
        <group position={position}>
            <mesh
                ref={meshRef}
                onClick={onClick}
                onPointerOver={() => setHovered(true)}
                onPointerOut={() => setHovered(false)}
            >
                <sphereGeometry args={[0.05, 16, 16]} />
                <meshStandardMaterial
                    color={source.color}
                    emissive={source.color}
                    emissiveIntensity={source.quality * 0.5}
                />
            </mesh>
            {hovered && (
                <Html distanceFactor={10}>
                    <div style={{
                        background: 'rgba(0,0,0,0.8)',
                        color: 'white',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        fontSize: '12px',
                        whiteSpace: 'nowrap',
                        border: `1px solid ${source.color}`,
                    }}>
                        <div style={{ fontWeight: 'bold' }}>{source.icon} {source.name}</div>
                        <div>Quality: {(source.quality * 100).toFixed(0)}%</div>
                        <div>{source.available ? '✓ Available' : '✗ Offline'}</div>
                    </div>
                </Html>
            )}
            {/* Aura ring */}
            <mesh rotation={[Math.PI / 2, 0, 0]}>
                <ringGeometry args={[0.06, 0.08, 32]} />
                <meshBasicMaterial
                    color={source.color}
                    transparent
                    opacity={source.quality * 0.5}
                    side={THREE.DoubleSide}
                />
            </mesh>
        </group>
    );
}

// Main rotating globe
function RotatingGlobe({
    sources,
    onSourceClick,
    autoRotate = true
}: {
    sources: EntropySource[];
    onSourceClick?: (source: EntropySource) => void;
    autoRotate?: boolean;
}) {
    const groupRef = useRef<THREE.Group>(null);
    const globeRef = useRef<THREE.Mesh>(null);

    useFrame(() => {
        if (autoRotate && groupRef.current) {
            groupRef.current.rotation.y += 0.002;
        }
    });

    // Earth texture colors
    const earthMaterial = useMemo(() => {
        return new THREE.MeshPhongMaterial({
            color: '#1a365d',
            emissive: '#0d1f3c',
            emissiveIntensity: 0.3,
            transparent: true,
            opacity: 0.9,
        });
    }, []);

    return (
        <group ref={groupRef}>
            {/* Earth sphere */}
            <mesh ref={globeRef} material={earthMaterial}>
                <sphereGeometry args={[1, 64, 64]} />
            </mesh>

            {/* Atmosphere glow */}
            <mesh scale={1.02}>
                <sphereGeometry args={[1, 32, 32]} />
                <meshBasicMaterial
                    color="#60a5fa"
                    transparent
                    opacity={0.1}
                    side={THREE.BackSide}
                />
            </mesh>

            {/* Grid lines (latitude/longitude) */}
            <mesh>
                <sphereGeometry args={[1.01, 32, 32]} />
                <meshBasicMaterial
                    color="#3b82f6"
                    wireframe
                    transparent
                    opacity={0.15}
                />
            </mesh>

            {/* Source markers */}
            {sources.map((source) => (
                <SourceMarker
                    key={source.id}
                    source={source}
                    radius={1}
                    onClick={() => onSourceClick?.(source)}
                />
            ))}
        </group>
    );
}

// Particle stream flowing into mixer
function EntropyParticleStream({ sources }: { sources: EntropySource[] }) {
    const particlesRef = useRef<THREE.Points>(null);

    // Use useMemo so particles update when sources change
    const particles = useMemo<EntropyParticle[]>(() => {
        const p: EntropyParticle[] = [];
        sources.forEach(source => {
            if (source.available) {
                for (let i = 0; i < 20; i++) {
                    p.push({
                        position: [
                            (Math.random() - 0.5) * 3,
                            (Math.random() - 0.5) * 3,
                            (Math.random() - 0.5) * 3,
                        ],
                        velocity: [
                            (Math.random() - 0.5) * 0.02,
                            (Math.random() - 0.5) * 0.02,
                            (Math.random() - 0.5) * 0.02,
                        ],
                        color: source.color,
                        source: source.id,
                        age: Math.random() * 100,
                    });
                }
            }
        });
        return p;
    }, [sources]);

    const positions = useMemo(() => {
        const pos = new Float32Array(particles.length * 3);
        particles.forEach((p, i) => {
            pos[i * 3] = p.position[0];
            pos[i * 3 + 1] = p.position[1];
            pos[i * 3 + 2] = p.position[2];
        });
        return pos;
    }, [particles]);

    const colors = useMemo(() => {
        const cols = new Float32Array(particles.length * 3);
        particles.forEach((p, i) => {
            const color = new THREE.Color(p.color);
            cols[i * 3] = color.r;
            cols[i * 3 + 1] = color.g;
            cols[i * 3 + 2] = color.b;
        });
        return cols;
    }, [particles]);

    useFrame(() => {
        if (particlesRef.current) {
            const posAttr = particlesRef.current.geometry.attributes.position;
            for (let i = 0; i < particles.length; i++) {
                const p = particles[i];

                // Move toward center (mixer)
                const toCenter = [
                    -p.position[0] * 0.01,
                    -p.position[1] * 0.01,
                    -p.position[2] * 0.01,
                ];

                p.position[0] += p.velocity[0] + toCenter[0];
                p.position[1] += p.velocity[1] + toCenter[1];
                p.position[2] += p.velocity[2] + toCenter[2];

                // Reset if too close to center
                const dist = Math.sqrt(
                    p.position[0] ** 2 + p.position[1] ** 2 + p.position[2] ** 2
                );
                if (dist < 0.3) {
                    p.position = [
                        (Math.random() - 0.5) * 3,
                        (Math.random() - 0.5) * 3,
                        (Math.random() - 0.5) * 3,
                    ];
                }

                (posAttr.array as Float32Array)[i * 3] = p.position[0];
                (posAttr.array as Float32Array)[i * 3 + 1] = p.position[1];
                (posAttr.array as Float32Array)[i * 3 + 2] = p.position[2];
            }
            posAttr.needsUpdate = true;
        }
    });

    const geometry = useMemo(() => {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        return geo;
    }, [positions, colors]);

    return (
        <points ref={particlesRef} geometry={geometry}>
            <pointsMaterial
                size={0.05}
                vertexColors
                transparent
                opacity={0.8}
                sizeAttenuation
            />
        </points>
    );
}

// =============================================================================
// Exported Globe Component
// =============================================================================

export function EntropyGlobe({
    sources,
    onSourceClick,
    autoRotate = true,
    showParticles = true
}: EntropyGlobeProps) {
    return (
        <div style={{ width: '100%', height: '400px', borderRadius: '16px', overflow: 'hidden' }}>
            <Canvas camera={{ position: [0, 0, 3], fov: 50 }}>
                <ambientLight intensity={0.4} />
                <pointLight position={[10, 10, 10]} intensity={1} />
                <pointLight position={[-10, -10, -10]} intensity={0.5} color="#60a5fa" />

                <Stars radius={100} depth={50} count={1000} factor={4} saturation={0} fade={true} speed={1} />

                <RotatingGlobe
                    sources={sources}
                    onSourceClick={onSourceClick}
                    autoRotate={autoRotate}
                />

                {showParticles && <EntropyParticleStream sources={sources} />}

                <OrbitControls
                    enablePan={false}
                    enableZoom
                    minDistance={2}
                    maxDistance={5}
                    autoRotate={false}
                />
            </Canvas>
        </div>
    );
}

// =============================================================================
// Entropy Mixing Animation (2D Canvas)
// =============================================================================

interface MixingParticlesProps {
    sources: EntropySource[];
    isGenerating: boolean;
    onComplete?: () => void;
}

export function EntropyMixingParticles({ sources, isGenerating, onComplete: _onComplete }: MixingParticlesProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const animationRef = useRef<number>(0);

    // Note: onComplete callback can be used for future animation completion events
    void _onComplete;

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;

        // Create particles
        const particles: {
            x: number;
            y: number;
            vx: number;
            vy: number;
            color: string;
            size: number;
            phase: number;
        }[] = [];

        sources.filter(s => s.available).forEach(source => {
            for (let i = 0; i < 30; i++) {
                const angle = Math.random() * Math.PI * 2;
                const distance = 100 + Math.random() * 80;
                particles.push({
                    x: centerX + Math.cos(angle) * distance,
                    y: centerY + Math.sin(angle) * distance,
                    vx: 0,
                    vy: 0,
                    color: source.color,
                    size: 3 + Math.random() * 4,
                    phase: Math.random() * Math.PI * 2,
                });
            }
        });

        let frame = 0;

        const animate = () => {
            ctx.fillStyle = 'rgba(10, 10, 30, 0.1)';
            ctx.fillRect(0, 0, width, height);

            particles.forEach((p) => {
                // Calculate force toward center
                const dx = centerX - p.x;
                const dy = centerY - p.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (isGenerating && dist > 20) {
                    // Spiral inward when generating
                    const force = 0.05;
                    p.vx += (dx / dist) * force + (dy / dist) * 0.03;
                    p.vy += (dy / dist) * force - (dx / dist) * 0.03;
                } else if (!isGenerating) {
                    // Orbit around center when idle
                    const orbitSpeed = 0.02;
                    p.vx = (dy / dist) * orbitSpeed + (dx / dist) * 0.001;
                    p.vy = (-dx / dist) * orbitSpeed + (dy / dist) * 0.001;
                }

                // Apply velocity with damping
                p.x += p.vx;
                p.y += p.vy;
                p.vx *= 0.98;
                p.vy *= 0.98;

                // Draw particle
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                ctx.fillStyle = p.color;
                ctx.globalAlpha = 0.7;
                ctx.fill();

                // Draw glow
                const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 3);
                gradient.addColorStop(0, p.color);
                gradient.addColorStop(1, 'transparent');
                ctx.fillStyle = gradient;
                ctx.globalAlpha = 0.3;
                ctx.fill();
            });

            // Draw center mixer
            ctx.globalAlpha = 1;
            ctx.beginPath();
            ctx.arc(centerX, centerY, 30 + Math.sin(frame * 0.05) * 5, 0, Math.PI * 2);
            const mixerGradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, 40);
            mixerGradient.addColorStop(0, 'rgba(120, 200, 255, 0.8)');
            mixerGradient.addColorStop(0.5, 'rgba(80, 150, 220, 0.4)');
            mixerGradient.addColorStop(1, 'transparent');
            ctx.fillStyle = mixerGradient;
            ctx.fill();

            frame++;
            animationRef.current = requestAnimationFrame(animate);
        };

        animate();

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
        };
    }, [sources, isGenerating]);

    return (
        <canvas
            ref={canvasRef}
            width={400}
            height={400}
            style={{
                width: '100%',
                maxWidth: '400px',
                height: 'auto',
                borderRadius: '16px',
                background: 'linear-gradient(135deg, #0a0a1e 0%, #1a1a3e 100%)',
            }}
        />
    );
}

// =============================================================================
// Interactive Certificate Badge
// =============================================================================

interface CertificateBadgeProps {
    certificate: {
        certificate_id: string;
        sources_used: string[];
        quality_score: number;
        generation_timestamp: string;
        total_entropy_bits: number;
    };
    size?: 'small' | 'medium' | 'large';
}

export function InteractiveCertificateBadge({ certificate, size = 'medium' }: CertificateBadgeProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    const sourceIcons: Record<string, string> = {
        ocean: '🌊',
        lightning: '⚡',
        seismic: '🌍',
        solar: '☀️',
        quantum: '⚛️',
        genetic: '🧬',
    };

    const sizeConfig = {
        small: { width: 150, iconSize: 20, fontSize: 10 },
        medium: { width: 250, iconSize: 32, fontSize: 12 },
        large: { width: 350, iconSize: 48, fontSize: 14 },
    };

    const config = sizeConfig[size];

    return (
        <div
            onClick={() => setIsExpanded(!isExpanded)}
            style={{
                width: config.width,
                padding: '16px',
                borderRadius: '16px',
                background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
                border: '2px solid',
                borderImage: 'linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899) 1',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                transform: isExpanded ? 'scale(1.05)' : 'scale(1)',
            }}
        >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <span style={{ fontSize: config.iconSize }}>🏆</span>
                <div>
                    <div style={{
                        fontWeight: 'bold',
                        color: '#f8fafc',
                        fontSize: config.fontSize + 2,
                    }}>
                        Natural Entropy Certificate
                    </div>
                    <div style={{
                        fontSize: config.fontSize,
                        color: '#94a3b8',
                        fontFamily: 'monospace',
                    }}>
                        {certificate.certificate_id.slice(0, 8)}...
                    </div>
                </div>
            </div>

            {/* Source icons orbiting */}
            <div style={{
                display: 'flex',
                justifyContent: 'center',
                gap: '12px',
                margin: '16px 0',
            }}>
                {certificate.sources_used.map((source, index) => (
                    <span
                        key={source}
                        style={{
                            fontSize: config.iconSize,
                            animation: `bounce ${1 + index * 0.2}s ease-in-out infinite`,
                        }}
                    >
                        {sourceIcons[source] || '❓'}
                    </span>
                ))}
            </div>

            {/* Quality meter */}
            <div style={{ marginBottom: '12px' }}>
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: config.fontSize,
                    color: '#94a3b8',
                }}>
                    <span>Quality Score</span>
                    <span style={{ color: '#22c55e' }}>
                        {(certificate.quality_score * 100).toFixed(1)}%
                    </span>
                </div>
                <div style={{
                    height: '6px',
                    background: '#334155',
                    borderRadius: '3px',
                    overflow: 'hidden',
                }}>
                    <div style={{
                        width: `${certificate.quality_score * 100}%`,
                        height: '100%',
                        background: 'linear-gradient(90deg, #22c55e, #3b82f6)',
                        transition: 'width 0.5s ease',
                    }} />
                </div>
            </div>

            {/* Expanded details */}
            {isExpanded && (
                <div style={{
                    paddingTop: '12px',
                    borderTop: '1px solid #334155',
                    fontSize: config.fontSize,
                    color: '#94a3b8',
                }}>
                    <div>🔐 {certificate.total_entropy_bits} bits of entropy</div>
                    <div>📅 {new Date(certificate.generation_timestamp).toLocaleString()}</div>
                    <div>🔗 Sources: {certificate.sources_used.join(' + ')}</div>
                </div>
            )}

            <style>{`
        @keyframes bounce {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-4px); }
        }
      `}</style>
        </div>
    );
}

// =============================================================================
// Source Selection Card
// =============================================================================

interface SourceCardProps {
    source: EntropySource;
    selected: boolean;
    onToggle: () => void;
}

export function EntropySourceCard({ source, selected, onToggle }: SourceCardProps) {
    return (
        <div
            onClick={onToggle}
            style={{
                padding: '16px',
                borderRadius: '12px',
                background: selected
                    ? `linear-gradient(135deg, ${source.color}22 0%, ${source.color}11 100%)`
                    : 'rgba(30, 41, 59, 0.5)',
                border: `2px solid ${selected ? source.color : 'transparent'}`,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                opacity: source.available ? 1 : 0.5,
            }}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '32px' }}>{source.icon}</span>
                <div>
                    <div style={{ fontWeight: 'bold', color: '#f8fafc' }}>
                        {source.name}
                    </div>
                    <div style={{
                        fontSize: '12px',
                        color: source.available ? '#22c55e' : '#ef4444'
                    }}>
                        {source.available ? '● Available' : '○ Offline'}
                    </div>
                </div>
                <div
                    style={{
                        marginLeft: 'auto',
                        width: '24px',
                        height: '24px',
                        borderRadius: '6px',
                        background: selected ? source.color : '#334155',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        fontSize: '14px',
                    }}
                >
                    {selected && '✓'}
                </div>
            </div>
            {source.quality > 0 && (
                <div style={{ marginTop: '8px' }}>
                    <div style={{
                        height: '4px',
                        background: '#334155',
                        borderRadius: '2px',
                        overflow: 'hidden',
                    }}>
                        <div style={{
                            width: `${source.quality * 100}%`,
                            height: '100%',
                            background: source.color,
                        }} />
                    </div>
                </div>
            )}
        </div>
    );
}

export default {
    EntropyGlobe,
    EntropyMixingParticles,
    InteractiveCertificateBadge,
    EntropySourceCard,
};
