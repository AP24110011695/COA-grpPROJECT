/* The Cache Machine — 3D scene and playback (V1 + dark theme).
 *
 * Consumes window.CACHE_PAYLOAD (built by ui/cache_scene.py from engine
 * output) and animates it. This script contains NO cache logic: hits,
 * misses, victims, tags, indices, and state come verbatim from the
 * engine's events and per-access snapshots.
 *
 * The payload's `theme` field ("light"/"dark") is presentation-only
 * metadata: it selects this scene's palette and overlay styling. It never
 * affects events, snapshots, or any simulation outcome.
 */
(function () {
  'use strict';

  var P = window.CACHE_PAYLOAD;
  var stage = document.getElementById('cm-stage');
  if (!P) {
    stage.innerHTML = '<div class="cm-note">Cache Machine: payload missing.</div>';
    return;
  }

  // presentation palette (theme-aware; no simulation meaning)
  var DARK = P.theme === "dark";
  document.body.classList.add(DARK ? "cm-dark" : "cm-light");
  var T = DARK ? {
    bg: 0x16181D, text: "#E8EAED", text2: "#A8B0BD",
    accent: 0x4F8DE8, accentSlot: 0x2E5F9E, accentSoft: 0x22304A,
    empty: 0x2A303B, hit: 0x66BB6A, miss: 0xEF5350, copy: 0xFFB74D,
    slab: 0x9DB8D4, plate: 0x2A303B, bus: 0x667080, cpu: 0x4F8DE8,
    hemiGround: 0x101216
  } : {
    bg: 0xf5f7fa, text: "#1F2933", text2: "#52606D",
    accent: 0x1F5FA8, accentSlot: 0x1F5FA8, accentSoft: 0xe8f0f8,
    empty: 0xdfe6ee, hit: 0x2E7D32, miss: 0xC62828, copy: 0xB26A00,
    slab: 0x9db8d4, plate: 0xdfe6ee, bus: 0xd9dee4, cpu: 0x1F5FA8,
    hemiGround: 0xd8e0ea
  };

  // ---------------------------------------------------------------- scene
  var scene = new THREE.Scene();
  scene.background = new THREE.Color(T.bg);

  var camera = new THREE.PerspectiveCamera(42, 1, 0.1, 800);
  var renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  stage.appendChild(renderer.domElement);

  scene.add(new THREE.HemisphereLight(0xffffff, T.hemiGround, 0.95));
  var sun = new THREE.DirectionalLight(0xffffff, 0.7);
  sun.position.set(6, 18, 10);
  scene.add(sun);

  var orbit = { az: -0.62, pol: 1.22, r: 36 };
  var target = new THREE.Vector3(-1, 3.2, 0);
  function updateCamera() {
    orbit.pol = Math.max(0.35, Math.min(1.45, orbit.pol));
    orbit.r = Math.max(12, Math.min(90, orbit.r));
    camera.position.set(
      target.x + orbit.r * Math.sin(orbit.pol) * Math.sin(orbit.az),
      target.y + orbit.r * Math.cos(orbit.pol),
      target.z + orbit.r * Math.sin(orbit.pol) * Math.cos(orbit.az));
    camera.lookAt(target);
  }

  function onResize() {
    var w = stage.clientWidth, h = stage.clientHeight;
    if (!w || !h) return;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
    renderer.render(scene, camera);
  }
  window.addEventListener('resize', onResize);

  // drag-orbit + wheel zoom (lightweight; no extra libraries)
  var dragging = false, lastX = 0, lastY = 0;
  renderer.domElement.addEventListener('mousedown', function (e) {
    dragging = true; lastX = e.clientX; lastY = e.clientY;
  });
  window.addEventListener('mouseup', function () { dragging = false; });
  window.addEventListener('mousemove', function (e) {
    if (!dragging) return;
    orbit.az -= (e.clientX - lastX) * 0.005;
    orbit.pol -= (e.clientY - lastY) * 0.005;
    lastX = e.clientX; lastY = e.clientY;
    updateCamera(); renderer.render(scene, camera);
  });
  renderer.domElement.addEventListener('wheel', function (e) {
    e.preventDefault();
    orbit.r += e.deltaY * 0.02;
    updateCamera(); renderer.render(scene, camera);
  }, { passive: false });

  // ------------------------------------------------------------- helpers
  function textCanvas(lines, options) {
    options = options || {};
    var font = (options.size || 30) + 'px "Consolas", monospace';
    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext('2d');
    ctx.font = font;
    var width = 1;
    lines.forEach(function (line) {
      width = Math.max(width, ctx.measureText(line).width);
    });
    var lineHeight = options.lineHeight || 38;
    canvas.width = Math.ceil(width + 24);
    canvas.height = lineHeight * lines.length + 16;
    ctx = canvas.getContext('2d');
    ctx.font = font;
    if (options.background) {
      ctx.fillStyle = options.background;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    ctx.fillStyle = options.color || '#1F2933';
    ctx.textBaseline = 'top';
    lines.forEach(function (line, i) {
      ctx.fillText(line, 12, 8 + i * lineHeight);
    });
    return canvas;
  }

  function textSprite(lines, options) {
    var canvas = textCanvas(lines, options);
    var sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(canvas), depthTest: false, transparent: true
    }));
    sprite.material.map.minFilter = THREE.LinearFilter;
    var scale = (options && options.scale || 0.02) * ((options && options.emphasis) || 1);
    sprite.scale.set(canvas.width * scale, canvas.height * scale, 1);
    return sprite;
  }

  function swapSprite(sprite, lines, options) {
    sprite.material.map.dispose();
    sprite.material = new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(textCanvas(lines, options)),
      depthTest: false, transparent: true });
    sprite.material.map.minFilter = THREE.LinearFilter;
  }

  function box(w, h, d, color, opacity) {
    return new THREE.Mesh(new THREE.BoxGeometry(w, h, d),
      new THREE.MeshLambertMaterial({
        color: color, transparent: (opacity !== undefined && opacity < 1),
        opacity: (opacity === undefined ? 1 : opacity)
      }));
  }

  // ------------------------------------------------------------ layout
  var G = P.geometry;
  var MEM_X = -16, CACHE_X = 12, BUS_Y = 2.6;

  [['Main Memory', MEM_X - 1, 11.5, 0],
   ['Address Bus', 0, 6.4, 0],
   ['CPU Cache', CACHE_X - 1, 11.5, 0]].forEach(function (t) {
    var s = textSprite([t[0]], { size: 44, color: T.text, scale: 0.017 });
    s.position.set(t[1], t[2], t[3]);
    scene.add(s);
  });

  var cpu = box(1.6, 1.0, 1.0, T.cpu);
  cpu.position.set(-10.5, BUS_Y, 0);
  scene.add(cpu);
  var cpuLabel = textSprite(['CPU'], { size: 34, color: '#FFFFFF', scale: 0.017 });
  cpuLabel.position.copy(cpu.position);
  scene.add(cpuLabel);

  var bus = box(17, 0.1, 0.6, T.bus);
  bus.position.set(0, BUS_Y, 0);
  scene.add(bus);

  // -------------------------------------------------------- memory wall
  // Slabs for the first WALL_MAX blocks referenced by the trace; blocks
  // beyond the cap still animate — the traveling copy carries its block
  // label and spawns from the wall's top edge.
  var WALL_COLS = 8, WALL_MAX = 128;
  var wallBlocks = P.memory.blocks.slice(0, WALL_MAX);
  var memoryTruncated = P.memory.truncated || (P.memory.blocks.length > WALL_MAX);
  var slabGeometry = new THREE.BoxGeometry(1.3, 0.8, 0.5);
  var slabMaterial = new THREE.MeshLambertMaterial({ color: T.slab });
  var wallPositions = {};
  wallBlocks.forEach(function (block, i) {
    var col = i % WALL_COLS, row = Math.floor(i / WALL_COLS);
    var mesh = new THREE.Mesh(slabGeometry, slabMaterial);
    mesh.position.set(MEM_X, 8.2 - row * 1.15, (col - (WALL_COLS - 1) / 2) * 1.7);
    scene.add(mesh);
    wallPositions[block] = mesh.position.clone();
    var label = textSprite(['blk ' + block], { size: 26, color: T.text2, scale: 0.013 });
    label.position.set(mesh.position.x, mesh.position.y + 0.75, mesh.position.z);
    scene.add(label);
  });
  var wallRows = Math.ceil(Math.min(wallBlocks.length, WALL_MAX) / WALL_COLS);
  if (memoryTruncated) {
    var wallNote = textSprite(
      ['memory wall shows the first ' + WALL_MAX + ' referenced blocks'],
      { size: 24, color: T.text2, scale: 0.014 });
    wallNote.position.set(MEM_X, 8.2 - wallRows * 1.15 - 0.9, 0);
    scene.add(wallNote);
  }
  function wallSource(block) {
    return wallPositions[block] ||
      new THREE.Vector3(MEM_X, 8.2 + 1.2, 0); // off-wall spawn for unlabeled blocks
  }

  // ---------------------------------------------------------- cache shelves
  var SETS = G.sets, WAYS = G.waysPerSet;
  var CACHE_COLS = Math.min(4, SETS);
  var slots = [];   // slots[s][w] = {mesh, label}
  (function buildShelves() {
    for (var s = 0; s < SETS; s++) {
      var col = s % CACHE_COLS, row = Math.floor(s / CACHE_COLS);
      var cx = CACHE_X + row * 2.6;
      var cz = (col - (CACHE_COLS - 1) / 2) * 2.9;
      var cy = 7.0 - row * 2.1;
      var plate = box(WAYS * 1.7 + 0.4, 0.12, 1.8, T.plate);
      plate.position.set(cx, cy - 0.55, cz);
      scene.add(plate);
      var shelfLabel = textSprite(['Set ' + s],
        { size: 28, color: T.text2, scale: 0.014 });
      shelfLabel.position.set(cx - (WAYS * 1.7) / 2 - 0.9, cy, cz);
      scene.add(shelfLabel);
      slots[s] = [];
      for (var w = 0; w < WAYS; w++) {
        var mesh = box(1.35, 0.85, 1.2, T.empty, 0.3);
        var wz = cz + (w - (WAYS - 1) / 2) * 1.7;
        mesh.position.set(cx, cy, wz);
        scene.add(mesh);
        var label = textSprite(['—'], { size: 26, color: T.text2, scale: 0.014 });
        label.position.set(cx, cy + 0.85, wz);
        scene.add(label);
        slots[s][w] = { mesh: mesh, label: label };
      }
    }
  })();

  // ------------------------------------------------------------- movers
  var copyMesh = box(1.35, 0.85, 1.2, T.copy);
  copyMesh.visible = false;
  var copyLabel = textSprite([''], { size: 28, color: '#FFFFFF', scale: 0.016 });
  copyLabel.visible = false;
  scene.add(copyMesh); scene.add(copyLabel);

  var ghostMesh = box(1.35, 0.85, 1.2, T.miss, 0.85);
  ghostMesh.visible = false;
  var ghostLabel = textSprite([''], { size: 28, color: '#FFFFFF', scale: 0.016 });
  ghostLabel.visible = false;
  scene.add(ghostMesh); scene.add(ghostLabel);

  var hitPacket = new THREE.Mesh(new THREE.SphereGeometry(0.26, 16, 12),
    new THREE.MeshLambertMaterial({ color: T.hit }));
  hitPacket.visible = false;
  scene.add(hitPacket);

  var addrSprite = textSprite([''], {
    size: 32, color: T.text, background: DARK ? 'rgba(31,35,43,0.95)' :
      'rgba(255,255,255,0.95)', scale: 0.017
  });
  addrSprite.visible = false;
  scene.add(addrSprite);

  // ------------------------------------------------------- scene state
  var N = P.events.length;
  var idx = 0;               // settled accesses; scene = snapshots[idx-1] (or empty)
  var playing = false, speed = 1, animating = false;

  function slotAt(set, way) {
    if (!slots[set] || !slots[set][way]) return null;
    return slots[set][way];
  }

  function applyLine(set, way, line) {
    var slot = slotAt(set, way);
    if (!slot) return;
    slot.mesh.scale.set(1, 1, 1);
    if (line && line.valid) {
      slot.mesh.material = new THREE.MeshLambertMaterial({ color: T.accentSlot });
      swapSprite(slot.label, ['tag ' + line.tag, 'blk ' + line.block],
        { size: 26, color: '#FFFFFF' });
    } else {
      slot.mesh.material = new THREE.MeshLambertMaterial({
        color: T.empty, transparent: true, opacity: 0.3 });
      swapSprite(slot.label, ['—'], { size: 26, color: T.text2 });
    }
  }

  function applySnapshot(k) { // k settled accesses; snapshots[k-1] authoritative
    var snap = k > 0 ? P.snapshots[k - 1].sets : null;
    for (var s = 0; s < SETS; s++) {
      for (var w = 0; w < WAYS; w++) {
        applyLine(s, w, snap ? snap[s][w] : null);
      }
    }
  }

  function counters(k) {
    var h = 0, m = 0, e = 0;
    for (var i = 0; i < k; i++) {
      var ev = P.events[i];
      if (ev.result === 'hit') h++; else m++;
      if (ev.evicted) e++;
    }
    return { h: h, m: m, e: e };
  }

  // ------------------------------------------------------------- overlay
  var infoEl = document.getElementById('cm-info');
  var countersEl = document.getElementById('cm-counters');
  var logEl = document.getElementById('cm-log');
  var progressEl = document.getElementById('cm-progress');
  var scrubEl = document.getElementById('cm-scrub');
  var playEl = document.getElementById('cm-play');
  var pauseEl = document.getElementById('cm-pause');
  var prevEl = document.getElementById('cm-prev');
  var nextEl = document.getElementById('cm-next');

  scrubEl.max = String(N);

  var logRows = [];
  P.events.forEach(function (ev) {
    var row = document.createElement('div');
    row.className = 'cm-row cm-' + ev.result;
    row.textContent = '#' + ev.n + ' addr ' + ev.address + ' — ' + ev.result +
      (ev.evicted ? ', evicted blk ' + ev.evicted.block : '');
    logEl.appendChild(row);
    logRows.push(row);
  });

  function updateHUD() {
    var c = counters(idx);
    countersEl.innerHTML =
      'Accesses <b>' + idx + '</b> / ' + N +
      ' &nbsp; Hits <b>' + c.h + '</b> &nbsp; Misses <b>' + c.m +
      '</b> &nbsp; Evictions <b>' + c.e + '</b>';
    scrubEl.value = String(idx);
    progressEl.textContent = idx + ' / ' + N;
    logRows.forEach(function (row, i) {
      row.className = row.className.replace(' cm-current', '') +
        (i === idx - 1 ? ' cm-current' : '');
    });
    var current = idx > 0 ? P.events[idx - 1] : null;
    if (current) {
      var evicted = current.evicted
        ? ' — evicted block ' + current.evicted.block + ' from way ' + current.evicted.way
        : '';
      var where = current.hasIndex
        ? 'set ' + current.set + ', way ' + current.way
        : 'fully associative, way ' + current.way;
      infoEl.innerHTML =
        '<b>Access ' + current.n + ' of ' + N + '</b> — address ' + current.address +
        ' → block ' + current.block + ' (tag ' + current.tag + ', ' + where + ') — ' +
        '<span class="cm-' + current.result + '">' + current.result.toUpperCase() +
        '</span>' + evicted +
        '<div class="cm-expl">' + current.explanation + '</div>';
    } else {
      infoEl.innerHTML = N === 0
        ? '<b>Empty trace.</b> Nothing to animate.'
        : '<b>Ready.</b> ' + N + ' accesses loaded — press Play or Next.';
    }
    prevEl.disabled = (idx === 0) || animating;
    nextEl.disabled = (idx >= N) || animating;
    playEl.disabled = playing || animating || (idx >= N);
    pauseEl.disabled = !playing;
  }

  // ---------------------------------------------------------- animation
  var raf = null;
  function hideMovers() {
    copyMesh.visible = false; copyLabel.visible = false;
    ghostMesh.visible = false; ghostLabel.visible = false;
    hitPacket.visible = false; addrSprite.visible = false;
  }
  function cancelAnimation() {
    if (raf !== null) { cancelAnimationFrame(raf); raf = null; }
    animating = false;
    hideMovers();
  }
  function finishAccess() { // complete the in-flight access from its snapshot
    cancelAnimation();
    idx += 1;
    applySnapshot(idx);
    updateHUD();
  }

  function reasonChip(ev) {
    if (ev.victimSelection === 'random') return 'Random (seed ' + ev.seed + ')';
    if (ev.victimSelection === 'fifo_oldest') return 'FIFO';
    if (ev.victimSelection === 'lru') return 'LRU';
    if (ev.victimSelection === 'forced') return 'direct';
    return ev.policy || '';
  }

  function lerp(a, b, t) { return a + (b - a) * t; }

  function animateAccess(i, done) { // transitions settled idx=i → i+1
    var ev = P.events[i];
    var slot = slotAt(ev.set, ev.way);
    var slotPos = slot ? slot.mesh.position.clone() : new THREE.Vector3(CACHE_X, 3, 0);
    var src = wallSource(ev.block);
    var mid = new THREE.Vector3(0, BUS_Y + 0.9, 0);
    var cpuPos = cpu.position.clone();
    var phases = [];

    // phase 1 — decode the address (tag | index | offset chips)
    phases.push({
      dur: 550,
      start: function () {
        var text = ev.hasIndex
          ? ['addr ' + ev.address + ' → tag ' + ev.tag + ' | index ' + ev.index +
             ' | offset ' + ev.offset]
          : ['addr ' + ev.address + ' → tag ' + ev.tag + ' | index — | offset ' +
             ev.offset];
        swapSprite(addrSprite, text, {
          size: 32, color: T.text,
          background: DARK ? 'rgba(31,35,43,0.95)' : 'rgba(255,255,255,0.95)'
        });
        addrSprite.scale.set(420 * 0.017, 60 * 0.017, 1);
        addrSprite.position.set(0, 5.4, 0);
        addrSprite.visible = true;
        if (ev.hasIndex && slot) {
          slot.mesh.material = new THREE.MeshLambertMaterial({
            color: T.accent, transparent: true, opacity: 0.45 });
        }
      },
      update: function (t) { addrSprite.position.y = 5.4 + 0.25 * Math.sin(t * Math.PI); }
    });

    if (ev.result === 'hit') {
      // green pulse on the cached copy; response packet returns to the CPU;
      // no memory-to-cache transfer — main memory is not consulted on a hit
      phases.push({
        dur: 850,
        start: function () {
          slot.mesh.material = new THREE.MeshLambertMaterial({ color: T.hit });
          hitPacket.visible = true;
          hitPacket.position.copy(slotPos);
        },
        update: function (t) {
          hitPacket.position.set(
            lerp(slotPos.x, cpuPos.x, t), BUS_Y + 0.4 * Math.sin(t * Math.PI),
            lerp(slotPos.z, cpuPos.z, t));
          var s = 1 + 0.18 * Math.sin(t * Math.PI * 3);
          slot.mesh.scale.set(s, s, s);
        }
      });
    } else {
      if (ev.evicted) {
        // tag mismatch: victim flashes, then its cached copy fades out at the
        // cache — nothing travels back to main memory (read-only model)
        var victimSrc = slotPos.clone();
        phases.push({
          dur: 700,
          start: function () {
            slot.mesh.material = new THREE.MeshLambertMaterial({
              color: T.miss, transparent: true, opacity: 0.95 });
            ghostMesh.visible = true;
            ghostMesh.position.copy(slotPos);
            ghostLabel.visible = true;
            ghostLabel.position.copy(slotPos).add(new THREE.Vector3(0, 0.95, 0));
            swapSprite(ghostLabel, ['blk ' + ev.evicted.block + ' discarded'],
              { size: 28, color: '#FFFFFF',
                background: DARK ? 'rgba(198,40,40,0.9)' : 'rgba(198,40,40,0.95)' });
            ghostLabel.scale.set(320 * 0.016, 64 * 0.016, 1);
          },
          update: function (t) {
            ghostMesh.position.y = victimSrc.y + t * 1.6;
            ghostMesh.material.opacity = 0.85 * (1 - t);
            ghostLabel.position.y = victimSrc.y + 0.95 + t * 1.6;
            ghostLabel.material.opacity = 1 - t;
          }
        });
      } else {
        // empty line — gentle accent pulse on the slot
        phases.push({
          dur: 550,
          start: function () {
            slot.mesh.material = new THREE.MeshLambertMaterial({
              color: T.accent, transparent: true, opacity: 0.35 });
          },
          update: function (t) {
            slot.mesh.material.opacity = 0.35 + 0.2 * Math.sin(t * Math.PI);
          }
        });
      }
      // phase 3 — a copy travels from main memory into the slot (via the bus)
      phases.push({
        dur: 950,
        start: function () {
          copyMesh.visible = true; copyLabel.visible = true;
          copyMesh.position.copy(src);
          copyLabel.position.copy(src).add(new THREE.Vector3(0, 0.95, 0));
          swapSprite(copyLabel, ['blk ' + ev.block + ' (copy)'],
            { size: 28, color: DARK ? '#16181D' : '#FFFFFF',
              background: DARK ? 'rgba(255,183,77,0.95)' : 'rgba(178,106,0,0.95)' });
          copyLabel.scale.set(280 * 0.016, 64 * 0.016, 1);
        },
        update: function (t) {
          if (t < 0.55) {
            var u = t / 0.55;
            copyMesh.position.set(lerp(src.x, mid.x, u),
              lerp(src.y, mid.y, u), lerp(src.z, 0, u));
          } else {
            var u2 = (t - 0.55) / 0.45;
            copyMesh.position.set(lerp(mid.x, slotPos.x, u2),
              lerp(mid.y, slotPos.y, u2), lerp(0, slotPos.z, u2));
          }
          copyLabel.position.copy(copyMesh.position).add(new THREE.Vector3(0, 0.95, 0));
        }
      });
    }

    // final phase — settle to the engine's authoritative snapshot
    phases.push({
      dur: 220,
      start: function () {
        hideMovers();
        applySnapshot(i + 1);
        idx = i + 1;
        updateHUD();
      },
      update: function () {}
    });

    animating = true;
    updateHUD();
    runPhases(phases, function () { if (playing) playChain(); });
  }

  // tiny phase runner: phases = [{dur, start, update(t 0..1)}]
  function runPhases(phases, done) {
    var i = -1, t = 0, last = null;
    function startPhase() {
      i++;
      if (i >= phases.length) {
        animating = false; raf = null;
        if (done) done();
        return true;
      }
      t = 0;
      if (phases[i].start) phases[i].start();
      return false;
    }
    if (startPhase()) return;
    function tick(now) {
      if (last === null) last = now;
      var dt = (now - last) * speed;
      last = now;
      t += dt;
      var ph = phases[i];
      var u = Math.min(1, t / ph.dur);
      if (ph.update) ph.update(u);
      renderer.render(scene, camera);
      if (u >= 1) { if (startPhase()) return; }
      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
  }

  // -------------------------------------------------------- transport
  function settleTo(k) {
    cancelAnimation(); playing = false;
    idx = Math.max(0, Math.min(N, k));
    applySnapshot(idx); updateHUD();
  }

  function playChain() {
    if (!playing || idx >= N || animating) {
      if (idx >= N) playing = false;
      updateHUD();
      return;
    }
    animateAccess(idx, function () { playChain(); });
  }

  playEl.addEventListener('click', function () {
    if (animating || idx >= N) return;
    playing = true; updateHUD(); playChain();
  });
  pauseEl.addEventListener('click', function () {
    playing = false;
    if (animating) finishAccess(); // complete the in-flight access, then hold
    updateHUD();
  });
  nextEl.addEventListener('click', function () {
    if (idx >= N) return;
    settleTo(idx + 1);
  });
  prevEl.addEventListener('click', function () {
    if (idx === 0) return;
    settleTo(idx - 1);
  });
  document.getElementById('cm-replay').addEventListener('click', function () {
    settleTo(0); playing = true; updateHUD(); playChain();
  });
  document.getElementById('cm-reset').addEventListener('click', function () {
    settleTo(0);
  });
  document.getElementById('cm-speed').addEventListener('change', function (e) {
    speed = parseFloat(e.target.value) || 1;
  });
  scrubEl.addEventListener('input', function (e) {
    settleTo(parseInt(e.target.value, 10) || 0);
  });

  // -------------------------------------------------------------- start
  updateCamera(); onResize(); applySnapshot(0); updateHUD();
  renderer.render(scene, camera);
})();
