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

  function playFx(key) {
    const fx = FX[key];
    if (!fx || !fx.el) return;

    const prev = activeTimers.get(fx.el);
    if (prev) clearTimeout(prev);
    fx.el.innerHTML = '';

    const img = document.createElement('img');
    img.alt = '';
    // cache-bust so a brand-new decode starts from frame 0 every time,
    // even if the same clip was just played
    img.src = `${fx.src}?t=${Date.now()}`;
    fx.el.appendChild(img);
    requestAnimationFrame(() => img.classList.add('shown'));

    const totalMs = fx.frames * fx.delay + 150; // small buffer past the last frame
    const timer = setTimeout(() => {
      img.classList.remove('shown');
      setTimeout(() => {
        if (fx.el.contains(img)) fx.el.removeChild(img);
      }, 150);
    }, totalMs);
    activeTimers.set(fx.el, timer);
  }

  document.querySelectorAll('.hotspot').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;
      playFx(target);
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
