// Interactive 3D preview of a .vox (surface voxels only) with three.js.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { locale, t } from './i18n.js';

export async function mountViewer(el, url, view) {
  const r = await fetch(url);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);

  const [sx, sy, sz] = data.size;
  const bytes = Uint8Array.from(atob(data.voxels), (c) => c.charCodeAt(0));
  const raw = data.bits === 16 ? new Uint16Array(bytes.buffer) : bytes;   // uint16 coords for grids over 255
  const k = data.step || 1;                                                 // big models arrive k times coarser
  const n = raw.length / 4;
  const emissive = new Set(data.emissive);
  const pal = data.palette.map((h) => new THREE.Color(h));
  let ne = 0;
  for (let i = 0; i < n; i++) if (emissive.has(raw[i * 4 + 3])) ne++;

  // voxel (x, y, z) with z up and y=0 at the front -> three.js (x, z, -y), centred
  const geo = new THREE.BoxGeometry(k, k, k);
  const solid = new THREE.InstancedMesh(geo, new THREE.MeshLambertMaterial(), Math.max(n - ne, 1));
  const glow = new THREE.InstancedMesh(geo, new THREE.MeshBasicMaterial(), Math.max(ne, 1));
  solid.count = n - ne; glow.count = ne;
  const m4 = new THREE.Matrix4();
  let a = 0, b = 0;
  for (let i = 0; i < n; i++) {
    const x = raw[i * 4], y = raw[i * 4 + 1], z = raw[i * 4 + 2], c = raw[i * 4 + 3];
    m4.makeTranslation(x * k - sx / 2 + k / 2, z * k + k / 2, -(y * k - sy / 2 + k / 2));
    if (emissive.has(c)) { glow.setMatrixAt(b, m4); glow.setColorAt(b, pal[c]); b++; }
    else { solid.setMatrixAt(a, m4); solid.setColorAt(a, pal[c]); a++; }
  }

  const scene = new THREE.Scene();
  scene.add(solid, glow);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8c8072, 1.5));
  const sun = new THREE.DirectionalLight(0xffffff, 1.9);
  sun.position.set(-0.7 * sx, 1.6 * sz, 1.2 * sy);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xffffff, 0.45);
  fill.position.set(sx, 0.5 * sz, -sy);
  scene.add(fill);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  el.innerHTML = '';
  el.append(renderer.domElement);

  const camera = new THREE.PerspectiveCamera(32, 1, 0.5, Math.max(4000, Math.max(sx, sy, sz) * 6));
  const controls = new OrbitControls(camera, renderer.domElement);
  const target = new THREE.Vector3(0, sz * 0.4, 0);
  const dist = Math.max(sx, sy, sz) * 1.75;
  const place = (az, el2) => {
    const A = THREE.MathUtils.degToRad(az), E = THREE.MathUtils.degToRad(el2);
    // az 0 = looking at the front face, positive az swings toward the left side
    camera.position.set(target.x - Math.sin(A) * Math.cos(E) * dist, target.y + Math.sin(E) * dist,
      target.z + Math.cos(A) * Math.cos(E) * dist);
    controls.target.copy(target);
    controls.update();
    render();
  };
  const render = () => renderer.render(scene, camera);
  controls.addEventListener('change', render);

  const resize = () => {
    const w = el.clientWidth, h = el.clientHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    render();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(el);

  const ui = document.createElement('div');
  ui.innerHTML = `<div class="views">
      <button class="btn" data-v="${view?.azimuth ?? 36},${view?.elevation ?? 18}">${t('viewer.default')}</button>
      <button class="btn" data-v="0,8">${t('viewer.front')}</button><button class="btn" data-v="90,8">${t('viewer.left')}</button>
      <button class="btn" data-v="180,20">${t('viewer.back')}</button><button class="btn" data-v="0,89">${t('viewer.top')}</button></div>
    <div class="hint">${t('viewer.hint', { n: n.toLocaleString(locale()) })}${k > 1 ? ' · ' + t('viewer.coarse', { k }) : ''}</div>`;
  el.append(...ui.children);
  el.querySelectorAll('[data-v]').forEach((btn) => btn.addEventListener('click', () => place(...btn.dataset.v.split(',').map(Number))));

  resize();
  place(view?.azimuth ?? 36, view?.elevation ?? 18);

  return () => {
    ro.disconnect();
    controls.dispose();
    geo.dispose();
    solid.material.dispose(); glow.material.dispose();
    renderer.dispose();
  };
}
