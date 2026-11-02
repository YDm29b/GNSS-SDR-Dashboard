"""
views/three_globe_view.py
=========================
Renders the GPS Constellation 3D globe using Three.js inside st.components.v1.html.
Features:
  - 100% Client-side 60 FPS animation via requestAnimationFrame.
  - NASA Blue Marble textured Earth sphere with Greenwich sidereal angle (GAST) rotation.
  - Thin soft atmosphere glow.
  - 32 GPS satellite markers clustered and color-coded into 6 orbital planes (A-F).
  - 32 closed orbit rings in the inertial frame (GCRS) matching each satellite's path.
  - OrbitControls with damping; camera NEVER resets during playback, scrub, or speed change.
  - Constant screen size (11px) PRN labels with up-right offset, hidden on the far side of Earth,
    with overlap prevention (defaults to ON).
  - Satellite hover/click info card displaying PRN, NORAD ID, Plane, Altitude, and Sub-lat/lon.
  - Slim single-row control bar directly below the globe:
      Play/Pause, Reset (0h), Now, Speed (1x-60x), Scrubber,
      "Simulated: YYYY-MM-DD HH:MM UTC", and separate "T+HH:MM" elapsed chip.
  - Works fully offline: inlines local Three.js, OrbitControls, and base64 Earth texture.
"""

import os
import json
import base64
from typing import Dict


def load_static_assets():
    """
    Loads local Three.js, OrbitControls, and the NASA Blue Marble texture.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    static_dir = os.path.join(base_dir, "static")

    three_js_path = os.path.join(static_dir, "three.min.js")
    controls_js_path = os.path.join(static_dir, "OrbitControls.js")
    earth_img_path = os.path.join(static_dir, "earth_2k.jpg")

    with open(three_js_path, "r", encoding="utf-8") as f:
        three_js_code = f.read()

    with open(controls_js_path, "r", encoding="utf-8") as f:
        controls_js_code = f.read()

    with open(earth_img_path, "rb") as f:
        earth_b64 = base64.b64encode(f.read()).decode("ascii")

    earth_data_uri = f"data:image/jpeg;base64,{earth_b64}"
    return three_js_code, controls_js_code, earth_data_uri


def render_three_globe(sim_data: Dict) -> str:
    """
    Generates the self-contained HTML component containing the Three.js scene
    and the integrated slim simulation control bar.
    """
    three_js_code, controls_js_code, earth_texture_uri = load_static_assets()
    sim_data_json = json.dumps(sim_data)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NCGSA GNSS SDR 3D Constellation</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Orbitron:wght@600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        user-select: none;
    }}

    body, html {{
        width: 100%;
        height: 100%;
        overflow: hidden;
        background-color: #060913;
        font-family: 'Inter', -apple-system, sans-serif;
        color: #f8fafc;
    }}

    #container {{
        position: relative;
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
        background: #060913;
    }}

    #globe-viewport {{
        position: relative;
        width: 100%;
        flex: 1;
        min-height: 0;
        cursor: grab;
        overflow: hidden;
    }}
    #globe-viewport:active {{
        cursor: grabbing;
    }}

    /* Constant Screen Size (11px) PRN HTML Labels Overlay */
    #labels-overlay {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        overflow: hidden;
        z-index: 5;
    }}
    .prn-screen-label {{
        position: absolute;
        top: 0;
        left: 0;
        font-family: 'Space Grotesk', -apple-system, sans-serif;
        font-size: 11px;
        font-weight: 700;
        line-height: 1;
        letter-spacing: 0.04em;
        pointer-events: none;
        white-space: nowrap;
        text-shadow: 0 0 4px #000000, 0 1px 3px rgba(0, 0, 0, 0.95);
        will-change: transform;
        display: none;
    }}

    /* Satellite Info Floating Card */
    #info-card {{
        position: absolute;
        top: 16px;
        left: 16px;
        background: rgba(13, 20, 36, 0.88);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(56, 189, 248, 0.35);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), inset 0 0 15px rgba(56, 189, 248, 0.08);
        border-radius: 10px;
        padding: 12px 16px;
        font-size: 0.82rem;
        line-height: 1.45;
        z-index: 10;
        pointer-events: none;
        display: none;
        min-width: 200px;
    }}
    #info-card h4 {{
        font-family: 'Orbitron', monospace;
        font-size: 0.96rem;
        color: #38bdf8;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .info-row {{
        display: flex;
        justify-content: space-between;
        margin-bottom: 2px;
        color: #94a3b8;
    }}
    .info-val {{
        color: #f1f5f9;
        font-weight: 500;
        font-variant-numeric: tabular-nums;
    }}

    /* Orbital Planes Legend */
    #plane-legend {{
        position: absolute;
        top: 16px;
        right: 16px;
        background: rgba(13, 20, 36, 0.75);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 20px;
        padding: 6px 14px;
        display: flex;
        gap: 12px;
        align-items: center;
        font-size: 0.74rem;
        z-index: 10;
    }}
    .legend-item {{
        display: flex;
        align-items: center;
        gap: 5px;
        color: #94a3b8;
    }}
    .legend-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }}

    /* Slim Bottom Simulation Control Bar */
    #controls-bar {{
        height: 48px;
        background: rgba(13, 20, 36, 0.95);
        border-top: 1px solid rgba(56, 189, 248, 0.22);
        display: flex;
        align-items: center;
        padding: 0 12px;
        gap: 8px;
        z-index: 20;
        flex-shrink: 0;
        width: 100%;
    }}

    .ctrl-btn {{
        background: rgba(30, 41, 59, 0.85);
        border: 1px solid rgba(56, 189, 248, 0.25);
        color: #f8fafc;
        border-radius: 6px;
        padding: 5px 8px;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.78rem;
        font-weight: 600;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 3px;
        transition: all 0.15s ease;
        white-space: nowrap;
    }}
    .ctrl-btn:hover {{
        background: rgba(56, 189, 248, 0.25);
        border-color: #38bdf8;
        color: #38bdf8;
    }}
    .ctrl-btn:active {{
        transform: scale(0.96);
    }}

    /* Speed Selector Group */
    .speed-group {{
        display: flex;
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 6px;
        overflow: hidden;
    }}
    .speed-btn {{
        background: transparent;
        border: none;
        color: #94a3b8;
        padding: 4px 6px;
        font-size: 0.74rem;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.15s ease;
    }}
    .speed-btn:hover {{
        color: #38bdf8;
    }}
    .speed-btn.active {{
        background: #0284c7;
        color: #ffffff;
    }}

    /* Scrubber Slider */
    #time-slider-container {{
        flex: 1;
        display: flex;
        align-items: center;
        min-width: 70px;
    }}
    #time-slider {{
        -webkit-appearance: none;
        width: 100%;
        height: 6px;
        border-radius: 3px;
        background: #1e293b;
        outline: none;
        cursor: pointer;
        transition: background 0.2s;
    }}
    #time-slider::-webkit-slider-thumb {{
        -webkit-appearance: none;
        appearance: none;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #38bdf8;
        box-shadow: 0 0 8px #38bdf8;
        cursor: pointer;
        transition: transform 0.1s ease;
    }}
    #time-slider::-webkit-slider-thumb:hover {{
        transform: scale(1.3);
    }}
    #time-slider::-moz-range-thumb {{
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #38bdf8;
        box-shadow: 0 0 8px #38bdf8;
        cursor: pointer;
        border: none;
    }}

    /* Time Badges */
    .time-badge {{
        font-family: 'Orbitron', monospace;
        font-size: 0.76rem;
        color: #38bdf8;
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(56, 189, 248, 0.25);
        padding: 4px 8px;
        border-radius: 6px;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }}
    .elapsed-chip {{
        font-family: 'Orbitron', monospace;
        font-size: 0.76rem;
        font-weight: 700;
        color: #00ff88;
        background: rgba(0, 255, 136, 0.08);
        border: 1px solid rgba(0, 255, 136, 0.35);
    }}
    .speed-badge {{
        font-size: 0.72rem;
        color: #94a3b8;
        white-space: nowrap;
    }}

    /* Multan Visibility Panel — glass-morphism, bottom-right of globe */
    #vis-panel {{
        position: absolute;
        bottom: 12px;
        right: 14px;
        background: rgba(10, 16, 30, 0.82);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(255, 0, 204, 0.35);
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.55), inset 0 0 10px rgba(255, 0, 204, 0.06);
        border-radius: 10px;
        padding: 9px 13px 10px;
        min-width: 185px;
        max-width: 220px;
        max-height: 230px;
        overflow-y: auto;
        z-index: 11;
        pointer-events: none;
    }}
    #vis-panel-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.74rem;
        font-weight: 700;
        color: #ff00cc;
        letter-spacing: 0.04em;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 5px;
    }}
    #vis-count {{
        font-family: 'Orbitron', monospace;
        font-size: 0.88rem;
        color: #ffffff;
    }}
    #vis-list {{
        font-family: 'Space Grotesk', monospace;
        font-size: 0.72rem;
        line-height: 1.55;
    }}
    .vis-row {{
        display: flex;
        justify-content: space-between;
        gap: 8px;
        color: #e2e8f0;
        padding: 1px 0;
    }}
    .vis-prn {{
        color: #ffffff;
        font-weight: 700;
        min-width: 50px;
    }}
    .vis-el {{
        color: #00ff88;
        font-variant-numeric: tabular-nums;
    }}
    .vis-az {{
        color: #94a3b8;
        font-variant-numeric: tabular-nums;
    }}
    /* Multan label overlay */
    #multan-label {{
        position: absolute;
        pointer-events: none;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 11px;
        font-weight: 700;
        color: #ff00cc;
        text-shadow: 0 0 5px #000, 0 0 8px rgba(255,0,204,0.55);
        white-space: nowrap;
        display: none;
        z-index: 6;
    }}
</style>
<script>
{three_js_code}
</script>
<script>
{controls_js_code}
</script>
</head>
<body>
<div id="container">
    <div id="globe-viewport">
        <!-- HTML Constant Screen Size (11px) Labels Overlay -->
        <div id="labels-overlay"></div>

        <!-- Floating Hover / Click Info Card -->
        <div id="info-card">
            <h4 id="card-title">PRN 01</h4>
            <div class="info-row"><span>NORAD ID:</span><span id="card-norad" class="info-val">---</span></div>
            <div class="info-row"><span>Plane:</span><span id="card-plane" class="info-val">---</span></div>
            <div class="info-row"><span>Altitude:</span><span id="card-alt" class="info-val">--- km</span></div>
            <div class="info-row"><span>Sub-Lat:</span><span id="card-lat" class="info-val">---°</span></div>
            <div class="info-row"><span>Sub-Lon:</span><span id="card-lon" class="info-val">---°</span></div>
        </div>

        <!-- Orbital Planes Legend -->
        <div id="plane-legend">
            <div class="legend-item"><div class="legend-dot" style="background: #38bdf8;"></div>A</div>
            <div class="legend-item"><div class="legend-dot" style="background: #a855f7;"></div>B</div>
            <div class="legend-item"><div class="legend-dot" style="background: #00ff88;"></div>C</div>
            <div class="legend-item"><div class="legend-dot" style="background: #f59e0b;"></div>D</div>
            <div class="legend-item"><div class="legend-dot" style="background: #ec4899;"></div>E</div>
            <div class="legend-item"><div class="legend-dot" style="background: #818cf8;"></div>F</div>
        </div>

        <!-- Multan Observer Visibility Panel (bottom-right of globe) -->
        <div id="vis-panel">
            <div id="vis-panel-title">📍 Visible from Multan: <span id="vis-count">--</span></div>
            <div id="vis-list"></div>
        </div>

        <!-- Multan HTML label (positioned per-frame like PRN labels) -->
        <div id="multan-label">Multan</div>
    </div>

    <!-- Slim Simulation Controls Bar -->
    <div id="controls-bar">
        <button id="btn-play" class="ctrl-btn" title="Play / Pause">▶ Play</button>
        <button id="btn-reset" class="ctrl-btn" title="Reset to 0h">⏮ 0h</button>
        <button id="btn-now" class="ctrl-btn" title="Current Time">⏱ Now</button>

        <div class="speed-group">
            <button class="speed-btn" data-speed="1">1x</button>
            <button class="speed-btn active" data-speed="5">5x</button>
            <button class="speed-btn" data-speed="15">15x</button>
            <button class="speed-btn" data-speed="30">30x</button>
            <button class="speed-btn" data-speed="60">60x</button>
        </div>

        <div id="time-slider-container">
            <input type="range" id="time-slider" min="0" max="720" step="0.1" value="0">
        </div>

        <!-- Separate Simulated UTC Time and Elapsed Chip (Item 3) -->
        <div id="sim-utc-display" class="time-badge">Simulated: 00:00 UTC</div>
        <div id="sim-elapsed-display" class="time-badge elapsed-chip">T+00:00</div>
        <div id="speed-display" class="speed-badge">Speed: 5 min/s</div>
        <button id="btn-labels" class="ctrl-btn" style="padding: 5px 8px;">🏷️ Labels: ON</button>
    </div>
</div>

<script>
// --- INGEST SIMULATION DATA ---
const simData = {sim_data_json};
const numSteps = simData.num_steps;
const maxSimMinutes = 720.0;
const earthRadius = simData.earth_radius_three; // ~6.3781 units (thousands of km)

// --- THREE.JS SCENE SETUP ---
const viewport = document.getElementById('globe-viewport');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x060913);

const camera = new THREE.PerspectiveCamera(40, viewport.clientWidth / viewport.clientHeight, 0.5, 500);
camera.position.set(0, 22, 62);

const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false, powerPreference: 'high-performance' }});
renderer.setSize(viewport.clientWidth, viewport.clientHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
viewport.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.minDistance = 9.0;
controls.maxDistance = 150.0;
controls.target.set(0, 0, 0);

// --- LIGHTING ---
const ambientLight = new THREE.AmbientLight(0xdbeafe, 0.45);
scene.add(ambientLight);

// Sun directional light in GCRS
const sunLight = new THREE.DirectionalLight(0xffffff, 0.95);
sunLight.position.set(45, 15, 30);
scene.add(sunLight);

// --- DEEP SPACE STARFIELD ---
const starCount = 1800;
const starGeometry = new THREE.BufferGeometry();
const starPositions = new Float32Array(starCount * 3);
for (let i = 0; i < starCount; i++) {{
    const theta = 2 * Math.PI * Math.random();
    const phi = Math.acos(2 * Math.random() - 1);
    const r = 280.0 + Math.random() * 40.0;
    starPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    starPositions[i * 3 + 1] = r * Math.cos(phi);
    starPositions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
}}
starGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
const starMaterial = new THREE.PointsMaterial({{ color: 0x94a3b8, size: 0.85, transparent: true, opacity: 0.65 }});
const starField = new THREE.Points(starGeometry, starMaterial);
scene.add(starField);

// --- EARTH TEXTURED SPHERE ---
const textureLoader = new THREE.TextureLoader();
const earthTexture = textureLoader.load('{earth_texture_uri}');
const earthGeometry = new THREE.SphereGeometry(earthRadius, 64, 64);
const earthMaterial = new THREE.MeshPhongMaterial({{
    map: earthTexture,
    specular: new THREE.Color(0x1e293b),
    shininess: 12,
}});
const earthMesh = new THREE.Mesh(earthGeometry, earthMaterial);
scene.add(earthMesh);

// --- THIN SOFT ATMOSPHERE GLOW ---
const atmoGeometry = new THREE.SphereGeometry(earthRadius * 1.018, 64, 64);
const atmoMaterial = new THREE.ShaderMaterial({{
    vertexShader: `
        varying vec3 vNormal;
        void main() {{
            vNormal = normalize(normalMatrix * normal);
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }}
    `,
    fragmentShader: `
        varying vec3 vNormal;
        void main() {{
            float intensity = pow(0.60 - dot(vNormal, vec3(0, 0, 1.0)), 2.2);
            gl_FragColor = vec4(0.22, 0.74, 0.97, 1.0) * intensity * 0.75;
        }}
    `,
    blending: THREE.AdditiveBlending,
    side: THREE.BackSide,
    transparent: true,
    depthWrite: false
}});
const atmoMesh = new THREE.Mesh(atmoGeometry, atmoMaterial);
scene.add(atmoMesh);

// --- SATELLITES, ORBIT RINGS & CONSTANT SCREEN SIZE LABELS ---
const satMeshes = [];
const ringLines = [];
const labelOverlay = document.getElementById('labels-overlay');
const labelElements = [];
let showLabels = true; // Default ON because far-side suppression and collision detection prevent overlap

simData.satellites.forEach((sat, idx) => {{
    const colorHex = sat.color;
    const color = new THREE.Color(colorHex);

    // 1. Closed Orbit Ring
    const ringPts = sat.ring_points;
    const ringPositions = new Float32Array(ringPts.length * 3);
    for (let i = 0; i < ringPts.length; i++) {{
        ringPositions[i * 3] = ringPts[i][0];
        ringPositions[i * 3 + 1] = ringPts[i][1];
        ringPositions[i * 3 + 2] = ringPts[i][2];
    }}
    const ringGeo = new THREE.BufferGeometry();
    ringGeo.setAttribute('position', new THREE.BufferAttribute(ringPositions, 3));
    const ringMat = new THREE.LineBasicMaterial({{
        color: color,
        transparent: true,
        opacity: 0.32,
        linewidth: 1
    }});
    const ringLine = new THREE.LineLoop(ringGeo, ringMat);
    scene.add(ringLine);
    ringLines.push(ringLine);

    // 2. Satellite Mesh (Glowing Sphere)
    const satGeo = new THREE.SphereGeometry(0.32, 16, 16);
    const satMat = new THREE.MeshStandardMaterial({{
        color: color,
        emissive: color,
        emissiveIntensity: 0.85,
        roughness: 0.3,
        metalness: 0.2
    }});
    const satMesh = new THREE.Mesh(satGeo, satMat);
    satMesh.userData = {{
        satIdx: idx,
        prn: sat.prn,
        display_name: sat.display_name,
        norad_id: sat.norad_id,
        plane_name: sat.plane_name,
        colorHex: colorHex
    }};

    // Invisible hit-test sphere for easy hover & click
    const hitGeo = new THREE.SphereGeometry(1.2, 8, 8);
    const hitMat = new THREE.MeshBasicMaterial({{ visible: false }});
    const hitMesh = new THREE.Mesh(hitGeo, hitMat);
    hitMesh.userData = satMesh.userData;
    satMesh.add(hitMesh);

    scene.add(satMesh);
    satMeshes.push(satMesh);

    // 3. Constant Screen Size (11px) PRN HTML Label
    const lbl = document.createElement('div');
    lbl.className = 'prn-screen-label';
    lbl.textContent = `PRN ${{String(sat.prn).padStart(2, '0')}}`;
    lbl.style.color = colorHex;
    labelOverlay.appendChild(lbl);
    labelElements.push(lbl);
}});

// --- SIMULATION TIME & PLAYBACK STATE ---
let isPlaying = true;
let simMinutes = 0.0;
let playbackSpeed = 5.0; // Default: 5 sim-minutes per real second
let lastTimeMs = performance.now();
let isUserDragging = false;

// DOM Controls
const btnPlay = document.getElementById('btn-play');
const btnReset = document.getElementById('btn-reset');
const btnNow = document.getElementById('btn-now');
const timeSlider = document.getElementById('time-slider');
const simUtcDisplay = document.getElementById('sim-utc-display');
const simElapsedDisplay = document.getElementById('sim-elapsed-display');
const speedDisplay = document.getElementById('speed-display');
const btnLabels = document.getElementById('btn-labels');
const speedButtons = document.querySelectorAll('.speed-btn');

const infoCard = document.getElementById('info-card');
const cardTitle = document.getElementById('card-title');
const cardNorad = document.getElementById('card-norad');
const cardPlane = document.getElementById('card-plane');
const cardAlt = document.getElementById('card-alt');
const cardLat = document.getElementById('card-lat');
const cardLon = document.getElementById('card-lon');

// Update state function
function updateSimulationState(minutes) {{
    const stepIdx = Math.floor(minutes);
    const frac = minutes - stepIdx;
    const nextIdx = Math.min(stepIdx + 1, numSteps - 1);

    // 1. Rotate Earth by Greenwich Apparent Sidereal Time (GAST)
    const gast0 = simData.gast_rad[stepIdx];
    const gast1 = simData.gast_rad[nextIdx];
    const gast = (1.0 - frac) * gast0 + frac * gast1;
    earthMesh.rotation.y = gast;

    // 2. Interpolate Satellite Positions
    for (let i = 0; i < simData.satellites.length; i++) {{
        const posArr = simData.satellites[i].positions;
        const p0 = posArr[stepIdx];
        const p1 = posArr[nextIdx];

        const x = (1.0 - frac) * p0[0] + frac * p1[0];
        const y = (1.0 - frac) * p0[1] + frac * p1[1];
        const z = (1.0 - frac) * p0[2] + frac * p1[2];

        satMeshes[i].position.set(x, y, z);
    }}

    // 3. Update Text and Slider (Item 3: Separate Simulated and T+ chips)
    const utcStr = simData.utc_labels[stepIdx];
    const simStr = simData.sim_labels[stepIdx]; // e.g. "+00:17"
    simUtcDisplay.textContent = `Simulated: ${{utcStr}}`;
    simElapsedDisplay.textContent = `T${{simStr}}`;

    if (!isUserDragging) {{
        timeSlider.value = minutes.toFixed(1);
    }}

    // 4. Update Info Card if currently showing
    if (activeSatIdx !== null) {{
        updateInfoCardData(activeSatIdx, stepIdx, frac, nextIdx);
    }}
}}

let activeSatIdx = null;

function updateInfoCardData(satIdx, stepIdx, frac, nextIdx) {{
    const sat = simData.satellites[satIdx];
    const sub0 = sat.subpoints[stepIdx];
    const sub1 = sat.subpoints[nextIdx];

    const lat = ((1.0 - frac) * sub0[0] + frac * sub1[0]).toFixed(2);
    const lon = ((1.0 - frac) * sub0[1] + frac * sub1[1]).toFixed(2);
    const alt = Math.round((1.0 - frac) * sub0[2] + frac * sub1[2]);

    cardTitle.textContent = `${{sat.display_name}} (NORAD ${{sat.norad_id}})`;
    cardTitle.style.color = sat.color;
    cardNorad.textContent = sat.norad_id;
    cardPlane.textContent = sat.plane_name;
    cardAlt.textContent = `${{alt.toLocaleString()}} km`;
    cardLat.textContent = `${{lat}}°`;
    cardLon.textContent = `${{lon}}°`;
}}

// --- RAYCASTER FOR HOVER / CLICK ---
const raycaster = new THREE.Raycaster();
raycaster.params.Points.threshold = 1.0;
const mouse = new THREE.Vector2();

viewport.addEventListener('pointermove', (event) => {{
    const rect = viewport.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(satMeshes, true);

    if (intersects.length > 0) {{
        const hit = intersects[0].object.userData.satIdx !== undefined ? intersects[0].object : (intersects[0].object.parent || intersects[0].object);
        activeSatIdx = hit.userData.satIdx;
        infoCard.style.display = 'block';
        const stepIdx = Math.floor(simMinutes);
        const frac = simMinutes - stepIdx;
        const nextIdx = Math.min(stepIdx + 1, numSteps - 1);
        updateInfoCardData(activeSatIdx, stepIdx, frac, nextIdx);
    }} else if (pinnedSatIdx === null) {{
        infoCard.style.display = 'none';
        activeSatIdx = null;
    }}
}});

let pinnedSatIdx = null;
viewport.addEventListener('click', (event) => {{
    const rect = viewport.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(satMeshes, true);

    if (intersects.length > 0) {{
        const hit = intersects[0].object.userData.satIdx !== undefined ? intersects[0].object : (intersects[0].object.parent || intersects[0].object);
        pinnedSatIdx = hit.userData.satIdx;
        activeSatIdx = pinnedSatIdx;
        infoCard.style.display = 'block';
    }} else {{
        pinnedSatIdx = null;
        infoCard.style.display = 'none';
        activeSatIdx = null;
    }}
}});

// --- CONTROL EVENT LISTENERS ---
btnPlay.addEventListener('click', () => {{
    isPlaying = !isPlaying;
    btnPlay.textContent = isPlaying ? '⏸ Pause' : '▶ Play';
    lastTimeMs = performance.now();
}});

btnReset.addEventListener('click', () => {{
    simMinutes = 0.0;
    updateSimulationState(simMinutes);
}});

btnNow.addEventListener('click', () => {{
    simMinutes = 0.0;
    updateSimulationState(simMinutes);
}});

speedButtons.forEach(btn => {{
    btn.addEventListener('click', () => {{
        speedButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        playbackSpeed = parseFloat(btn.dataset.speed);
        speedDisplay.textContent = `Speed: ${{playbackSpeed}} min/s`;
    }});
}});

timeSlider.addEventListener('mousedown', () => {{ isUserDragging = true; }});
timeSlider.addEventListener('touchstart', () => {{ isUserDragging = true; }});
timeSlider.addEventListener('input', () => {{
    simMinutes = parseFloat(timeSlider.value);
    updateSimulationState(simMinutes);
}});
timeSlider.addEventListener('mouseup', () => {{ isUserDragging = false; }});
timeSlider.addEventListener('touchend', () => {{ isUserDragging = false; }});

btnLabels.addEventListener('click', () => {{
    showLabels = !showLabels;
    btnLabels.textContent = showLabels ? '🏷️ Labels: ON' : '🏷️ Labels: OFF';
}});

// --- WINDOW RESIZE ---
window.addEventListener('resize', () => {{
    camera.aspect = viewport.clientWidth / viewport.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(viewport.clientWidth, viewport.clientHeight);
}});

// Temporary vector for projection to avoid per-frame allocation
const projVec = new THREE.Vector3();

// --- 60 FPS ANIMATION LOOP ---
function animate(currentTimeMs) {{
    requestAnimationFrame(animate);

    const deltaSec = (currentTimeMs - lastTimeMs) / 1000.0;
    lastTimeMs = currentTimeMs;

    if (isPlaying && deltaSec > 0 && deltaSec < 0.25) {{
        simMinutes = (simMinutes + playbackSpeed * deltaSec) % maxSimMinutes;
        updateSimulationState(simMinutes);
    }}

    // Smooth OrbitControls damping
    controls.update();

    // Constant screen size (11px) PRN HTML labels with far-side suppression and collision check (Item 2)
    if (showLabels) {{
        const camPos = camera.position;
        const canvasW = viewport.clientWidth;
        const canvasH = viewport.clientHeight;
        const placedBoxes = [];

        for (let i = 0; i < satMeshes.length; i++) {{
            const satPos = satMeshes[i].position;
            const labelEl = labelElements[i];

            // 1. Far side of Earth suppression:
            // Earth is at (0, 0, 0). Vector from Earth to camera is camPos.
            // Vector from Earth to satellite is satPos.
            // If dot <= 0, satellite is on the far hemisphere facing away from camera.
            const dot = satPos.x * camPos.x + satPos.y * camPos.y + satPos.z * camPos.z;
            if (dot <= 0) {{
                labelEl.style.display = 'none';
                continue;
            }}

            // 2. Project 3D satellite position to 2D screen coordinates
            projVec.copy(satPos);
            projVec.project(camera);

            if (projVec.z > 1.0) {{
                labelEl.style.display = 'none';
                continue;
            }}

            const sx = (projVec.x * 0.5 + 0.5) * canvasW;
            const sy = (-projVec.y * 0.5 + 0.5) * canvasH;

            // Offset: 7px right, 14px up
            const lx = Math.round(sx + 7);
            const ly = Math.round(sy - 14);

            // Bounding box for overlap detection (~42px width, ~14px height)
            const box = {{
                left: lx,
                top: ly,
                right: lx + 44,
                bottom: ly + 14
            }};

            // 3. Prevent label collision / overlap
            let overlaps = false;
            for (let j = 0; j < placedBoxes.length; j++) {{
                const b = placedBoxes[j];
                if (box.left < b.right && box.right > b.left &&
                    box.top < b.bottom && box.bottom > b.top) {{
                    overlaps = true;
                    break;
                }}
            }}

            if (overlaps) {{
                labelEl.style.display = 'none';
            }} else {{
                labelEl.style.display = 'block';
                labelEl.style.transform = `translate3d(${{lx}}px, ${{ly}}px, 0)`;
                placedBoxes.push(box);
            }}
        }}
    }} else {{
        for (let i = 0; i < labelElements.length; i++) {{
            labelElements[i].style.display = 'none';
        }}
    }}

    renderer.render(scene, camera);
}}

// Initialize first frame and start loop
btnPlay.textContent = isPlaying ? '⏸ Pause' : '▶ Play';
updateSimulationState(simMinutes);
requestAnimationFrame((t) => {{
    lastTimeMs = t;
    animate(t);
}});
</script>
</body>
</html>"""

    return html_template
