/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

/**
 * Same-window wall-TV shell. Loaded only when the dashboard URL has moh_tv=.
 * Chrome and tab rotation run on this document so there is no iframe login.
 */
(function () {
  if (window.__mohTvPlayer) {
    return;
  }
  window.__mohTvPlayer = true;

  function tvPreset() {
    var match = /(?:^|[?&])moh_tv=([^&]*)/.exec(window.location.search || '');
    return match ? decodeURIComponent(match[1]) : '';
  }

  var preset = tvPreset();
  if (!preset) {
    return;
  }

  var THEME_KEY = 'superset-dev-theme-override';
  var CFG = {
    canvas: { width: 1920, height: 1080 },
    skipEmptyRatio: 0.8,
    readyTimeoutMs: 25000,
    emptyMarkers: [],
    chrome: {},
    slides: [],
    intervalMs: 30000,
    reloadMinutes: 0,
  };

  function $(id) {
    return document.getElementById(id);
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  function injectCss() {
    if ($('moh-tv-player-css')) {
      return;
    }
    var style = document.createElement('style');
    style.id = 'moh-tv-player-css';
    style.textContent =
      ':root{--tv-letterbox:#05080B;--tv-ink:#14181D;--tv-ink-2:#52606D;' +
      '--tv-ink-3:#626B77;--tv-card:#FFFFFF;--tv-rule:#DCE4EC;--tv-ok:#1E7A4C;' +
      '--tv-ok-bg:#E6F4EC;--tv-warn:#8F5D00;--tv-warn-bg:#FBF0DE;--tv-mod:#0374B8;' +
      '--tv-font:Inter,-apple-system,"Segoe UI",Roboto,sans-serif;' +
      '--tv-mast-h:72px;--tv-strip-h:74px;--tv-head-h:68px;}' +
      'html.moh-tv-active,body.moh-tv-active{margin:0;height:100%;' +
      'background:var(--tv-letterbox);overflow:hidden;}' +
      'body.moh-tv-active.idle{cursor:none;}' +
      '#mohTvPanel{position:fixed;inset:0;background:var(--tv-letterbox);' +
      'overflow:hidden;z-index:40;}' +
      '#mohTvScreen{position:absolute;left:0;top:0;width:1920px;height:1080px;' +
      'transform-origin:0 0;overflow:hidden;background:#EEF2F6;color:var(--tv-ink);' +
      'font-family:var(--tv-font);display:flex;flex-direction:column;}' +
      '#mohTvMast{flex:none;height:var(--tv-mast-h);background:var(--tv-ink);' +
      'display:flex;align-items:center;gap:20px;padding:0 40px;color:#fff;}' +
      '#mohTvMast img{width:52px;height:52px;object-fit:contain;flex:none;}' +
      '#mohTvMast .w1{font-size:27px;font-weight:700;letter-spacing:-.01em;}' +
      '#mohTvMast .w2{font-size:19px;font-weight:500;color:rgba(255,255,255,.72);}' +
      '#mohTvMast .cal{margin-left:auto;text-align:right;}' +
      '#mohTvMast .c1{font-size:23px;font-weight:600;}' +
      '#mohTvMast .c2{font-size:17px;color:rgba(255,255,255,.62);}' +
      '#mohTvStrip{flex:none;height:var(--tv-strip-h);background:var(--tv-card);' +
      'border-bottom:2px solid var(--tv-rule);display:flex;align-items:center;' +
      'gap:20px;padding:0 40px;}' +
      '.moh-tv-strip-item{display:flex;flex-direction:column;gap:2px;min-width:0;}' +
      '.moh-tv-strip-k{font-size:18px;font-weight:600;letter-spacing:.1em;' +
      'text-transform:uppercase;color:var(--tv-ink-3);}' +
      '.moh-tv-strip-v{font-size:24px;font-weight:600;white-space:nowrap;}' +
      '.moh-tv-strip-sep{width:1px;align-self:stretch;background:var(--tv-rule);' +
      'margin:18px 0;}' +
      '.moh-tv-fresh{margin-left:auto;display:inline-flex;align-items:center;' +
      'gap:10px;background:var(--tv-ok-bg);color:var(--tv-ok);border-radius:8px;' +
      'padding:8px 16px;font-size:24px;font-weight:600;}' +
      '.moh-tv-fresh.stale{background:var(--tv-warn-bg);color:var(--tv-warn);}' +
      '.moh-tv-fresh .dot{width:14px;height:14px;border-radius:50%;background:currentColor;}' +
      '#mohTvHead{flex:none;height:var(--tv-head-h);display:flex;align-items:center;' +
      'gap:18px;padding:0 40px;border-top:6px solid var(--tv-mod);' +
      'background:linear-gradient(to bottom,color-mix(in srgb,var(--tv-mod) 7%,transparent),transparent);}' +
      '#mohTvGlyph{min-width:54px;height:54px;padding:0 12px;border-radius:11px;' +
      'background:var(--tv-mod);color:#fff;display:flex;align-items:center;' +
      'justify-content:center;font-size:22px;font-weight:700;}' +
      '#mohTvSlideTitle{font-size:44px;font-weight:700;letter-spacing:-.015em;line-height:1.1;}' +
      '#mohTvStage{flex:1 1 auto;min-height:0;position:relative;overflow:hidden;background:#fff;}' +
      '#mohTvStage #app{height:100%;overflow:hidden;}' +
      '#mohTvLabel{position:absolute;left:16px;bottom:10px;z-index:10;' +
      'font:600 22px/1.2 var(--tv-font);color:#fff;background:rgba(0,0,0,.45);' +
      'padding:6px 12px;border-radius:8px;pointer-events:none;display:none;}' +
      '#mohTvControls{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);' +
      'z-index:50;display:flex;gap:10px;}' +
      '#mohTvControls button{font:600 15px/1 var(--tv-font);color:#fff;' +
      'background:rgba(0,0,0,.5);border:0;cursor:pointer;padding:9px 18px;' +
      'border-radius:8px;opacity:.38;transition:opacity .25s;}' +
      '#mohTvControls button:hover{opacity:1;}' +
      '.moh-ai-overlay,#mohAiOverlay{display:none!important;}';
    document.head.appendChild(style);
  }

  function injectShell() {
    if ($('mohTvPanel')) {
      return;
    }
    injectCss();
    document.documentElement.classList.add('moh-tv-active');
    document.body.classList.add('moh-tv-active');

    var panel = document.createElement('div');
    panel.id = 'mohTvPanel';
    panel.innerHTML =
      '<div id="mohTvScreen">' +
        '<div id="mohTvMast">' +
          '<img id="mohTvLogo" alt="Ministry of Health" src="/moh-static/logomohnewww.png">' +
          '<div>' +
            '<div class="w1" id="mohTvTitle">Ministry of Health</div>' +
            '<div class="w2" id="mohTvWord">Service Delivery</div>' +
          '</div>' +
          '<div class="cal">' +
            '<div class="c1" id="mohTvPeriod"></div>' +
          '</div>' +
        '</div>' +
        '<div id="mohTvStrip">' +
          '<div class="moh-tv-strip-item">' +
            '<div class="moh-tv-strip-k">Geography</div>' +
            '<div class="moh-tv-strip-v" id="mohTvGeo">National · Ethiopia</div>' +
          '</div>' +
          '<div class="moh-tv-strip-sep"></div>' +
          '<div class="moh-tv-strip-item">' +
            '<div class="moh-tv-strip-k">Period</div>' +
            '<div class="moh-tv-strip-v" id="mohTvStripPeriod"></div>' +
          '</div>' +
          '<div class="moh-tv-strip-sep"></div>' +
          '<div class="moh-tv-strip-item">' +
            '<div class="moh-tv-strip-k">Source</div>' +
            '<div class="moh-tv-strip-v" id="mohTvSource">DHIS2 · Routine</div>' +
          '</div>' +
          '<div class="moh-tv-fresh" id="mohTvFresh">' +
            '<span class="dot"></span><span id="mohTvFreshText">Data as of …</span>' +
          '</div>' +
        '</div>' +
        '<div id="mohTvHead">' +
          '<div id="mohTvGlyph">TV</div>' +
          '<div id="mohTvSlideTitle"></div>' +
        '</div>' +
        '<div id="mohTvStage"><div id="mohTvLabel"></div></div>' +
      '</div>';
    document.body.appendChild(panel);

    var controls = document.createElement('div');
    controls.id = 'mohTvControls';
    controls.innerHTML =
      '<button id="mohTvPrev" type="button">◀ Prev</button>' +
      '<button id="mohTvFs" type="button">⛶ Fullscreen</button>' +
      '<button id="mohTvNext" type="button">Next ▶</button>';
    document.body.appendChild(controls);

    var app = $('app');
    var stage = $('mohTvStage');
    if (app && stage) {
      stage.insertBefore(app, $('mohTvLabel'));
    }
  }

  function placeScreen() {
    var screenEl = $('mohTvScreen');
    if (!screenEl) {
      return;
    }
    var k = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    screenEl.style.transform =
      'translate(' + ((window.innerWidth - 1920 * k) / 2) + 'px,' +
      ((window.innerHeight - 1080 * k) / 2) + 'px) scale(' + k + ')';
  }

  function idleCursor() {
    var timer = 0;
    var bump = function () {
      document.body.classList.remove('idle');
      clearTimeout(timer);
      timer = setTimeout(function () {
        document.body.classList.add('idle');
      }, 3000);
    };
    ['mousemove', 'keydown', 'pointerdown'].forEach(function (ev) {
      document.addEventListener(ev, bump, { passive: true });
    });
    bump();
  }

  function goFullscreen() {
    var el = document.documentElement;
    var fn = el.requestFullscreen || el.webkitRequestFullscreen
      || el.mozRequestFullScreen || el.msRequestFullscreen;
    if (fn && !document.fullscreenElement && !document.webkitFullscreenElement) {
      try { fn.call(el); } catch (err) { /* needs gesture */ }
    }
  }

  function toggleFullscreen() {
    if (document.fullscreenElement || document.webkitFullscreenElement) {
      (document.exitFullscreen || document.webkitExitFullscreen || function () {}).call(document);
    } else {
      goFullscreen();
    }
  }

  function syncControls() {
    var fsBtn = $('mohTvFs');
    if (!fsBtn) {
      return;
    }
    var full = !!(document.fullscreenElement || document.webkitFullscreenElement);
    fsBtn.textContent = full ? '⛶ Exit' : '⛶ Fullscreen';
  }

  function applyTheme(theme) {
    if (!theme) {
      return;
    }
    try {
      localStorage.setItem(THEME_KEY, JSON.stringify(theme));
      window.addEventListener('pagehide', function () {
        try { localStorage.removeItem(THEME_KEY); } catch (err) { /* ignore */ }
      });
    } catch (err) { /* storage blocked */ }
  }

  function setAccent(color) {
    document.documentElement.style.setProperty('--tv-mod', color || '#0374B8');
  }

  function glyphText(title) {
    var words = String(title || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) {
      return 'TV';
    }
    if (words.length === 1) {
      return words[0].slice(0, 3).toUpperCase();
    }
    return words.slice(0, 2).map(function (word) {
      return word[0];
    }).join('').toUpperCase();
  }

  var clipped = false;
  var warned = {};
  var slideIndex = -1;
  var liveYear = '';

  function applyYear(year) {
    if (year) {
      liveYear = year;
    }
    var shown = liveYear || '';
    if ($('mohTvPeriod')) {
      $('mohTvPeriod').textContent = shown;
    }
    if ($('mohTvStripPeriod')) {
      $('mohTvStripPeriod').textContent = shown;
    }
  }

  function yearFromPeriod(period) {
    if (!period || period.fiscalYear == null) {
      return '';
    }
    var fy = String(period.fiscalYear);
    return /^\d{4}$/.test(fy) ? fy + ' EFY' : fy;
  }

  function paintChrome(n) {
    var slide = CFG.slides[n === undefined ? slideIndex : n] || {};
    var chrome = CFG.chrome || {};
    var title = slide.label || '';
    setAccent(slide.accent || '#0374B8');
    if ($('mohTvTitle')) $('mohTvTitle').textContent = chrome.title || 'Ministry of Health';
    if ($('mohTvWord')) $('mohTvWord').textContent = chrome.wordmark || '';
    applyYear(liveYear);
    if ($('mohTvLogo') && chrome.logoUrl) $('mohTvLogo').src = chrome.logoUrl;
    if ($('mohTvGeo')) $('mohTvGeo').textContent = chrome.geography || '';
    if ($('mohTvSource')) {
      $('mohTvSource').textContent =
        sourcesFromChartTitles() || slide.source || chrome.source || '';
    }
    if ($('mohTvSlideTitle')) $('mohTvSlideTitle').textContent = title;
    if ($('mohTvGlyph')) $('mohTvGlyph').textContent = glyphText(title);
    var label = $('mohTvLabel');
    if (label) {
      label.textContent = clipped
        ? title + ' · too tall — clipped, not scaled'
        : '';
      label.style.display = clipped ? 'block' : 'none';
    }
    if (clipped && title && !warned[title]) {
      warned[title] = true;
      console.warn('TV: "' + title + '" is taller than the 1920×1080 stage. '
        + 'Split or trim the dashboard tab. Type is not scaled.');
    }
  }

  var SOURCE_MARKERS = [
    [/EDHS/i, 'EDHS'],
    [/Mini-?EDHS|MEDHS/i, 'Mini-EDHS'],
    [/EmONC/i, 'EmONC'],
    [/SARA|\bSPA\b/i, 'SPA'],
    [/NHWA/i, 'NHWA'],
    [/eLMIS|\bLMIS\b/i, 'eLMIS'],
    [/\bNHA\b/i, 'NHA'],
    [/\bPHEM\b/i, 'PHEM'],
    [/\bHRIS\b/i, 'HRIS'],
    [/\bHFR\b/i, 'HFR'],
    [/\bHMIS\b|\bDHIS2\b/i, 'DHIS2'],
  ];

  function sourcesFromChartTitles() {
    var found = [];
    document.querySelectorAll(
      '.dashboard-component-chart-holder .header-title, ' +
      '.dashboard-component-chart-holder [data-test="editable-title"]'
    ).forEach(function (el) {
      var text = el.textContent || '';
      SOURCE_MARKERS.forEach(function (pair) {
        if (pair[0].test(text) && found.indexOf(pair[1]) === -1) {
          found.push(pair[1]);
        }
      });
    });
    if (!found.length) {
      return '';
    }
    if (found.length === 1 && found[0] === 'DHIS2') {
      return 'DHIS2 · Routine';
    }
    return found.join(' · ');
  }

  function formatFreshness(period) {
    if (!period || period.fiscalYear == null) {
      return null;
    }
    var fy = String(period.fiscalYear);
    var year = /^\d{4}$/.test(fy) ? fy + ' EFY' : fy;
    var extra = period.monthName || (period.quarter != null ? ('Q' + period.quarter) : '');
    return extra ? year + ' · ' + extra : year;
  }

  function loadFreshness() {
    var url = CFG.chrome && CFG.chrome.freshnessUrl;
    var chip = $('mohTvFresh');
    var text = $('mohTvFreshText');
    if (!url || !chip || !text) {
      return;
    }
    fetch(url, { credentials: 'same-origin' })
      .then(function (resp) {
        return resp.ok ? resp.json() : Promise.reject();
      })
      .then(function (data) {
        var period =
          (data.sources && data.sources.routine && data.sources.routine.monthly)
          || (data.sources && data.sources.routine && data.sources.routine.quarterly);
        applyYear(yearFromPeriod(period));
        var asOf = formatFreshness(period);
        if (asOf) {
          text.textContent = 'Data as of ' + asOf;
          chip.classList.remove('stale');
        } else {
          text.textContent = 'Data as of Not available';
          chip.classList.add('stale');
        }
      })
      .catch(function () {
        text.textContent = 'Data as of Not available';
        chip.classList.add('stale');
      });
  }

  function setImp(el, prop, value) {
    if (el && el.style) {
      el.style.setProperty(prop, value, 'important');
    }
  }

  function hideEl(el) {
    setImp(el, 'display', 'none');
  }

  function alignChartTitles() {
    document.querySelectorAll(
      '[data-test="chart-context-chip"],[data-test="dashboard-context-strip"]'
    ).forEach(hideEl);
    document.querySelectorAll(
      '.dashboard-component-chart-holder .header-controls'
    ).forEach(hideEl);
    document.querySelectorAll(
      '.dashboard-component-chart-holder .slice-header,' +
      '.dashboard-component-chart-holder [data-test="slice-header"]'
    ).forEach(function (header) {
      setImp(header, 'display', 'flex');
      setImp(header, 'flex-wrap', 'nowrap');
      setImp(header, 'align-items', 'center');
      setImp(header, 'height', '40px');
      setImp(header, 'min-height', '40px');
      setImp(header, 'max-height', '40px');
      setImp(header, 'margin', '0 0 8px 0');
      setImp(header, 'padding', '0 4px');
      setImp(header, 'overflow', 'hidden');
    });
    document.querySelectorAll(
      '.dashboard-component-chart-holder .header-title,' +
      '.dashboard-component-chart-holder .header-title *,' +
      '.dashboard-component-chart-holder [data-test="editable-title"]'
    ).forEach(function (title) {
      setImp(title, 'display', 'block');
      setImp(title, 'flex', '1 1 auto');
      setImp(title, 'width', '100%');
      setImp(title, 'max-width', '100%');
      setImp(title, 'min-width', '0');
      setImp(title, 'height', '40px');
      setImp(title, 'line-height', '40px');
      setImp(title, 'font-size', '22px');
      setImp(title, 'font-weight', '600');
      setImp(title, 'white-space', 'nowrap');
      setImp(title, 'overflow', 'hidden');
      setImp(title, 'text-overflow', 'ellipsis');
      setImp(title, '-webkit-line-clamp', '1');
      setImp(title, '-webkit-box-orient', 'unset');
    });
  }

  function unlockScroll() {
    var style = $('moh-tv-unlock');
    if (!style) {
      style = document.createElement('style');
      style.id = 'moh-tv-unlock';
      (document.head || document.documentElement).appendChild(style);
    }
    style.textContent =
      'html,body{height:auto!important;overflow:hidden!important;margin:0!important;' +
      'font-family:Inter,-apple-system,"Segoe UI",Roboto,sans-serif!important;}' +
      '#app,.ant-layout,.ant-layout-content,.ant-layout-content>div,' +
      '.dashboard,.dashboard-content,.grid-content,[data-test="grid-content"]' +
      '{height:auto!important;max-height:none!important;overflow:visible!important;' +
      'margin:0!important;padding:0!important;}' +
      '.dashboard{padding-top:0!important;margin-top:0!important;}' +
      '#main-menu,header.top,.navbar,.ant-layout-header,.dashboard-header-container,' +
      '[data-test="dashboard-header-wrapper"],.dashboard-header-container .header-with-actions,' +
      '[data-test="dashboard-filters-panel"],.dashboard-filters-panel,' +
      '.moh-ai-overlay,#mohAiOverlay,.moh-ai-toggle,#mohAiToggle,#mohAiPanel,' +
      '[class*="HoverMenu"],.hover-menu,[data-test="dashboard-component-chart-holder"] .header-controls' +
      '{display:none!important;}' +
      '.dashboard,.dashboard-content,[data-test="dashboard-content"],' +
      '[class*="dashboard-builder"],.grid-content,[data-test="grid-content"],' +
      '.dashboard-grid{max-width:none!important;width:100%!important;}' +
      '.ant-tabs-nav,[data-test="dashboard-component-tabs"] .ant-tabs-nav' +
      '{display:none!important;}' +
      'html.moh-tv-active [data-test="chart-context-chip"],' +
      'html.moh-tv-active [data-test="dashboard-context-strip"]' +
      '{display:none!important;}' +
      'html.moh-tv-active .dashboard-component-chart-holder .slice-header,' +
      'html.moh-tv-active .dashboard-component-chart-holder [data-test="slice-header"]' +
      '{display:flex!important;flex-wrap:nowrap!important;align-items:center!important;' +
      'height:40px!important;min-height:40px!important;max-height:40px!important;' +
      'margin:0 0 8px!important;padding:0 4px!important;overflow:hidden!important;}' +
      'html.moh-tv-active .dashboard-component-chart-holder .header-title,' +
      'html.moh-tv-active .dashboard-component-chart-holder .header-title *,' +
      'html.moh-tv-active .dashboard-component-chart-holder [data-test="editable-title"]' +
      '{display:block!important;flex:1 1 auto!important;width:100%!important;' +
      'max-width:100%!important;min-width:0!important;height:40px!important;' +
      'line-height:40px!important;font-size:22px!important;font-weight:600!important;' +
      'white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;' +
      '-webkit-line-clamp:1!important;}';
    alignChartTitles();
  }

  function hideTabBars() {
    document.querySelectorAll(
      '.ant-tabs-nav, [data-test="dashboard-component-tabs"] .ant-tabs-nav'
    ).forEach(function (el) {
      el.style.display = 'none';
    });
  }

  function contentHeight() {
    var grid = document.querySelector('[data-test="grid-content"]')
      || document.querySelector('.grid-content')
      || document.querySelector('.dashboard-grid');
    if (grid && grid.scrollHeight > 40) {
      return grid.scrollHeight;
    }
    return (document.body && document.body.scrollHeight) || window.innerHeight;
  }

  var resizeObs = null;
  var resizeObsTarget = null;

  function wireResizeObserver() {
    var target = document.querySelector('[data-test="grid-content"]')
      || document.querySelector('.grid-content')
      || document.querySelector('.dashboard-grid');
    if (!target || target === resizeObsTarget) {
      return;
    }
    if (resizeObs) {
      resizeObs.disconnect();
    }
    resizeObsTarget = target;
    resizeObs = new ResizeObserver(function () {
      fit();
    });
    resizeObs.observe(target);
  }

  function fit() {
    unlockScroll();
    hideTabBars();
    alignChartTitles();
    wireResizeObserver();
    var stage = $('mohTvStage');
    var stageH = (stage && stage.clientHeight) || CFG.canvas.height;
    clipped = contentHeight() > stageH + 8;
    paintChrome();
  }

  var fitTimers = [];
  function scheduleFit() {
    fitTimers.forEach(clearTimeout);
    fitTimers = [800, 2000, 5000].map(function (delay) {
      return setTimeout(fit, delay);
    });
  }

  function isVisible(el) {
    return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  }

  function findTab(title) {
    var fallback = null;
    var tabs = document.querySelectorAll('.ant-tabs-tab');
    for (var i = 0; i < tabs.length; i += 1) {
      var tab = tabs[i];
      var btn = tab.querySelector('.ant-tabs-tab-btn');
      if (((btn || tab).textContent || '').trim() === title) {
        if (isVisible(tab)) {
          return tab;
        }
        fallback = fallback || tab;
      }
    }
    return fallback;
  }

  async function clickPath(path, my) {
    for (var p = 0; p < path.length; p += 1) {
      if (my !== token) {
        return false;
      }
      var el = null;
      for (var attempt = 0; attempt < 10 && !(el = findTab(path[p])); attempt += 1) {
        await sleep(400);
        if (my !== token) {
          return false;
        }
      }
      if (!el) {
        throw new Error('tab not found: ' + path[p]);
      }
      el.click();
      await sleep(450);
      if (my !== token) {
        return false;
      }
    }
    await sleep(1000);
    return true;
  }

  function slideState() {
    var st = { total: 0, loading: 0, empty: 0, error: 0 };
    document.querySelectorAll('[data-test="dashboard-component-chart-holder"]')
      .forEach(function (holder) {
        if (!isVisible(holder)) {
          return;
        }
        st.total += 1;
        if (holder.querySelector('[data-test="loading-indicator"]')) {
          st.loading += 1;
        } else if (holder.querySelector('.ant-alert-error,[data-test="error-message"]')) {
          st.error += 1;
        } else {
          var text = holder.textContent || '';
          if (CFG.emptyMarkers.some(function (marker) {
            return text.indexOf(marker) !== -1;
          })) {
            st.empty += 1;
          }
        }
      });
    return st;
  }

  var token = 0;
  var skipStreak = 0;
  var slideTimer = null;
  var watchdog = null;

  function startTimer() {
    stopTimer();
    clearTimeout(watchdog);
    if (CFG.slides.length > 1) {
      slideTimer = setInterval(next, CFG.intervalMs);
    }
  }

  function stopTimer() {
    if (slideTimer) {
      clearInterval(slideTimer);
      slideTimer = null;
    }
  }

  async function settle(n, my) {
    var t0 = Date.now();
    var calm = 0;
    while (my === token && Date.now() - t0 < CFG.readyTimeoutMs) {
      await sleep(500);
      var st = slideState();
      var quiet = st.total > 0 ? st.loading === 0 : Date.now() - t0 >= 4000;
      calm = quiet ? calm + 1 : 0;
      if (calm >= 3) {
        break;
      }
    }
    if (my !== token) {
      return;
    }
    fit();
    var state = slideState();
    var blank = state.total === 0 && contentHeight() < 120;
    var unusable = state.total > 0
      && (state.empty + state.error) / state.total >= CFG.skipEmptyRatio;
    if ((blank || unusable) && CFG.slides.length > 1
        && skipStreak < CFG.slides.length - 1) {
      skipStreak += 1;
      console.warn('TV: skipping "' + CFG.slides[n].label + '" — '
        + (blank ? 'nothing rendered'
          : (state.empty + state.error) + ' of ' + state.total + ' cards empty or failed'));
      next();
      return;
    }
    skipStreak = 0;
    startTimer();
  }

  async function waitForGrid(my) {
    var t0 = Date.now();
    while (my === token && Date.now() - t0 < CFG.readyTimeoutMs) {
      if (document.querySelector(
        '[data-test="grid-content"],.grid-content,.dashboard-grid'
      )) {
        return true;
      }
      await sleep(400);
    }
    return false;
  }

  async function run(n) {
    var my = ++token;
    clipped = false;
    paintChrome(n);
    stopTimer();
    if (!(await waitForGrid(my)) || my !== token) {
      return;
    }
    try {
      if (await clickPath(CFG.slides[n].path, my) && my === token) {
        scheduleFit();
        await settle(n, my);
      }
    } catch (err) {
      if (my !== token) {
        return;
      }
      console.warn('TV: could not open slide', CFG.slides[n] && CFG.slides[n].label, err);
      startTimer();
    }
  }

  function go() {
    stopTimer();
    clearTimeout(watchdog);
    watchdog = setTimeout(function () {
      if (!slideTimer) {
        startTimer();
      }
    }, CFG.readyTimeoutMs + 20000);
    run(slideIndex);
  }

  function next() {
    slideIndex = (slideIndex + 1) % CFG.slides.length;
    go();
  }

  function prev() {
    slideIndex = (slideIndex - 1 + CFG.slides.length) % CFG.slides.length;
    go();
  }

  function bindControls() {
    var controls = $('mohTvControls');
    if (!controls) {
      return;
    }
    document.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowRight') {
        next();
      } else if (event.key === 'ArrowLeft') {
        prev();
      } else {
        goFullscreen();
      }
    });
    controls.addEventListener('click', function (event) {
      event.stopPropagation();
      if (event.target && event.target.id === 'mohTvNext') {
        next();
      } else if (event.target && event.target.id === 'mohTvPrev') {
        prev();
      } else if (event.target && event.target.id === 'mohTvFs') {
        toggleFullscreen();
      }
    });
  }

  function startPlayer() {
    injectShell();
    placeScreen();
    window.addEventListener('resize', function () {
      placeScreen();
      fit();
    });
    idleCursor();
    goFullscreen();
    document.addEventListener('fullscreenchange', syncControls);
    document.addEventListener('webkitfullscreenchange', syncControls);
    bindControls();
    loadFreshness();
    unlockScroll();
    if (!CFG.slides.length) {
      if ($('mohTvSlideTitle')) {
        $('mohTvSlideTitle').textContent = 'No TV slides configured.';
      }
      return;
    }
    next();
    if (CFG.reloadMinutes > 0) {
      setInterval(function () {
        window.location.reload();
      }, CFG.reloadMinutes * 60000);
    }
  }

  function applyConfig(data) {
    CFG = Object.assign(CFG, data || {});
    CFG.canvas = CFG.canvas || { width: 1920, height: 1080 };
    CFG.skipEmptyRatio = CFG.skipEmptyRatio || 0.8;
    CFG.readyTimeoutMs = CFG.readyTimeoutMs || 25000;
    CFG.emptyMarkers = CFG.emptyMarkers || [];
    CFG.chrome = CFG.chrome || {};
    CFG.slides = CFG.slides || [];
    applyTheme(CFG.theme);
    startPlayer();
  }

  function bounceToLogin() {
    var nextUrl = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace('/login/?next=' + nextUrl);
  }

  fetch('/moh-static/tv-config/' + encodeURIComponent(preset), {
    credentials: 'same-origin',
  }).then(function (resp) {
    if (resp.status === 401) {
      bounceToLogin();
      return null;
    }
    if (!resp.ok) {
      throw new Error('tv-config ' + resp.status);
    }
    return resp.json();
  }).then(function (data) {
    if (data) {
      applyConfig(data);
    }
  }).catch(function (err) {
    console.warn('TV player failed to load config', err);
  });
})();
