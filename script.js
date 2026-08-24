(() => {
  'use strict';

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
  };

  // the dog cycles through a different short reaction on every click, in order
  const fxDogEl = document.getElementById('fxDog');
  const DOG_VARIANTS = [
    { src: 'assets/fx-dog-ear.gif',  frames: 8,  delay: 130, caption: '강아지 귀가 쫑긋 섭니다.',        sfx: null  },
    { src: 'assets/fx-dog-bark.gif', frames: 11, delay: 110, caption: '강아지가 멍멍 짖습니다!',          sfx: 'dog' },
  ];
  let dogVariantIndex = 0;

  let captionTimer = null;
  function showCaption(text) {
    clearTimeout(captionTimer);
    caption.textContent = text;
    caption.classList.remove('visible');
    void caption.offsetWidth;
    caption.classList.add('visible');
    captionTimer = setTimeout(() => caption.classList.remove('visible'), 2400);
  }

  // Each fx container can only play one clip at a time; track its running timer
  // so a rapid re-click restarts cleanly instead of stacking timeouts.
  const activeTimers = new WeakMap();

  function playFxOn(el, src, frames, delay) {
    if (!el) return;
    const prev = activeTimers.get(el);
    if (prev) clearTimeout(prev);
    el.innerHTML = '';

    const img = document.createElement('img');
    img.alt = '';
    // cache-bust so a brand-new decode starts from frame 0 every time,
    // even if the same clip was just played
    img.src = `${src}?t=${Date.now()}`;
    el.appendChild(img);
    requestAnimationFrame(() => img.classList.add('shown'));

    const totalMs = frames * delay + 150; // small buffer past the last frame
    const timer = setTimeout(() => {
      img.classList.remove('shown');
      setTimeout(() => {
        if (el.contains(img)) el.removeChild(img);
      }, 150);
    }, totalMs);
    activeTimers.set(el, timer);
  }

  function playFx(key) {
    const fx = FX[key];
    if (!fx || !fx.el) return;
    playFxOn(fx.el, fx.src, fx.frames, fx.delay);
  }

  function playDogFx() {
    const variant = DOG_VARIANTS[dogVariantIndex];
    dogVariantIndex = (dogVariantIndex + 1) % DOG_VARIANTS.length;
    playFxOn(fxDogEl, variant.src, variant.frames, variant.delay);
    if (variant.sfx) playSfx(variant.sfx);
    return variant.caption;
  }

  // ---------- interaction sound effects (Web Audio API — supports overlapping
  // rapid re-clicks cleanly, unlike a single reused <audio> element) ----------
  let audioCtx = null;
  const sfxBuffers = new Map();   // key -> decoded AudioBuffer (or a pending Promise)
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
      .catch(() => null);
    sfxBuffers.set(key, promise);
    return promise;
  }

  async function playSfx(key) {
    const ctx = getAudioCtx();
    if (!ctx) return;
    const buffer = await loadSfx(key);
    if (!buffer) return;
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    const gain = ctx.createGain();
    gain.gain.value = SFX_VOLUME;
    source.connect(gain).connect(ctx.destination);
    source.start();
  }

  document.querySelectorAll('.hotspot').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;

      if (target === 'dog') {
        const dogCaption = playDogFx();
        showCaption(dogCaption);
        return;
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
