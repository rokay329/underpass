(() => {
  'use strict';

  // ---------- intro veil: a "tap to enter" gate. Nothing animates until
  // the viewer actually taps/clicks/presses the veil — that same user
  // gesture is what starts the reveal AND fires the entry chime, so the
  // sound can never land early or late relative to the animation (the
  // previous "try to autoplay, else wait for the first stray touch"
  // approach was the reason the music sometimes lagged behind). ----------
  const introVeil = document.getElementById('introVeil');
  const sceneEl = document.getElementById('scene');
  let entered = false;

  // ---------- scene scale: .scene is built at its native 941x1672px size
  // and scaled as one rigid unit via `transform: scale()`, instead of
  // relying on CSS viewport units (100vh/100dvh/100svh) to resize the box
  // that everything else is positioned as a % of. This is what fixes the
  // Safari-only bug where the fx overlays (fire, dog, etc.) would
  // visually detach from the base art the moment Safari's address bar
  // slid in/out mid-tap: with CSS viewport units, that resize changed
  // .scene's actual box size, and its children (a big raster <img> vs.
  // freshly-injected small fx <img>s, sometimes on different GPU
  // compositing layers) didn't always repaint in sync during that resize.
  // A `transform: scale()` composites the whole subtree as a single
  // bitmap-like unit, so nothing inside it can ever drift relative to
  // anything else, no matter how choppy or frequent the resize is. ----------
  const sceneFrameEl = document.getElementById('sceneFrame');
  const SCENE_W = 941;
  const SCENE_H = 1672;
  let sceneScaleRaf = null;

  function updateSceneScale() {
    if (!sceneEl || !sceneFrameEl) return;
    const stageEl = sceneFrameEl.parentElement;
    if (!stageEl) return;
    const stageStyle = getComputedStyle(stageEl);
    const padX = parseFloat(stageStyle.paddingLeft || '0') + parseFloat(stageStyle.paddingRight || '0');
    // Deliberately window.innerWidth/innerHeight (the LAYOUT viewport) here,
    // never window.visualViewport. The layout viewport stays put through
    // both Safari's address-bar show/hide *and* pinch-zoom -- only the
    // visual viewport shrinks for those. Driving this off visualViewport
    // was actively fighting pinch-zoom (zooming in shrinks visualViewport,
    // which made this function shrink the scene back down to "compensate",
    // so the page never appeared to zoom at all, just gained empty margin).
    const availW = window.innerWidth - padX;
    const availH = window.innerHeight;
    const scale = Math.max(0.01, Math.min(availH / SCENE_H, availW / SCENE_W));
    sceneFrameEl.style.width = (SCENE_W * scale) + 'px';
    sceneFrameEl.style.height = (SCENE_H * scale) + 'px';
    sceneEl.style.transform = `scale(${scale})`;
  }

  function scheduleSceneScale() {
    if (sceneScaleRaf) cancelAnimationFrame(sceneScaleRaf);
    sceneScaleRaf = requestAnimationFrame(updateSceneScale);
  }

  updateSceneScale();
  window.addEventListener('resize', scheduleSceneScale);
  window.addEventListener('orientationchange', scheduleSceneScale);

  function enterScene() {
    if (entered) return;
    entered = true;
    if (introVeil) introVeil.classList.add('is-entering');
    if (sceneEl) sceneEl.classList.add('is-entering');
    playSfx('intro'); // fired from the same gesture, so it's always in sync
    // safety net in case animationend doesn't fire for some reason
    setTimeout(() => { if (introVeil) introVeil.remove(); }, 6600);
  }

  if (introVeil) {
    introVeil.addEventListener('click', enterScene);
    introVeil.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        enterScene();
      }
    });
    // IMPORTANT: only react to the veil's OWN fade animation ending, not
    // to animationend events bubbling up from its children (the "눌러서
    // 입장하기" prompt breathes forever under normal motion, but under
    // prefers-reduced-motion every animation — including that one — is
    // forced to finish almost instantly. Without this check, that alone
    // would remove the veil before anyone ever taps it, skipping
    // enterScene() entirely and leaving the scene stuck dark/zoomed in
    // its pre-entry state forever.)
    introVeil.addEventListener('animationend', (e) => {
      if (e.target === introVeil) introVeil.remove();
    });
    // safety net: if someone never taps, still let them in after a while
    // (won't have the chime, since there's no gesture to hang it on)
    setTimeout(enterScene, 12000);
  }

  // ---------- fireflies: small ambient particles drifting over the whole
  // scene at rest, no interaction required. Generated once on load with
  // randomized size/color/drift/twinkle per instance (via inline CSS
  // custom properties), so they don't all look identical. ----------
  (function createFireflies() {
    const container = document.getElementById('fireflies');
    if (!container) return;

    // white / pale yellow / warm gold / ember orange, so the mix leans
    // warm without every speck being the same shade
    const COLORS = ['#fff8e6', '#ffe9a8', '#ffcf8a', '#ff9d4d'];
    const COUNT = 11;
    const frag = document.createDocumentFragment();

    for (let i = 0; i < COUNT; i++) {
      const el = document.createElement('span');
      el.className = 'firefly';

      const size = Math.random() * 2 + 1.6;                // 1.6–3.6px, small and uneven
      const color = COLORS[Math.floor(Math.random() * COLORS.length)];
      const left = Math.random() * 92 + 4;                 // 4%–96%
      const top = Math.random() * 90 + 5;                  // 5%–95%
      const driftDur = Math.random() * 11 + 8;             // 8–19s, slow drift
      const twinkleDur = Math.random() * 4 + 3;            // 3–7s
      const driftDelay = -(Math.random() * driftDur);       // negative delay: staggers start points
      const twinkleDelay = -(Math.random() * twinkleDur);
      const spread = Math.random() * 22 + 10;               // how far it wanders, in px
      const rand = () => (Math.random() * spread * 2 - spread).toFixed(1);
      // about half fully vanish for a stretch of every cycle (op-min: 0),
      // the rest just dim way down — both read as low-key, not a light show
      const vanishes = Math.random() < 0.55;
      const opMin = (vanishes ? 0 : Math.random() * 0.08).toFixed(2);
      const opMax = (Math.random() * 0.3 + 0.45).toFixed(2);
      const glow = (size * 1.8).toFixed(1);
      const glowSpread = (size * 0.75).toFixed(1);

      el.style.cssText = [
        `left:${left.toFixed(1)}%`,
        `top:${top.toFixed(1)}%`,
        `width:${size.toFixed(1)}px`,
        `height:${size.toFixed(1)}px`,
        `background:${color}`,
        `box-shadow:0 0 ${glow}px ${glowSpread}px ${color}`,
        `--dx1:${rand()}px`, `--dy1:${rand()}px`,
        `--dx2:${rand()}px`, `--dy2:${rand()}px`,
        `--dx3:${rand()}px`, `--dy3:${rand()}px`,
        `--op-min:${opMin}`, `--op-max:${opMax}`,
        `animation-duration:${driftDur.toFixed(1)}s, ${twinkleDur.toFixed(1)}s`,
        `animation-delay:${driftDelay.toFixed(1)}s, ${twinkleDelay.toFixed(1)}s`,
      ].join(';');

      frag.appendChild(el);
    }
    container.appendChild(frag);
  })();

  const caption = document.getElementById('caption');

  const FX = {
    fire:    { el: document.getElementById('fxFire'),    src: 'assets/fx-fire.gif',    frames: 32, delay: 110 },
    bed:     { el: document.getElementById('fxBed'),     src: 'assets/fx-bed.gif',     frames: 23, delay: 100 },
    night:   { el: document.getElementById('fxNight'),   src: 'assets/fx-star.gif',    frames: 16, delay: 80  },
    puddle:  { el: document.getElementById('fxPuddle'),  src: 'assets/fx-puddle.gif',  frames: 20, delay: 90  },
    lantern: { el: document.getElementById('fxLantern'), src: 'assets/fx-lantern.gif', frames: 15, delay: 150 },
    tarp:    { el: document.getElementById('fxTarp'),    src: 'assets/fx-tarp.gif',    frames: 10, delay: 240 },
  };

  const CAPTIONS = {
    fire:    '장작이 타닥타닥, 불꽃이 크게 일렁입니다.',
    bed:     '잠시 몸을 누이고 눈을 감아봅니다.',
    night:   '별똥별 하나가 도시의 불빛 위로 스쳐 지나갑니다.',
    puddle:  '고요한 물 위로 파문이 번져갑니다.',
    lantern: '랜턴 불빛이 파르르 떨리다 꺼지고, 잠시 후 다시 밝아집니다.',
    tarp:    '바람 한 줄기가 천막 자락을 스치고 지나갑니다.',
  };

  const SFX_SRC = {
    fire:    'assets/sfx/fire.wav',
    bed:     'assets/sfx/bed.wav',
    night:   'assets/sfx/night.wav',
    puddle:  'assets/sfx/puddle.wav',
    lantern: 'assets/sfx/lantern.wav',
    tarp:    'assets/sfx/tarp.wav',
    dog:     'assets/sfx/dog.wav',
    intro:   'assets/sfx/intro.wav',
  };

  // the dog cycles through a different short reaction on every click, in order
  const fxDogEl = document.getElementById('fxDog');
  const DOG_VARIANTS = [
    { src: 'assets/fx-dog-ear.gif',  frames: 23, delay: 110, caption: '쿤이 귀가 쫑긋 서고, 하트가 떠오릅니다.', sfx: null  },
    { src: 'assets/fx-dog-bark.gif', frames: 11, delay: 110, caption: '쿤이가 멍멍 짖습니다!',          sfx: 'dog' },
  ];
  let dogVariantIndex = 0;
  // #fxDog's own top: normally the resting/bark position, nudged down to
  // 55.7% only while the ear-perk clip is showing, so the ears+hearts clear
  // the dog's real ears with no overlap (set directly on the element --
  // not via a transform -- so its layout position is unambiguous).
  const DOG_TOP_DEFAULT = '53.4%';
  const DOG_TOP_EAR = '53.4%';

  let captionTimer = null;
  function showCaption(text, holdMs = 2400) {
    clearTimeout(captionTimer);
    caption.textContent = text;
    caption.classList.remove('visible');
    void caption.offsetWidth;
    caption.classList.add('visible');
    captionTimer = setTimeout(() => caption.classList.remove('visible'), holdMs);
  }

  // Each fx container tracks every pending timeout it currently owns (not
  // just one) so a rapid re-click — or switching into/out of the meteor
  // shower below, which schedules a whole burst of timers on one
  // container — always cancels cleanly instead of stacking or leaving
  // stray stars behind.
  const activeTimers = new WeakMap();

  function clearElTimers(el) {
    const timers = activeTimers.get(el);
    if (timers) timers.forEach((id) => clearTimeout(id));
    activeTimers.set(el, []);
  }

  function trackTimer(el, id) {
    activeTimers.get(el).push(id);
  }

  function playFxOn(el, src, frames, delay) {
    if (!el) return;
    clearElTimers(el);
    el.innerHTML = '';

    const img = document.createElement('img');
    img.alt = '';
    // cache-bust so a brand-new decode starts from frame 0 every time,
    // even if the same clip was just played
    img.src = `${src}?t=${Date.now()}`;
    el.appendChild(img);
    requestAnimationFrame(() => img.classList.add('shown'));

    const totalMs = frames * delay + 150; // small buffer past the last frame
    trackTimer(el, setTimeout(() => {
      img.classList.remove('shown');
      setTimeout(() => {
        if (el.contains(img)) el.removeChild(img);
      }, 150);
    }, totalMs));
  }

  function playFx(key) {
    const fx = FX[key];
    if (!fx || !fx.el) return;
    playFxOn(fx.el, fx.src, fx.frames, fx.delay);
  }

  // ---------- milestone events: every hotspot gets a bigger, rarer
  // reaction on a specific click count of its own (the night sky's
  // 10-click meteor shower, above/below, was the first of these). All of
  // it is built from the same GIF clips already loaded plus small
  // CSS-driven particles/glow -- no new artwork needed. ----------
  function pulseGlow(className, duration) {
    const el = document.getElementById('milestoneGlow');
    if (!el) return;
    el.classList.remove('pulse-cheer');
    void el.offsetWidth; // restart the animation even if the same class was just used
    el.classList.add(className);
    setTimeout(() => el.classList.remove(className), duration);
  }

  function spawnLeaves() {
    const container = document.getElementById('milestoneParticles');
    if (!container) return;
    const COUNT = 5;
    for (let i = 0; i < COUNT; i++) {
      const el = document.createElement('span');
      el.className = 'leaf';
      const left = 34 + Math.random() * 10;  // starts near the tarp
      const top = 42 + Math.random() * 8;
      const dx = 18 + Math.random() * 14;    // drifts rightward with the gust
      const dy = 10 + Math.random() * 14;
      const rot = 180 + Math.random() * 360;
      const dur = 1.6 + Math.random() * 0.8;
      const delay = Math.random() * 400;
      const color = Math.random() < 0.5 ? 'var(--moss)' : 'var(--ember-strong)';
      el.style.cssText = [
        `left:${left.toFixed(1)}%`,
        `top:${top.toFixed(1)}%`,
        `--leaf-dx:${dx.toFixed(1)}%`,
        `--leaf-dy:${dy.toFixed(1)}%`,
        `--leaf-rot:${rot.toFixed(0)}deg`,
        `animation-duration:${dur.toFixed(2)}s`,
        `animation-delay:${delay.toFixed(0)}ms`,
        `background:${color}`,
      ].join(';');
      container.appendChild(el);
      setTimeout(() => {
        if (container.contains(el)) container.removeChild(el);
      }, dur * 1000 + delay + 150);
    }
  }

  const LANTERN_HUE_DURATION_MS = 2500; // matches lantern-hue-shift's 2.4s + a little slack

  function playLanternMilestone() {
    playFx('lantern');
    const el = FX.lantern.el;
    if (el) {
      el.classList.remove('fx-milestone-hue');
      void el.offsetWidth;
      el.classList.add('fx-milestone-hue');
      // must be removed again once the animation finishes -- otherwise every
      // later click on this hotspot injects a fresh <img> that inherits the
      // still-present class and replays the rainbow sweep forever
      setTimeout(() => el.classList.remove('fx-milestone-hue'), LANTERN_HUE_DURATION_MS);
    }
  }

  function playTarpMilestone() {
    playFx('tarp');
    spawnLeaves();
  }

  const HOTSPOT_MILESTONES = {
    lantern: { every: 9, run: playLanternMilestone, caption: '랜턴 불빛이 알록달록, 색색이 물들었다 사라집니다.' },
    tarp:    { every: 5, run: playTarpMilestone,    caption: '센 바람이 불어와 천막 자락과 낙엽이 함께 흩날립니다.' },
  };
  const hotspotClickCounts = { lantern: 0, tarp: 0 };

  // ---------- meteor shower: every 10th click on the night sky spawns a
  // burst of shooting stars instead of just the one. Reuses the same
  // fx-star.gif clip (its frames are transparent except for the star
  // trail itself), just as several staggered, randomly offset/scaled
  // copies layered inside the same sky hotspot area. ----------
  const NIGHT_KEY = 'night';
  const METEOR_SHOWER_EVERY = 10;
  const METEOR_SHOWER_CAPTION = '별똥별이 우수수 쏟아집니다!';
  const METEOR_SHOWER_CAPTION_HOLD_MS = 5200; // keep the caption up for the whole shower
  let nightClickCount = 0;

  function playMeteorShower() {
    const fx = FX[NIGHT_KEY];
    const el = fx && fx.el;
    if (!el) return;
    clearElTimers(el);
    el.innerHTML = '';

    const { src, frames } = fx;
    const shownDelay = 105;                 // a bit slower per frame than the plain star (80ms)
    const totalMs = frames * shownDelay + 150; // ~1.85s each, so individual trails last longer
    const COUNT = 14;                       // more stars, so the shower reads as sustained

    for (let i = 0; i < COUNT; i++) {
      const startDelay = i * (170 + Math.random() * 220); // spread entrances out over several seconds
      const spawnTimer = setTimeout(() => {
        const img = document.createElement('img');
        img.alt = '';
        img.src = `${src}?t=${Date.now()}_${i}`;
        img.style.position = 'absolute';
        img.style.inset = '0';
        // scatter across the sky crop and vary the scale, so it doesn't
        // read as the same single clip just repeated in place; kept close
        // to center (a slight up-and-right bias, echoing the plain single
        // star) and pulled in on both sides so a star's trail never gets
        // clipped by the crop's left or right edge.
        const dx = (Math.random() * 34 - 9).toFixed(1);
        const dy = (Math.random() * 26 - 7).toFixed(1);
        const scale = (Math.random() * 0.25 + 0.55).toFixed(2);
        img.style.transform = `translate(${dx}%, ${dy}%) scale(${scale})`;
        el.appendChild(img);
        requestAnimationFrame(() => img.classList.add('shown'));

        const removeTimer = setTimeout(() => {
          img.classList.remove('shown');
          setTimeout(() => {
            if (el.contains(img)) el.removeChild(img);
          }, 150);
        }, totalMs);
        trackTimer(el, removeTimer);
      }, startDelay);
      trackTimer(el, spawnTimer);
    }
  }

  function playDogFx() {
    const variant = DOG_VARIANTS[dogVariantIndex];
    dogVariantIndex = (dogVariantIndex + 1) % DOG_VARIANTS.length;
    // the ear-perk clip only ever redraws the ears/forehead, well above the
    // eyes -- give it its own tighter mask (see style.css) so that zone is
    // the only part of the frame that can ever show, instead of sharing the
    // bark clip's taller mask which was drawn to also cover its mouth movement
    const isEar = variant === DOG_VARIANTS[0];
    if (fxDogEl) {
      fxDogEl.classList.toggle('fx-dog-ear', isEar);
      fxDogEl.style.top = isEar ? DOG_TOP_EAR : DOG_TOP_DEFAULT;
    }
    playFxOn(fxDogEl, variant.src, variant.frames, variant.delay);
    if (variant.sfx) playSfx(variant.sfx);
    return variant.caption;
  }

  // every 10th pat: a cheering moment -- the bark reaction plays with a
  // burst of golden "buff" sparks radiating out from the dog, and the
  // whole scene flashes with a brief surge of warm light. Doesn't touch
  // dogVariantIndex, so the normal ear/bark alternation carries on
  // unaffected afterward.
  const DOG_MILESTONE_EVERY = 10;
  const DOG_MILESTONE_CAPTION = '쿤이가 당신을 응원합니다!';
  let dogClickCount = 0;

  // center of the dog's actual drawn face within the bark clip -- measured
  // from fx-dog-bark.gif's own non-transparent content (not the fx box's
  // geometric center, which sits noticeably lower/left of the face since
  // the clip has a lot of empty margin around the character), then mapped
  // into the fx box's position on the scene (left:12.115%, top:55.323%,
  // width:16.259%, height:9.868%). Reused by every buff particle so they
  // all radiate from where the bark is actually happening.
  const DOG_CX = 20.3;
  const DOG_CY = 59.0;
  const SPARK_COLORS = ['#fff3d6', '#ffd98a']; // warm white and gold, alternating
  const BUFF_SPARK_DURATION_MS = 1300; // was 900 -- sparks now drift and hang longer
  const BUFF_RING_DURATION_MS = 1400;  // was 900 -- ring expands more slowly

  function spawnBuffSparks(count, ringDist) {
    const container = document.getElementById('milestoneParticles');
    if (!container) return;
    for (let i = 0; i < count; i++) {
      const el = document.createElement('span');
      el.className = 'buff-spark';
      const angle = (Math.PI * 2 * i) / count + (Math.random() * 0.4 - 0.2);
      const dist = ringDist + Math.random() * 22; // px -- translate() needs
                                                    // real units here, not
                                                    // %, since % on a tiny
                                                    // element resolves
                                                    // against its OWN size
      const dx = (Math.cos(angle) * dist).toFixed(1);
      const dy = (Math.sin(angle) * dist * 0.7).toFixed(1); // flattened a bit
      const delay = Math.random() * 150;
      const color = SPARK_COLORS[i % SPARK_COLORS.length];
      el.style.cssText = [
        `left:${DOG_CX.toFixed(1)}%`,
        `top:${DOG_CY.toFixed(1)}%`,
        `--spark-dx:${dx}px`,
        `--spark-dy:${dy}px`,
        `animation-delay:${delay.toFixed(0)}ms`,
        `background:${color}`,
      ].join(';');
      container.appendChild(el);
      setTimeout(() => {
        if (container.contains(el)) container.removeChild(el);
      }, BUFF_SPARK_DURATION_MS + delay + 150);
    }
  }

  // an expanding golden ring, like a small shockwave, right under the sparks
  function spawnBuffRing() {
    const container = document.getElementById('milestoneParticles');
    if (!container) return;
    const el = document.createElement('span');
    el.className = 'buff-ring';
    el.style.cssText = `left:${DOG_CX.toFixed(1)}%;top:${DOG_CY.toFixed(1)}%;`;
    container.appendChild(el);
    setTimeout(() => {
      if (container.contains(el)) container.removeChild(el);
    }, BUFF_RING_DURATION_MS + 50);
  }

  function playDogMilestone() {
    const bark = DOG_VARIANTS[1];
    if (fxDogEl) {
      fxDogEl.classList.remove('fx-dog-ear'); // always the bark clip, never the tight ear mask
      fxDogEl.style.top = DOG_TOP_DEFAULT;
    }
    playFxOn(fxDogEl, bark.src, bark.frames, bark.delay);
    playSfx('dog');
    spawnBuffRing();
    spawnBuffSparks(10, 30);                          // first burst, right away
    setTimeout(() => spawnBuffSparks(7, 44), 260);     // second, wider wave
    setTimeout(() => spawnBuffSparks(5, 56), 560);     // third, widest -- stretches the burst out
    pulseGlow('pulse-cheer', 3400);
    return DOG_MILESTONE_CAPTION;
  }

  // ---------- interaction sound effects (Web Audio API — supports overlapping
  // rapid re-clicks cleanly, unlike a single reused <audio> element) ----------
  let audioCtx = null;
  const sfxBuffers = new Map();   // key -> in-flight/resolved decode Promise (dedup only)
  const sfxReady = new Map();     // key -> already-decoded AudioBuffer, ready to play instantly
  const SFX_VOLUME = 0.5;         // quieter than the BGM, just a light accent

  function getAudioCtx() {
    if (!audioCtx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return null;
      audioCtx = new Ctx();
    }
    if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {});
    return audioCtx;
  }

  async function loadSfx(key) {
    if (sfxBuffers.has(key)) return sfxBuffers.get(key);
    const ctx = getAudioCtx();
    if (!ctx || !SFX_SRC[key]) return null;
    const promise = fetch(SFX_SRC[key])
      .then((res) => res.arrayBuffer())
      .then((buf) => ctx.decodeAudioData(buf))
      .then((buffer) => {
        sfxReady.set(key, buffer);
        return buffer;
      })
      .catch(() => null);
    sfxBuffers.set(key, promise);
    return promise;
  }

  // Kick off fetch+decode for every sound as soon as the page loads (this
  // needs no user gesture — only *playback* is gated). By the time the
  // viewer actually taps anything, the buffers are already sitting in
  // `sfxReady`, so playSfx() below can start them synchronously instead of
  // going through an `await`. That matters: strict mobile browsers (iOS
  // Safari in particular) only "unlock" audio when a source is started
  // synchronously inside the gesture's own call stack — an `await` in
  // between (e.g. waiting on a network fetch) breaks that link, which is
  // exactly why the entry chime used to stay silent until some *later*
  // interaction finally landed inside an already-unlocked context.
  Object.keys(SFX_SRC).forEach((key) => { loadSfx(key); });

  function startBuffer(ctx, buffer) {
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    const gain = ctx.createGain();
    gain.gain.value = SFX_VOLUME;
    source.connect(gain).connect(ctx.destination);
    source.start();
  }

  function playSfx(key) {
    const ctx = getAudioCtx();
    if (!ctx) return;
    const ready = sfxReady.get(key);
    if (ready) {
      // fast path: no awaiting, so this stays inside the caller's gesture
      startBuffer(ctx, ready);
      return;
    }
    // slow path (buffer not decoded yet, e.g. a very fast first click) —
    // best effort; may be silently blocked on the strictest browsers, but
    // should rarely be hit since decoding starts on page load
    loadSfx(key).then((buffer) => {
      if (buffer) startBuffer(ctx, buffer);
    });
  }

  document.querySelectorAll('.hotspot').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;

      if (target === 'dog') {
        dogClickCount += 1;
        const isDogMilestone = dogClickCount % DOG_MILESTONE_EVERY === 0;
        const dogCaption = isDogMilestone ? playDogMilestone() : playDogFx();
        showCaption(dogCaption, isDogMilestone ? 3600 : 2400);
        return;
      }

      if (target === NIGHT_KEY) {
        nightClickCount += 1;
        if (nightClickCount % METEOR_SHOWER_EVERY === 0) {
          playMeteorShower();
          playSfx(NIGHT_KEY);
          showCaption(METEOR_SHOWER_CAPTION, METEOR_SHOWER_CAPTION_HOLD_MS);
          return;
        }
      }

      const milestone = HOTSPOT_MILESTONES[target];
      if (milestone) {
        hotspotClickCounts[target] += 1;
        if (hotspotClickCounts[target] % milestone.every === 0) {
          milestone.run();
          playSfx(target);
          showCaption(milestone.caption, 3200);
          return;
        }
      }

      playFx(target);
      playSfx(target);
      if (CAPTIONS[target]) showCaption(CAPTIONS[target]);
    });
  });

  // ---------- background music toggle ----------
  const bgmAudio = document.getElementById('bgmAudio');
  const bgmToggle = document.getElementById('bgmToggle');

  if (bgmAudio && bgmToggle) {
    bgmAudio.volume = 0.55;

    bgmToggle.addEventListener('click', () => {
      if (bgmAudio.paused) {
        bgmAudio.play().catch(() => {
          // playback can still fail (e.g. slow load); leave the button in its off state
        });
        bgmToggle.setAttribute('aria-pressed', 'true');
        bgmToggle.setAttribute('aria-label', '배경음악 끄기');
      } else {
        bgmAudio.pause();
        bgmToggle.setAttribute('aria-pressed', 'false');
        bgmToggle.setAttribute('aria-label', '배경음악 켜기');
      }
    });
  }
})();
