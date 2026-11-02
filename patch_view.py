"""
patch_view.py — temporary patch script; delete after use.
Adds Focus Multan button, Multan 3D pin, halo meshes, LOS lines,
visibility logic, and panel update to three_globe_view.py.
"""
import sys, os, re

VIEW_PATH = os.path.join(os.path.dirname(__file__), "views", "three_globe_view.py")

with open(VIEW_PATH, "r", encoding="utf-8") as f:
    src = f.read()

CHANGED = False

# ── 1. Add "📍 Multan" Focus button before the Labels button ──────────────────
OLD_BTN = '        <button id="btn-labels" class="ctrl-btn" style="padding: 5px 8px;">'
NEW_BTN = (
    '        <button id="btn-focus-multan" class="ctrl-btn" '
    'title="Fly camera toward Multan">\U0001f4cd Multan</button>\n'
    '        <button id="btn-labels" class="ctrl-btn" style="padding: 5px 8px;">'
)
if OLD_BTN in src:
    src = src.replace(OLD_BTN, NEW_BTN, 1)
    print("  [1] Added Focus-Multan button.")
    CHANGED = True
else:
    print("  [1] SKIP — btn-labels not found.")

# ── 2. After satellite loop (after satMeshes.push), add Multan pin + halos + LOS ─
OLD_AFTER_LOOP = "// --- SIMULATION TIME & PLAYBACK STATE ---"
NEW_BEFORE_STATE = r"""// --- MULTAN OBSERVER: 3D PIN, HALO MESHES & LOS LINES ---
const obsData   = simData.observer;  // {lat, lon, elevation_m, elevation_mask_deg}
const el_deg    = simData.el_deg;    // [num_sats][num_steps]
const az_deg    = simData.az_deg;    // [num_sats][num_steps]
const maskAngle = obsData.elevation_mask_deg;

// Multan body-frame position (ECEF-style, relative to Earth mesh BEFORE GAST rotation)
// Convention matches earthMesh local frame: x=cos(lat)*cos(lon), y=sin(lat), z=-cos(lat)*sin(lon)
const mLat = obsData.lat * Math.PI / 180;
const mLon = obsData.lon * Math.PI / 180;
const mR   = earthRadius * 1.006;   // just above surface

const multanBodyPos = new THREE.Vector3(
    mR * Math.cos(mLat) * Math.cos(mLon),
    mR * Math.sin(mLat),
   -mR * Math.cos(mLat) * Math.sin(mLon)
);

// Magenta glowing pin sphere, child of earthMesh (rotates with GAST automatically)
const multanGeo  = new THREE.SphereGeometry(0.14, 16, 16);
const multanMat  = new THREE.MeshStandardMaterial({
    color: 0xff00cc, emissive: 0xff00cc, emissiveIntensity: 1.4,
    roughness: 0.2, metalness: 0.1
});
const multanPin  = new THREE.Mesh(multanGeo, multanMat);
multanPin.position.copy(multanBodyPos);
earthMesh.add(multanPin);

// Glowing ring around the pin (outward-facing disk in the surface normal plane)
const multanRingGeo  = new THREE.RingGeometry(0.18, 0.32, 32);
const multanRingMat  = new THREE.MeshBasicMaterial({
    color: 0xff00cc, transparent: true, opacity: 0.55,
    side: THREE.DoubleSide, depthWrite: false
});
const multanRing = new THREE.Mesh(multanRingGeo, multanRingMat);
// Align ring to surface normal (outward from Earth center in body frame)
multanRing.position.copy(multanBodyPos);
multanRing.lookAt(new THREE.Vector3(0, 0, 0));  // face Earth centre → normal outward
earthMesh.add(multanRing);

// Per-satellite HALO (pre-built as child of satMesh, invisible until visible)
const haloMeshes = satMeshes.map((sm) => {
    const h = new THREE.Mesh(
        new THREE.SphereGeometry(0.52, 16, 16),
        new THREE.MeshBasicMaterial({
            color: new THREE.Color(sm.userData.colorHex),
            transparent: true, opacity: 0.22, side: THREE.BackSide, depthWrite: false
        })
    );
    h.visible = false;
    sm.add(h);
    return h;
});

// Per-satellite LINE-OF-SIGHT (pre-allocated geometry, one per satellite)
const losLines = simData.satellites.map((sat) => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
    const mat = new THREE.LineBasicMaterial({
        color: new THREE.Color(sat.color), transparent: true, opacity: 0.62
    });
    const line = new THREE.Line(geo, mat);
    line.visible = false;
    scene.add(line);
    return { line, geo };
});

// Reusable world-space vector for Multan pin (computed once per frame after earth rotation)
const multanWorldPos = new THREE.Vector3();

// Visibility panel DOM refs
const visCount = document.getElementById('vis-count');
const visList  = document.getElementById('vis-list');
const multanLabel = document.getElementById('multan-label');

// Frame counter for ~4 Hz panel updates (every 15 frames at 60 FPS)
let _frameCount = 0;

// Helper: interpolate azimuth with wrap-around
function lerpAz(a0, a1, t) {
    const diff = ((a1 - a0 + 540) % 360) - 180;
    return a0 + t * diff;
}

// Update the visibility panel DOM
function updateVisibilityPanel(visibleEntries) {
    visCount.textContent = visibleEntries.length;
    // Sort by elevation descending
    visibleEntries.sort((a, b) => b.el - a.el);
    let html = '';
    for (const e of visibleEntries) {
        const prnStr = 'PRN ' + String(e.prn).padStart(2, '0');
        const elStr  = e.el.toFixed(1) + '\u00b0';
        const azStr  = e.az.toFixed(0) + '\u00b0';
        html += '<div class="vis-row">'
              + '<span class="vis-prn">' + prnStr + '</span>'
              + '<span class="vis-el">El ' + elStr + '</span>'
              + '<span class="vis-az">Az ' + azStr + '</span>'
              + '</div>';
    }
    visList.innerHTML = html;
}

// Focus Multan camera animation state
let focusAnim = null;   // { startPos, endPos, t }
const _tmpFocus = new THREE.Vector3();

document.getElementById('btn-focus-multan').addEventListener('click', () => {
    multanPin.getWorldPosition(multanWorldPos);
    // Target camera position: along the direction of Multan from centre, at camera orbit distance
    const dist = camera.position.length();
    const endPos = multanWorldPos.clone().normalize().multiplyScalar(dist);
    focusAnim = { startPos: camera.position.clone(), endPos, t: 0 };
});

// --- SIMULATION TIME & PLAYBACK STATE ---"""

if OLD_AFTER_LOOP in src:
    src = src.replace(OLD_AFTER_LOOP, NEW_BEFORE_STATE, 1)
    print("  [2] Added Multan pin, halos, LOS, panel helpers, Focus animation.")
    CHANGED = True
else:
    print("  [2] SKIP — anchor not found.")

# ── 3. Update updateSimulationState() to handle per-satellite visibility ──────
# Insert after "satMeshes[i].position.set(x, y, z);" inside the sat loop
OLD_SAT_POS = "        satMeshes[i].position.set(x, y, z);\n    }\n\n    // 3."
NEW_SAT_POS = """        satMeshes[i].position.set(x, y, z);

        // Visibility: interpolate el/az (with azimuth wrap-around)
        const el0 = el_deg[i][stepIdx], el1 = el_deg[i][nextIdx];
        const az0 = az_deg[i][stepIdx], az1 = az_deg[i][nextIdx];
        const satEl = (1.0 - frac) * el0 + frac * el1;
        const satAz = lerpAz(az0, az1, frac);
        const isVis = satEl >= maskAngle;

        // Dim / bright styling
        const sm = satMeshes[i];
        sm.material.emissiveIntensity = isVis ? 1.2 : 0.25;
        sm.material.opacity           = isVis ? 1.0 : 0.35;
        sm.material.transparent       = true;
        sm.scale.setScalar(isVis ? 1.25 : 1.0);
        haloMeshes[i].visible = isVis;

        // LOS line (uses Multan world pos computed above)
        if (isVis) {
            const sp = sm.position;
            const pa = losLines[i].geo.attributes.position;
            pa.setXYZ(0, multanWorldPos.x, multanWorldPos.y, multanWorldPos.z);
            pa.setXYZ(1, sp.x, sp.y, sp.z);
            pa.needsUpdate = true;
            losLines[i].line.visible = true;
        } else {
            losLines[i].line.visible = false;
        }
    }

    // 3."""
if OLD_SAT_POS in src:
    src = src.replace(OLD_SAT_POS, NEW_SAT_POS, 1)
    print("  [3] Added visibility logic inside satellite update loop.")
    CHANGED = True
else:
    print("  [3] SKIP — satellite pos anchor not found.")

# ── 4. In the animate() loop, after controls.update(), add:
#       - compute multanWorldPos (once per frame)
#       - Multan label projection
#       - panel update (every 15 frames)
#       - Focus animation step
OLD_ANIM_CONTROLS = "    // Smooth OrbitControls damping\n    controls.update();"
NEW_ANIM_CONTROLS = """    // Smooth OrbitControls damping
    controls.update();

    // --- MULTAN WORLD POSITION (once per frame, after earthMesh has been rotated) ---
    multanPin.getWorldPosition(multanWorldPos);

    // --- MULTAN HTML LABEL (same projection as PRN labels) ---
    {
        const canvasW = viewport.clientWidth;
        const canvasH = viewport.clientHeight;
        projVec.copy(multanWorldPos);
        projVec.project(camera);
        const dot = multanWorldPos.dot(camera.position);
        if (dot > 0 && projVec.z <= 1.0) {
            const mx = Math.round((projVec.x * 0.5 + 0.5) * canvasW + 6);
            const my = Math.round((-projVec.y * 0.5 + 0.5) * canvasH - 12);
            multanLabel.style.transform = 'translate3d(' + mx + 'px,' + my + 'px,0)';
            multanLabel.style.display = 'block';
        } else {
            multanLabel.style.display = 'none';
        }
    }

    // --- PANEL UPDATE (~4 Hz = every 15 frames) ---
    _frameCount++;
    if (_frameCount % 15 === 0) {
        const si = Math.floor(simMinutes);
        const fr = simMinutes - si;
        const ni = Math.min(si + 1, numSteps - 1);
        const visEntries = [];
        for (let i = 0; i < simData.satellites.length; i++) {
            const el0 = el_deg[i][si], el1 = el_deg[i][ni];
            const az0 = az_deg[i][si], az1 = az_deg[i][ni];
            const elVal = (1.0 - fr) * el0 + fr * el1;
            const azVal = lerpAz(az0, az1, fr);
            if (elVal >= maskAngle) {
                visEntries.push({ prn: simData.satellites[i].prn, el: elVal, az: azVal });
            }
        }
        updateVisibilityPanel(visEntries);
    }

    // --- FOCUS MULTAN CAMERA ANIMATION ---
    if (focusAnim !== null) {
        focusAnim.t += 0.035;
        const tSmooth = focusAnim.t < 1 ? focusAnim.t * focusAnim.t * (3 - 2 * focusAnim.t) : 1;
        camera.position.lerpVectors(focusAnim.startPos, focusAnim.endPos, tSmooth);
        camera.lookAt(0, 0, 0);
        if (focusAnim.t >= 1) {
            // Sync OrbitControls after the lerp so subsequent dragging works normally
            controls.target.set(0, 0, 0);
            controls.update();
            focusAnim = null;
        }
    }"""
if OLD_ANIM_CONTROLS in src:
    src = src.replace(OLD_ANIM_CONTROLS, NEW_ANIM_CONTROLS, 1)
    print("  [4] Added animate() Multan world-pos, label, panel, focus anim.")
    CHANGED = True
else:
    print("  [4] SKIP — controls.update() anchor not found.")

# ── 5. Update labels loop: visible satellites skip overlap suppression, always shown ──
# Replace the overlap check block for visible sats
OLD_OVERLAP = "            if (overlaps) {\n                labelEl.style.display = 'none';\n            } else {\n                labelEl.style.display = 'block';\n                labelEl.style.transform = `translate3d(${lx}px, ${ly}px, 0)`;\n                placedBoxes.push(box);\n            }"
NEW_OVERLAP = """            // Visible satellites: always show label (skip overlap suppression)
            const satIsVisible = (typeof el_deg !== 'undefined')
                ? el_deg[i][Math.floor(simMinutes)] >= maskAngle
                : false;

            if (satIsVisible) {
                // Visible sat: always show, skip collision test
                labelEl.style.display = 'block';
                labelEl.style.transform = 'translate3d(' + lx + 'px, ' + ly + 'px, 0)';
                placedBoxes.push(box);
            } else if (overlaps) {
                labelEl.style.display = 'none';
            } else {
                labelEl.style.display = 'block';
                labelEl.style.transform = 'translate3d(' + lx + 'px, ' + ly + 'px, 0)';
                placedBoxes.push(box);
            }"""
if OLD_OVERLAP in src:
    src = src.replace(OLD_OVERLAP, NEW_OVERLAP, 1)
    print("  [5] Visible satellites always show their label.")
    CHANGED = True
else:
    print("  [5] SKIP — overlap block not found (may use backtick template literals).")

# Try backtick template literal version
OLD_OVERLAP_BT = "            if (overlaps) {{\n                labelEl.style.display = 'none';\n            }} else {{\n                labelEl.style.display = 'block';\n                labelEl.style.transform = `translate3d(${{lx}}px, ${{ly}}px, 0)`;\n                placedBoxes.push(box);\n            }}"
NEW_OVERLAP_BT = """            // Visible satellites: always show label (skip overlap suppression)
            const satIsVisible = (typeof el_deg !== 'undefined')
                ? el_deg[i][Math.floor(simMinutes)] >= maskAngle
                : false;

            if (satIsVisible) {{
                labelEl.style.display = 'block';
                labelEl.style.transform = `translate3d(${{lx}}px, ${{ly}}px, 0)`;
                placedBoxes.push(box);
            }} else if (overlaps) {{
                labelEl.style.display = 'none';
            }} else {{
                labelEl.style.display = 'block';
                labelEl.style.transform = `translate3d(${{lx}}px, ${{ly}}px, 0)`;
                placedBoxes.push(box);
            }}"""
if OLD_OVERLAP_BT in src:
    src = src.replace(OLD_OVERLAP_BT, NEW_OVERLAP_BT, 1)
    print("  [5b] Visible satellites always show their label (backtick variant).")
    CHANGED = True
else:
    print("  [5b] SKIP — backtick overlap block not found either.")

if CHANGED:
    with open(VIEW_PATH, "w", encoding="utf-8") as f:
        f.write(src)
    print("DONE: views/three_globe_view.py patched successfully.")
else:
    print("WARNING: No changes made.")
    sys.exit(1)
