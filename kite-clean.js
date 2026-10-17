(function () {
  if (document.documentElement.dataset.kiteClean === '1') return;
  document.documentElement.dataset.kiteClean = '1';
  document.body.classList.remove('solo-chart');
  document.body.classList.add('kite-clean');
  var legacyRow = document.querySelector('.fixed-trading-row');
  if (legacyRow && legacyRow.parentElement) {
    var grid = legacyRow.parentElement;
    while (legacyRow.firstChild) grid.appendChild(legacyRow.firstChild);
    legacyRow.remove();
  }
  var docked = document.getElementById('optionChainDialog');
  if (docked && docked.open) {
    try { docked.close(); } catch (err) {}
  }
  var multi = !!document.getElementById('workspace');
  var chainRows = [];
  if (multi) document.body.classList.add('kite-multi');

  function el(tag, id, cls) {
    var node = document.createElement(tag);
    if (id) node.id = id;
    if (cls) node.className = cls;
    return node;
  }
  function svg(path) {
    var holder = document.createElement('div');
    holder.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">' + path + '</svg>';
    return holder.firstChild;
  }

  var root = el('div', 'kiteClean');
  var strip = el('div', 'kiteStrip');
  var quotes = el('div', 'kiteQuotes');
  var tools = el('div', 'kiteTools');
  var balance = el('div', 'kiteBalance');
  var balanceValue = el('div', 'kiteBalanceValue');
  var balanceLabel = el('span', '', 'kiteBalanceLabel');
  balanceLabel.textContent = 'Trading Balance';
  balance.append(balanceLabel, balanceValue);
  var holdHost = el('div', 'kiteHold');
  var bar = el('div', 'kiteBar');
  bar.setAttribute('aria-label', 'Chart tools');
  var draw = el('div', 'kiteDraw');
  draw.setAttribute('aria-label', 'Drawing tools');
  var drawSide = el('div', 'kiteDrawSide');
  drawSide.setAttribute('aria-label', 'Drawing tools');
  var barLeft = el('div', 'kiteBarLeft');
  var barCenter = el('div', 'kiteBarCenter');
  var barRight = el('div', 'kiteBarRight');
  var stage = el('div', 'kiteStage');
  var charts = el('div', 'kiteCharts');
  var rail = el('div', 'kiteRail');
  rail.setAttribute('aria-label', 'Side panels');
  var drawer = el('div', 'kiteDrawer');
  drawer.hidden = true;
  var positions = el('div', 'kitePositions');
  positions.setAttribute('aria-label', 'Positions');
  var ordersHost = el('div', 'kiteOrders');
  ordersHost.setAttribute('aria-label', 'Orders');
  var depthHost = el('div', 'kiteDepth');
  depthHost.setAttribute('aria-label', 'Market depth');
  var chainHost = el('div', 'kiteChain');
  chainHost.setAttribute('aria-label', 'Option chain');
  var chainPop = el('div', 'kiteChainPop');
  chainPop.hidden = true;
  var chainSheet = el('div', 'kiteChainSheet');
  var chainTop = el('div', '', 'kiteChainTop');
  var chainTitle = document.createElement('h2');
  chainTitle.textContent = 'Option Chain';
  var chainClose = document.createElement('button');
  chainClose.type = 'button';
  chainClose.className = 'kiteChainClose';
  chainClose.setAttribute('aria-label', 'Close option chain');
  chainClose.textContent = '✕';
  chainTop.append(chainTitle, chainClose);
  chainSheet.append(chainTop, chainHost);
  chainPop.append(chainSheet);
  var presetsHost = el('div', 'kitePresets');
  presetsHost.setAttribute('aria-label', 'Order presets');
  drawer.append(positions, ordersHost, depthHost, presetsHost);
  document.body.append(chainPop);
  chainClose.onclick = function () { closeChain(); };
  chainPop.addEventListener('click', function (event) {
    if (event.target === chainPop) closeChain();
  });
  var tickets = el('div', 'kiteTickets');
  var call = el('div', 'kiteCall');
  var pnl = el('div', 'kitePnl');
  var pnlLabel = el('span');
  pnlLabel.textContent = 'Unrealized P&L';
  var pnlValue = el('b', 'kitePnlValue');
  pnlValue.textContent = '—';
  pnl.append(pnlLabel, pnlValue);
  var strikeLock = { CE: '', PE: '' };
  var mtmCacheOn = null;
  var ticketPaintTimer = null;
  var put = el('div', 'kitePut');
  strip.append(quotes, balance);
  barLeft.append(draw);
  bar.append(barLeft, barCenter, barRight);
  stage.append(drawSide, charts, rail, drawer);
  tickets.append(call, pnl, put);
  root.append(strip, bar, stage, tickets);
  document.body.insertBefore(root, document.body.firstChild);

  function move(node, parent) {
    if (node && parent && node.parentElement !== parent) parent.append(node);
  }
  function labelOf(id) {
    var node = document.getElementById(id);
    return node ? node.closest('label') : null;
  }

  move(document.getElementById('holdExitBar'), holdHost);
  move(document.getElementById('message'), holdHost);

  function moneyNumber(text) {
    var raw = String(text == null ? '' : text).replace(/\u20b9/g, '').replace(/,/g, '').replace(/\u2212/g, '-').replace(/\s/g, '');
    if (!raw || raw === '\u2014' || raw === '-' || raw === 'Pending') return null;
    var value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }
  function paintTicketPnl() {
    var total = null;
    if (!multi) {
      var sum = 0;
      var any = false;
      document.querySelectorAll('.manual-pnl-summary').forEach(function (node) {
        var raw = node.dataset.running;
        if (raw === undefined || raw === '') return;
        var value = Number(raw);
        if (!Number.isFinite(value)) return;
        sum += value;
        any = true;
      });
      if (any) total = sum;
    } else {
      total = moneyNumber((document.getElementById('pnl-running') || {}).textContent);
    }
    if (total == null) {
      pnlValue.textContent = '\u2014';
      pnlValue.dataset.sign = '';
      return;
    }
    pnlValue.textContent = total.toLocaleString('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 });
    pnlValue.dataset.sign = total > 0 ? 'up' : total < 0 ? 'down' : '';
  }

  var KITE_SCREEN_THEMES = {
    normal: { name: 'Normal', bg: '#FFFFFF', surface: '#F7F9FC', alt: '#EDF1F6', ink: '#243348', muted: '#526075', edge: '#C8D1DE', grid: '#E1E6EE', green: '#067044', red: '#B8293E', blue: '#2459A8', scheme: 'light' },
    dark: { name: 'Dark', bg: '#10161E', surface: '#18212C', alt: '#24303E', ink: '#E1E8F2', muted: '#B7C4D5', edge: '#46566B', grid: '#303C4B', green: '#58DF9B', red: '#FF929A', blue: '#8ABFFF', scheme: 'dark' },
    cream: { name: 'Soft Cream', bg: '#FAF4E8', surface: '#F5EDDD', alt: '#EEE4D2', ink: '#353028', muted: '#655947', edge: '#CBBEAA', grid: '#DFD4BE', green: '#07683F', red: '#AE293B', blue: '#2455A0', scheme: 'light' },
    grey: { name: 'Grey', bg: '#2F2F33', surface: '#35353B', alt: '#414149', ink: '#F0F0F5', muted: '#CDCDD9', edge: '#62626F', grid: '#494951', green: '#6AE6AC', red: '#FFA3AA', blue: '#A0C9FF', scheme: 'dark' },
    graphite: { name: 'Graphite', bg: '#181B20', surface: '#22262D', alt: '#303640', ink: '#E5E7EB', muted: '#A8B0BC', edge: '#505058', grid: '#303033', green: '#58DF9B', red: '#FF929A', blue: '#8ABFFF', scheme: 'dark' },
    navy: { name: 'Dark Navy', bg: '#1E222D', surface: '#262B38', alt: '#303748', ink: '#E6EBF5', muted: '#BEC8DB', edge: '#515D76', grid: '#363E50', green: '#65E1AA', red: '#FF9BA5', blue: '#99C6FF', scheme: 'dark' },
    sepia: { name: 'Warm Sepia', bg: '#F5F2EB', surface: '#F0EBE1', alt: '#E6DFD3', ink: '#2C2C2C', muted: '#625A4D', edge: '#C8BFAF', grid: '#DCD5C8', green: '#07683F', red: '#AC293B', blue: '#2455A0', scheme: 'light' },
    sage: { name: 'Soft Sage', bg: '#E8ECE9', surface: '#DFE6E0', alt: '#D3DDD5', ink: '#1E293B', muted: '#46574D', edge: '#B0C0B4', grid: '#C6D1C9', green: '#075D38', red: '#A52439', blue: '#244F97', scheme: 'light' }
  };
  var kiteThemeKey = 'normal';
  function chartTargets() {
    var list = [];
    if (window.mc325Charts) {
      ['CE', 'PE', 'REF'].forEach(function (side) {
        if (window.mc325Charts[side] && window.mc325Charts[side].chart) list.push(window.mc325Charts[side]);
      });
    }
    if (window.shivMultiPanes) {
      Object.keys(window.shivMultiPanes).forEach(function (key) {
        var pane = window.shivMultiPanes[key];
        if (pane && pane.chart) list.push(pane);
      });
    }
    return list;
  }
  function applyKiteScreenTheme(key, save) {
    var theme = KITE_SCREEN_THEMES[key] || KITE_SCREEN_THEMES.normal;
    kiteThemeKey = KITE_SCREEN_THEMES[key] ? key : 'normal';
    document.body.dataset.screenTheme = kiteThemeKey;
    document.documentElement.style.colorScheme = theme.scheme;
    [['bg', theme.bg], ['surface', theme.surface], ['alt', theme.alt], ['edge', theme.edge], ['scheme', theme.scheme]].forEach(function (pair) {
      document.body.style.setProperty('--screen-' + pair[0], pair[1]);
    });
    document.body.style.setProperty('--ink', theme.ink);
    document.body.style.setProperty('--muted', theme.muted);
    chartTargets().forEach(function (slot) {
      try {
        slot.chart.applyOptions({
          layout: { background: { type: 'solid', color: theme.surface }, textColor: theme.ink },
          grid: { vertLines: { visible: false, color: theme.grid }, horzLines: { visible: false, color: theme.grid } },
          rightPriceScale: { borderColor: theme.edge, minimumWidth: 84 },
          timeScale: { borderColor: theme.edge, textColor: theme.ink },
          crosshair: { vertLine: { labelBackgroundColor: '#2563eb' }, horzLine: { labelBackgroundColor: '#2563eb' } }
        });
        if (slot.series) {
          slot.series.applyOptions({
            upColor: theme.scheme === 'light' ? '#00846B' : '#26A69A',
            downColor: theme.scheme === 'light' ? '#C7334B' : '#EF5350',
            wickUpColor: theme.scheme === 'light' ? '#00846B' : '#26A69A',
            wickDownColor: theme.scheme === 'light' ? '#C7334B' : '#EF5350'
          });
        }
      } catch (err) {}
    });
    var legacy = document.getElementById('screen-theme');
    if (legacy && legacy.value !== kiteThemeKey) {
      legacy.value = kiteThemeKey;
      legacy.dispatchEvent(new Event('change', { bubbles: true }));
    }
    if (save !== false) {
      try { localStorage.setItem(multi ? 'multiLegScreenTheme' : 'mc325ScreenTheme', kiteThemeKey); } catch (err) {}
    }
  }
  function closeKiteSettingsPop() {
    var pop = document.getElementById('kiteSettingsPop');
    if (!pop || pop.hidden) return;
    var bar = pop.querySelector('.manual-trail-bar');
    if (bar) {
      bar.classList.remove('kite-settings-open');
      bar.hidden = true;
      var card = pop.dataset.cardId && document.getElementById(pop.dataset.cardId);
      var host = card && (card.querySelector('.manual-trail-group') || card);
      if (host) host.append(bar);
    }
    pop.hidden = true;
    pop.dataset.cardId = '';
  }
  function openTrailSettings(card) {
    if (!card) return;
    var bar = card.querySelector('.manual-trail-bar');
    if (!bar) return;
    closeKiteSettingsPop();
    var pop = document.getElementById('kiteSettingsPop');
    if (!pop) {
      pop = el('div', 'kiteSettingsPop');
      pop.hidden = true;
      pop.innerHTML = '<div class="kiteSettingsSheet" role="dialog" aria-label="Trail SL settings"><button type="button" class="kiteSettingsClose" aria-label="Close">✕</button><div class="kiteSettingsBody"></div></div>';
      document.body.append(pop);
      pop.querySelector('.kiteSettingsClose').onclick = closeKiteSettingsPop;
      pop.addEventListener('click', function (event) {
        if (event.target === pop) closeKiteSettingsPop();
      });
    }
    pop.dataset.cardId = card.id || '';
    if (!card.id) {
      card.id = 'kite-card-' + Math.random().toString(36).slice(2, 8);
      pop.dataset.cardId = card.id;
    }
    var body = pop.querySelector('.kiteSettingsBody');
    body.append(bar);
    bar.hidden = false;
    bar.classList.add('kite-settings-open');
    pop.hidden = false;
    dressTrail(card);
  }
  function openMtmSettings() {
    var multiOpen = document.getElementById('mtm-open');
    if (multiOpen) {
      multiOpen.click();
      return;
    }
    var dialog = document.querySelector('dialog.mtm-dialog');
    var hidden = document.querySelector('button.portfolio-mtm-button');
    if (hidden) {
      if (typeof hidden.onclick === 'function') {
        try {
          hidden.onclick.call(hidden, new Event('click'));
        } catch (err) {
          hidden.click();
        }
      } else hidden.click();
    }
    if (dialog && dialog.open) return;
    if (dialog && dialog.showModal) dialog.showModal();
  }
  function kiteChartSpan(width) {
    return Math.max(24, Math.min(96, Math.floor((width || 320) / 8)));
  }
  function kiteVisibleRange(last, span) {
    return { from: last - span, to: last + 1 };
  }
  function syncKitePriceScaleWidth() {
    var targets = chartTargets();
    var widest = 84;
    targets.forEach(function (slot) {
      try {
        var w = slot.chart.priceScale('right').width();
        if (w > widest) widest = w;
      } catch (err) {}
    });
    targets.forEach(function (slot) {
      try {
        slot.chart.applyOptions({ rightPriceScale: { minimumWidth: widest, borderVisible: true } });
      } catch (err) {}
    });
  }
  function applyKiteTimeScaleOptions(chart) {
    if (!chart) return;
    try {
      chart.timeScale().applyOptions({ rightOffset: 0, fixRightEdge: false, borderVisible: true });
    } catch (err) {}
  }
  function patchMc325CenterLatest(slot) {
    if (!slot || !slot.chart || !slot.series) return;
    if (slot.centerLatest && slot.centerLatest.__kiteTight) return;
    var chart = slot.chart;
    var series = slot.series;
    var tight = function (requestedSpan) {
      if (slot.follow === false) return;
      var last = series.data().length - 1;
      if (last < 0) return;
      var scale = chart.timeScale();
      var width = scale.width() || 320;
      var range = scale.getVisibleLogicalRange();
      var span = requestedSpan || (range && range.to > range.from ? range.to - range.from : kiteChartSpan(width));
      var next = kiteVisibleRange(last, span);
      applyKiteTimeScaleOptions(chart);
      if (!range || Math.abs(range.from - next.from) > 0.02 || Math.abs(range.to - next.to) > 0.02) {
        scale.setVisibleLogicalRange(next);
      }
    };
    tight.__kiteTight = true;
    slot.centerLatest = tight;
  }
  function wireMc325Charts(charts) {
    var map = charts || window.mc325Charts;
    if (!map) return;
    ['CE', 'REF', 'PE'].forEach(function (side) {
      var slot = map[side];
      if (!slot || !slot.chart) return;
      applyKiteTimeScaleOptions(slot.chart);
      patchMc325CenterLatest(slot);
    });
    syncKitePriceScaleWidth();
    fitKiteCharts();
  }
  function fitKiteCharts() {
    ['CE', 'REF', 'PE'].forEach(function (id) {
      var slot = window.mc325Charts && window.mc325Charts[id];
      if (!slot || !slot.chart || !slot.series) return;
      try {
        slot.follow = true;
        applyKiteTimeScaleOptions(slot.chart);
        slot.chart.priceScale('right').applyOptions({ autoScale: true });
        var rows = slot.series.data();
        var last = rows.length - 1;
        if (last < 0) return;
        var width = slot.chart.timeScale().width() || 320;
        var span = kiteChartSpan(width);
        slot.chart.timeScale().setVisibleLogicalRange(kiteVisibleRange(last, span));
      } catch (err) {}
    });
    var panes = window.shivMultiPanes;
    if (panes) {
      Object.keys(panes).forEach(function (key) {
        var pane = panes[key];
        if (!pane || !pane.card || pane.card.hidden || !pane.chart || !pane.series) return;
        try {
          pane.followLatest = true;
          applyKiteTimeScaleOptions(pane.chart);
          pane.chart.priceScale('right').applyOptions({ autoScale: true });
          var bars = pane.series.data();
          var last = bars.length - 1;
          if (last < 0) return;
          var host = pane.card.querySelector('.chart-pane');
          var width = pane.chart.timeScale().width() || (host && host.clientWidth) || pane.card.clientWidth || 320;
          var span = kiteChartSpan(width);
          pane.chart.timeScale().setVisibleLogicalRange(kiteVisibleRange(last, span));
        } catch (err) {}
      });
    }
    syncKitePriceScaleWidth();
  }
  window.addEventListener('mc325-chart-loaded', function (event) {
    wireMc325Charts(event.detail && event.detail.charts);
  });
  setTimeout(function () { wireMc325Charts(); }, 600);
  setTimeout(function () { wireMc325Charts(); }, 2200);
  function parkSummary() {
    var summary = document.getElementById('tradeSummary');
    if (!summary) {
      summary = document.createElement('section');
      summary.id = 'tradeSummary';
      summary.setAttribute('aria-label', 'Trades');
      positions.append(summary);
      if (window.shivBoard && window.shivBoard.mountSummary) window.shivBoard.mountSummary(summary);
      return;
    }
    if (summary.parentElement !== positions) positions.append(summary);
  }

  if (!multi) {
    var brokers = document.querySelector('.manual-brokers');
    if (brokers) brokers.hidden = true;
    var choices = document.querySelector('.chart-choices');
    if (choices) {
      var ceBtn = choices.querySelector('[data-chart="CE"]');
      var spotBtn = choices.querySelector('[data-chart="REF"]');
      var peBtn = choices.querySelector('[data-chart="PE"]');
      if (ceBtn && spotBtn && peBtn) {
        ceBtn.textContent = 'CALL';
        spotBtn.textContent = 'SPOT';
        peBtn.textContent = 'PUT';
        choices.append(ceBtn, spotBtn, peBtn);
      }
      move(choices, barCenter);
    }
    move(document.querySelector('.grid'), charts);
    window.mc325StrikeCE = 0;
    window.mc325StrikePE = 0;
    window.mc325SelectedStrike = 0;
    window.kiteHoldChartStrikes = true;
    function showAllChartPanels() {
      document.querySelectorAll('.panel.choice-hide, .panel.window-hidden, .panel.solo-hide').forEach(function (panel) {
        panel.classList.remove('choice-hide', 'window-hidden', 'solo-hide');
      });
      document.body.classList.remove('focus-ce', 'focus-pe', 'solo-chart');
    }
    showAllChartPanels();
    setTimeout(showAllChartPanels, 400);
    function applyCaptureChart(data) {
      if (!data || data.status !== 'OK' || !data.legs) return;
      window.kiteLastChart = data;
      ['CE', 'PE'].forEach(function (side) {
        var leg = data.legs[side];
        if (!leg || !(Number(leg.strike) > 0)) return;
        if (strikeLock[side]) return;
        var select = document.querySelector('.kiteStrike[data-side="' + side + '"]');
        strikeValue(select, leg.strike);
        if (Number(leg.ltp) > 0) rememberPrice(side, leg.ltp);
        else {
          var row = chainRows.find(function (item) { return String(item.strike) === String(leg.strike); });
          if (row && row[side] && Number(row[side].ltp) > 0) rememberPrice(side, row[side].ltp);
        }
      });
      if (window.kiteHoldChartStrikes) {
        if (data.legs.CE && Number(data.legs.CE.strike) > 0) window.mc325StrikeCE = Number(data.legs.CE.strike);
        if (data.legs.PE && Number(data.legs.PE.strike) > 0) window.mc325StrikePE = Number(data.legs.PE.strike);
        window.mc325SelectedStrike = 0;
        window.kiteHoldChartStrikes = false;
      }
      paintLimits();
      refreshMtmQuiet();
    }
    function kiteReloadChartsIfEmpty() {
      var ce = document.getElementById('ohlcCE');
      if (!ce || !/No data loaded/i.test(ce.textContent || '')) return;
      window.mc325StrikeCE = 0;
      window.mc325StrikePE = 0;
      window.mc325SelectedStrike = 0;
      window.kiteHoldChartStrikes = true;
      var expiry = document.getElementById('expirySelect');
      if (expiry) expiry.dispatchEvent(new Event('change', { bubbles: true }));
    }
    setTimeout(kiteReloadChartsIfEmpty, 2500);
    function parkCards() {
      move(document.querySelector('.order-card[data-side="CE"]'), call);
      move(document.querySelector('.order-card[data-side="PE"]'), put);
      var chain = document.getElementById('optionChainDialog');
      if (chain && chain.parentElement !== drawer) drawer.insertBefore(chain, drawer.firstChild);
      if (chain && chain.open) chain.close();
      parkSummary();
      dressTickets();
    }
    parkCards();
    window.addEventListener('mc325-chart-loaded', function (event) {
      parkCards();
      showAllChartPanels();
      setTimeout(sizeCharts, 30);
      setTimeout(sizeCharts, 300);
      setTimeout(fitKiteCharts, 80);
      setTimeout(fitKiteCharts, 450);
      applyCaptureChart(event.detail && event.detail.data);
      ['CE', 'PE'].forEach(function (side) {
        if (!strikeLock[side]) return;
        window['mc325Strike' + side] = Number(strikeLock[side]);
        var select = document.querySelector('.kiteStrike[data-side="' + side + '"]');
        if (select) ensureOption(select, strikeLock[side]);
      });
    });
    paintTicketPnl();
    document.querySelectorAll('.manual-pnl-summary').forEach(function (node) {
      new MutationObserver(paintTicketPnl).observe(node, { attributes: true, attributeFilter: ['data-running'] });
    });
    setInterval(paintTicketPnl, 1000);
    var fitted = 0;
    function fitCharts() {
      ['CE', 'REF', 'PE'].forEach(function (id) {
        var node = document.getElementById('chart' + id);
        var slot = window.mc325Charts && window.mc325Charts[id];
        if (!node || !slot || !slot.chart) return;
        if (node.closest('.panel') && node.closest('.panel').classList.contains('choice-hide')) return;
        var height = node.clientHeight;
        var width = node.clientWidth;
        if (height < 40 || width < 40) return;
        try {
          slot.chart.resize(width, height);
          fitted += 1;
        } catch (err) {}
      });
      if (fitted < 8) fitKiteCharts();
    }
    function sizeCharts() {
      var host = document.getElementById('kiteCharts');
      if (!host || host.clientHeight < 80) return;
      var grid = host.querySelector('.grid, #charts');
      if (grid) {
        grid.style.setProperty('height', host.clientHeight + 'px', 'important');
        grid.style.setProperty('min-height', host.clientHeight + 'px', 'important');
      }
      host.querySelectorAll('.panel, .chart-card').forEach(function (panel) {
        panel.style.setProperty('height', host.clientHeight + 'px', 'important');
      });
      host.querySelectorAll('.chart').forEach(function (node) {
        node.style.setProperty('height', Math.max(160, host.clientHeight - 4) + 'px', 'important');
      });
      fitCharts();
    }
    window.addEventListener('resize', function () { requestAnimationFrame(sizeCharts); });
    setTimeout(sizeCharts, 50);
    setTimeout(sizeCharts, 400);
    setTimeout(sizeCharts, 1200);
    if (window.ResizeObserver) new ResizeObserver(function () { requestAnimationFrame(sizeCharts); }).observe(charts);
  } else {
    move(document.getElementById('nav-spots'), quotes);
    var pills = el('div', 'kitePills');
    ['chart-side-ce', 'chart-side-spot', 'chart-side-pe'].forEach(function (id) {
      var input = document.getElementById(id);
      if (!input || !input.parentElement) return;
      var word = input.parentElement.querySelector('.kiteWord');
      if (!word) {
        word = document.createElement('span');
        word.className = 'kiteWord';
        input.parentElement.append(word);
      }
      word.textContent = id === 'chart-side-ce' ? 'CALL' : id === 'chart-side-pe' ? 'PUT' : 'SPOT';
      pills.append(input.parentElement);
    });
    barCenter.append(pills);
    var chartHost = document.getElementById('charts');
    move(chartHost, charts);
    var ceAside = document.getElementById('ce-strikes') && document.getElementById('ce-strikes').closest('aside');
    var peAside = document.getElementById('pe-strikes') && document.getElementById('pe-strikes').closest('aside');
    move(ceAside, call);
    move(document.getElementById('centre-pnl'), pnl);
    paintTicketPnl();
    var runningPnl = document.getElementById('pnl-running');
    if (runningPnl) new MutationObserver(paintTicketPnl).observe(runningPnl, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['data-sign'] });
    setInterval(paintTicketPnl, 1000);
    move(peAside, put);
    var workspace = document.getElementById('workspace');
    if (workspace) workspace.hidden = true;
    function showThree() {
      var count = document.getElementById('view-count');
      var sides = ['chart-side-ce', 'chart-side-spot', 'chart-side-pe'];
      if (count && count.value !== '3') {
        count.value = '3';
        if (typeof count.onchange === 'function') count.onchange();
      }
      sides.forEach(function (id) {
        var input = document.getElementById(id);
        if (input && !input.checked) {
          input.checked = true;
          if (typeof input.onchange === 'function') input.onchange();
        }
      });
    }
    var orderChartsLock = false;
    function orderCharts() {
      if (orderChartsLock) return;
      var host = document.getElementById('charts');
      if (!host) return;
      var cards = Array.prototype.slice.call(host.children);
      function rank(card) {
        if (card.hidden) return 9;
        var text = (card.querySelector('.chart-contract-label') || {}).textContent || '';
        if (/\bPE\b/.test(text)) return 2;
        if (/\bCE\b/.test(text)) return 0;
        if (/SPOT/.test(text)) return 1;
        return 5;
      }
      var sorted = cards.slice().sort(function (a, b) { return rank(a) - rank(b); });
      var same = sorted.every(function (card, index) { return card === cards[index]; });
      if (!same) {
        orderChartsLock = true;
        try {
          sorted.forEach(function (card) { host.append(card); });
        } finally {
          orderChartsLock = false;
        }
      }
    }
    try { showThree(); } catch (err) {}
    setTimeout(function () { try { showThree(); orderCharts(); } catch (err) {} }, 400);
    setTimeout(function () { try { showThree(); orderCharts(); } catch (err) {} }, 1500);
    setTimeout(fitKiteCharts, 900);
    setTimeout(fitKiteCharts, 2400);
    setTimeout(orderCharts, 1200);
    if (chartHost) {
      new MutationObserver(function () {
        if (orderChartsLock) return;
        orderCharts();
      }).observe(chartHost, { childList: true });
    }
    parkSummary();
    var chainDialog = document.getElementById('chain-dialog');
    if (chainDialog && chainDialog.parentElement !== drawer) drawer.insertBefore(chainDialog, drawer.firstChild);
  }

  function mirrorQuotes() {
    if (document.getElementById('nav-spots')) return;
    [['NIFTY', 'shellNiftyLiveSpot', 'shellNiftyLiveChange'], ['SENSEX', 'shellSensexLiveSpot', 'shellSensexLiveChange']].forEach(function (spec) {
      var price = document.getElementById(spec[1]);
      var change = document.getElementById(spec[2]);
      if (!price || !change) return;
      var box = el('span', '', 'kiteQuote');
      var name = el('span');
      name.textContent = spec[0];
      var value = el('b');
      var delta = el('small');
      box.append(name, value, delta);
      quotes.append(box);
      function pull() {
        value.textContent = price.textContent || '—';
        delta.textContent = change.textContent || '';
        var cls = change.className || '';
        var text = (change.textContent || '').trim();
        var sign = cls.indexOf('red') >= 0 || text.charAt(0) === '-' ? 'down' : (cls.indexOf('green') >= 0 || text.charAt(0) === '+' ? 'up' : '');
        value.dataset.sign = sign;
        delta.dataset.sign = sign;
      }
      pull();
      new MutationObserver(pull).observe(price, { childList: true, characterData: true, subtree: true, attributes: true });
      new MutationObserver(pull).observe(change, { childList: true, characterData: true, subtree: true, attributes: true });
    });
  }
  mirrorQuotes();

  function paintFunds(rows) {
    balanceValue.replaceChildren();
    [['kite_main', 'Zerodha'], ['angelone_main', 'Angel One']].forEach(function (spec) {
      var row = (rows || []).find(function (item) {
        return item.account_id === spec[0] || (spec[0] === 'angelone_main' && item.broker === 'angelone' && item.status === 'OK');
      });
      var line = document.createElement('div');
      var amount = row && row.funds ? row.funds.live_balance : null;
      line.textContent = spec[1] + ' ' + (row && row.status === 'OK' && amount != null ? Number(amount).toLocaleString('en-IN', { style: 'currency', currency: 'INR' }) : '—');
      balanceValue.append(line);
    });
  }
  var margin = document.getElementById('shellRealMarginTop');
  if (margin) {
    function pullMargin() {
      var lines = margin.querySelectorAll('div');
      if (!lines.length) {
        balanceValue.textContent = margin.textContent || '—';
        return;
      }
      balanceValue.replaceChildren();
      lines.forEach(function (line) {
        var copy = document.createElement('div');
        copy.textContent = (line.textContent || '').replace(/CF\d+|K\d+/g, '').replace(/\s+/g, ' ').trim();
        balanceValue.append(copy);
      });
    }
    pullMargin();
    new MutationObserver(pullMargin).observe(margin, { childList: true, characterData: true, subtree: true });
  } else {
    function loadFunds() {
      fetch('/funds/all', { credentials: 'same-origin', cache: 'no-store' }).then(function (res) {
        return res.ok ? res.json() : null;
      }).then(function (data) {
        if (data) paintFunds(data.accounts || []);
      }).catch(function () {});
    }
    loadFunds();
    setInterval(loadFunds, 30000);
  }

  var toolOrder = ['Cursor', 'Trend line', 'Horizontal line', 'Vertical line', 'Text', 'Delete selected drawing', 'Clear custom drawings'];
  function buildDrawRail() {
    var bars = document.querySelectorAll('.chart-draw-tools');
    if (!bars.length || draw.dataset.ready === '1') return;
    var sources = Array.prototype.slice.call(bars[0].querySelectorAll('button'));
    if (!sources.length) return;
    draw.dataset.ready = '1';
    toolOrder.forEach(function (name) {
      var source = sources.find(function (button) { return (button.title || '').indexOf(name) === 0; });
      if (!source) return;
      var index = sources.indexOf(source);
      var button = document.createElement('button');
      button.type = 'button';
      button.textContent = source.textContent;
      button.title = (source.title || '').replace(/^(CE|PE|REF|SPOT)\s+/i, '');
      button.setAttribute('aria-label', button.title || 'Drawing tool');
      button.onclick = function () {
        document.querySelectorAll('.chart-draw-tools').forEach(function (host) {
          var peer = host.querySelectorAll('button')[index];
          if (peer) peer.click();
        });
        syncDraw();
      };
      draw.append(button);
      var side = button.cloneNode(true);
      side.onclick = button.onclick;
      drawSide.append(side);
    });
  }
  function syncDraw() {
    var host = document.querySelector('.chart-draw-tools');
    if (!host) return;
    var sources = host.querySelectorAll('button');
    [draw, drawSide].forEach(function (hostBar) {
      hostBar.querySelectorAll('button').forEach(function (button) {
        var source = Array.prototype.find.call(sources, function (item) {
          return (item.title || '').indexOf(button.title) === 0 || button.title.indexOf((item.title || '').replace(/^(CE|PE|REF|SPOT)\s+/i, '')) === 0;
        });
        if (source) button.setAttribute('aria-pressed', source.getAttribute('aria-pressed') || 'false');
      });
    });
  }
  buildDrawRail();
  function parkTradeSummary() {
    var summary = document.getElementById('tradeSummary');
    if (summary && summary.parentElement !== positions) positions.append(summary);
  }
  parkTradeSummary();
  window.addEventListener('mc325-chart-loaded', parkTradeSummary);

  var gear = document.createElement('button');
  gear.type = 'button';
  gear.className = 'kiteIcon';
  gear.title = 'Line settings';
  gear.setAttribute('aria-label', 'Line settings');
  gear.append(svg('<circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 3.5v2.2M12 18.3V21M3.5 12h2.2M18.3 12H21M5.8 5.8l1.5 1.5M16.7 16.7l1.5 1.5M18.2 5.8l-1.5 1.5M7.3 16.7l-1.5 1.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'));
  gear.onclick = function () {
    var open = document.querySelectorAll('.drawing-editor:not([hidden])');
    open.forEach(function (editor) { editor.hidden = true; });
    gear.setAttribute('aria-pressed', 'false');
  };
  var framePop = el('div', '', 'kitePop');
  var chip = document.createElement('button');
  chip.type = 'button';
  chip.className = 'kiteFrame';
  chip.title = 'Timeframe';
  chip.setAttribute('aria-haspopup', 'menu');
  chip.setAttribute('aria-label', 'Timeframe');
  var frameMenu = el('div', '', 'kiteMenu');
  frameMenu.hidden = true;
  frameMenu.setAttribute('role', 'menu');
  framePop.append(chip, frameMenu);
  function frameLabel() {
    var minutes = document.getElementById('minutes');
    var chosen = minutes && minutes.selectedOptions && minutes.selectedOptions[0];
    chip.textContent = minutes && minutes.value ? minutes.value + 'm' : '—';
    chip.title = chosen ? chosen.textContent : 'Timeframe';
  }
  function buildFrameMenu() {
    var minutes = document.getElementById('minutes');
    frameMenu.replaceChildren();
    if (!minutes) return;
    Array.prototype.forEach.call(minutes.options, function (option) {
      var item = document.createElement('button');
      item.type = 'button';
      item.setAttribute('role', 'menuitemradio');
      item.textContent = option.textContent;
      item.setAttribute('aria-checked', String(option.value === minutes.value));
      item.onclick = function (event) {
        event.stopPropagation();
        minutes.value = option.value;
        minutes.dispatchEvent(new Event('change', { bubbles: true }));
        frameLabel();
        frameMenu.hidden = true;
        chip.setAttribute('aria-expanded', 'false');
      };
      frameMenu.append(item);
    });
  }
  chip.onclick = function (event) {
    event.stopPropagation();
    buildFrameMenu();
    frameMenu.hidden = !frameMenu.hidden;
    chip.setAttribute('aria-expanded', String(!frameMenu.hidden));
  };
  frameLabel();
  var minutesNode = document.getElementById('minutes');
  if (minutesNode) minutesNode.addEventListener('change', frameLabel);
  document.addEventListener('click', function () {
    frameMenu.hidden = true;
    chip.setAttribute('aria-expanded', 'false');
  });
  var layouts = el('div', '', 'kiteLayouts');
  layouts.setAttribute('aria-label', 'Chart layout');
  [1, 2, 3].forEach(function (count) {
    var button = document.createElement('button');
    button.type = 'button';
    button.dataset.layout = String(count);
    button.title = count + ' chart' + (count === 1 ? '' : 's');
    button.setAttribute('aria-label', button.title);
    button.append(svg(count === 1
      ? '<rect x="4" y="5" width="16" height="14" fill="none" stroke="currentColor" stroke-width="1.6"/>'
      : count === 2
        ? '<rect x="3" y="5" width="8" height="14" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="13" y="5" width="8" height="14" fill="none" stroke="currentColor" stroke-width="1.6"/>'
        : '<rect x="3" y="5" width="5" height="14" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="9.5" y="5" width="5" height="14" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="16" y="5" width="5" height="14" fill="none" stroke="currentColor" stroke-width="1.6"/>'));
    button.onclick = function () { setLayout(count); };
    layouts.append(button);
  });
  var theme = el('div', '', 'kiteTheme');
    var themeButton = document.createElement('button');
    themeButton.type = 'button';
    themeButton.setAttribute('aria-label', 'Screen theme');
    themeButton.setAttribute('aria-haspopup', 'menu');
    themeButton.append(svg('<circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 3.5v2.2M12 18.3V21M3.5 12h2.2M18.3 12H21M6 6l1.6 1.6M16.4 16.4 18 18M18 6l-1.6 1.6M7.6 16.4 6 18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'));
    var themeMenu = el('div', '', 'kiteMenu screen-theme-menu');
    themeMenu.hidden = true;
    themeMenu.setAttribute('role', 'menu');
    function paintThemeMenu(active) {
      themeMenu.replaceChildren();
      var themeSelect = document.getElementById('screen-theme');
      var entries = [];
      if (themeSelect && themeSelect.options.length) {
        Array.prototype.forEach.call(themeSelect.options, function (option) {
          entries.push({ key: option.value, name: option.textContent });
        });
      } else {
        Object.keys(KITE_SCREEN_THEMES).forEach(function (key) {
          entries.push({ key: key, name: KITE_SCREEN_THEMES[key].name });
        });
      }
      entries.forEach(function (entry) {
        var item = document.createElement('button');
        item.type = 'button';
        item.setAttribute('role', 'menuitemradio');
        item.textContent = entry.name;
        item.setAttribute('aria-checked', String(entry.key === active));
        item.onclick = function (event) {
          event.stopPropagation();
          applyKiteScreenTheme(entry.key, true);
          paintThemeMenu(entry.key);
          themeMenu.hidden = true;
          themeButton.setAttribute('aria-expanded', 'false');
        };
        themeMenu.append(item);
      });
    }
    themeButton.onclick = function (event) {
      event.stopPropagation();
      closeKiteSettingsPop();
      var opening = themeMenu.hidden;
      paintThemeMenu(kiteThemeKey);
      themeMenu.hidden = !opening;
      themeButton.setAttribute('aria-expanded', String(!themeMenu.hidden));
    };
    theme.append(themeButton, themeMenu);
  document.addEventListener('click', function (event) {
    if (!theme.contains(event.target)) {
      themeMenu.hidden = true;
      themeButton.setAttribute('aria-expanded', 'false');
    }
  });
  var savedTheme = 'normal';
  try { savedTheme = localStorage.getItem(multi ? 'multiLegScreenTheme' : 'mc325ScreenTheme') || 'normal'; } catch (err) {}
  applyKiteScreenTheme(savedTheme, false);
  paintThemeMenu(kiteThemeKey);
  barLeft.insertBefore(framePop, draw);
  barLeft.append(gear);
  barRight.append(theme, layouts);
  function markLayout(count) {
    layouts.querySelectorAll('button').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.layout === String(count)));
    });
  }
  function setLayout(count) {
    document.body.classList.toggle('kite-layout-1', count === 1);
    var view = document.getElementById('view-count');
    if (view) {
      document.body.classList.remove('kite-layout-1');
      var allowed = Array.prototype.some.call(view.options, function (option) { return option.value === String(count); });
      if (allowed && view.value !== String(count)) {
        view.value = String(count);
        if (typeof view.onchange === 'function') view.onchange();
      }
      markLayout(count);
      return;
    }
    var ce = document.querySelector('.chart-choices [data-chart="CE"]');
    var spot = document.querySelector('.chart-choices [data-chart="REF"]');
    var focused = document.body.classList.contains('focus-ce') || document.body.classList.contains('focus-pe');
    if (count === 3 && spot) spot.click();
    else if (!focused && ce) ce.click();
    markLayout(count);
    window.dispatchEvent(new Event('resize'));
  }
  markLayout(3);

  function railButton(label, glyph, mode) {
    var button = document.createElement('button');
    button.type = 'button';
    button.title = label;
    button.setAttribute('aria-label', label);
    button.dataset.mode = mode;
    button.append(svg(glyph));
    var caption = document.createElement('span');
    caption.textContent = label;
    button.append(caption);
    button.onclick = function () { setDrawer(mode); };
    rail.append(button);
    return button;
  }
  railButton('Positions', '<path d="M9 7V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="4" y="7" width="16" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M4 12h16" fill="none" stroke="currentColor" stroke-width="1.6"/>', 'positions');
  railButton('Orders', '<path d="M7 4h10a1 1 0 0 1 1 1v15l-2.2-1.4L13.5 20l-2.3-1.4L9 20l-2.2-1.4L4.5 20V5a1 1 0 0 1 1-1z" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 8h8M8 12h8M8 16h5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>', 'orders');
  railButton('Market Depth', '<path d="M5 18V10M10 18V6M15 18v-5M20 18V8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>', 'depth');
  railButton('Option Chain', '<path d="M9 7h11M9 12h11M9 17h11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M4.5 7h.01M4.5 12h.01M4.5 17h.01" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/>', 'chain');
  railButton('Order Presets', '<path d="M12 4.5l1.6 3.3 3.6.5-2.6 2.5.6 3.6L12 12.7 8.8 14.4l.6-3.6L6.8 8.3l3.6-.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>', 'presets');

  function closeChain() {
    chainPop.hidden = true;
    var button = rail.querySelector('[data-mode="chain"]');
    if (button) button.setAttribute('aria-pressed', 'false');
  }
  function openChain() {
    var show = chainPop.hidden;
    chainPop.hidden = !show;
    var button = rail.querySelector('[data-mode="chain"]');
    if (button) button.setAttribute('aria-pressed', String(show));
    if (show) loadStrikes();
  }
  function setDrawer(mode) {
    if (mode === 'chain') {
      openChain();
      return;
    }
    closeChain();
    var open = drawer.dataset.mode === mode;
    drawer.dataset.mode = open ? '' : mode;
    drawer.hidden = !drawer.dataset.mode;
    drawer.classList.toggle('open', !!drawer.dataset.mode);
    rail.querySelectorAll('button').forEach(function (button) {
      var pressed = button.dataset.mode === 'chain' ? !chainPop.hidden : button.dataset.mode === drawer.dataset.mode;
      button.setAttribute('aria-pressed', String(pressed));
    });
    if (drawer.dataset.mode === 'positions') parkSummary();
    if (drawer.dataset.mode === 'orders') loadOrders();
    if (drawer.dataset.mode === 'depth') loadDepth();
    if (drawer.dataset.mode === 'presets') loadPresets();
  }
  function panelNote(host, text) {
    host.replaceChildren();
    var note = document.createElement('p');
    note.className = 'kiteChainEmpty';
    note.textContent = text;
    host.append(note);
  }
  function loadOrders() {
    fetch('/orders/all', { credentials: 'same-origin', cache: 'no-store' }).then(function (res) {
      return res.ok ? res.json() : null;
    }).then(function (data) {
      var rows = [];
      ((data && data.accounts) || []).forEach(function (account) {
        (account.orders || []).forEach(function (order) {
          rows.push({
            broker: account.broker_name || account.account_name || account.broker || '',
            instrument: order.instrument || '',
            side: order.side || '',
            qty: order.qty != null ? order.qty : '',
            price: order.avg != null ? order.avg : order.price,
            status: order.status || ''
          });
        });
      });
      if (!rows.length) {
        panelNote(ordersHost, 'The broker returned no orders.');
        return;
      }
      var table = document.createElement('table');
      table.className = 'kiteChainTable';
      var head = document.createElement('tr');
      ['Broker', 'Contract', 'Side', 'Qty', 'Price', 'Status'].forEach(function (label) {
        var th = document.createElement('th');
        th.textContent = label;
        head.append(th);
      });
      table.append(head);
      rows.forEach(function (row) {
        var tr = document.createElement('tr');
        [row.broker, row.instrument, row.side, row.qty, row.price, row.status].forEach(function (value) {
          var td = document.createElement('td');
          td.textContent = value == null || value === '' ? '—' : String(value);
          tr.append(td);
        });
        table.append(tr);
      });
      ordersHost.replaceChildren(table);
    }).catch(function () {
      panelNote(ordersHost, 'The broker returned no orders.');
    });
  }
  function loadDepth() {
    panelNote(depthHost, 'The broker quote on this page does not include market depth.');
  }
  function loadPresets() {
    panelNote(presetsHost, 'The broker returned no order presets.');
  }

  function strikeText(value) {
    var n = Number(value);
    return Number.isFinite(n) ? n.toLocaleString('en-IN') : String(value);
  }
  function strikeValue(node, value) {
    if (!node) return '';
    if (arguments.length < 2) return node.dataset.value || node.value || '';
    var next = value == null ? '' : String(value);
    node.dataset.value = next;
    try { node.value = next; } catch (err) {}
    paintStrikeFace(node);
    return next;
  }
  function paintStrikeFace(button) {
    if (!button) return;
    var side = button.dataset.side === 'PE' ? 'PE' : 'CE';
    var value = strikeValue(button);
    button.textContent = Number(value) > 0 ? strikeText(value) + ' ' + side : 'Strike';
  }
  function closeStrikeMenus() {
    document.querySelectorAll('.kiteStrikeMenu').forEach(function (menu) {
      menu.hidden = true;
    });
    document.querySelectorAll('.kiteStrike').forEach(function (button) {
      button.setAttribute('aria-expanded', 'false');
    });
  }
  function strikeButton(menu) {
    return menu.kiteButton || null;
  }
  function placeStrikeMenu(menu, button) {
    if (!menu || !button) return;
    if (menu.parentElement !== document.body) document.body.append(menu);
    var rect = button.getBoundingClientRect();
    var width = Math.min(460, window.innerWidth - 16);
    var left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
    menu.style.setProperty('position', 'fixed', 'important');
    menu.style.setProperty('width', width + 'px', 'important');
    menu.style.setProperty('left', left + 'px', 'important');
    menu.style.setProperty('right', 'auto', 'important');
    menu.style.setProperty('bottom', 'auto', 'important');
    menu.style.setProperty('z-index', '400', 'important');
    var maxH = Math.max(180, Math.min(420, rect.top - 12));
    menu.style.setProperty('max-height', maxH + 'px', 'important');
    var height = menu.offsetHeight || maxH;
    var top = rect.top - 6 - height;
    if (top < 8) top = Math.min(window.innerHeight - height - 8, rect.bottom + 6);
    menu.style.setProperty('top', Math.max(8, top) + 'px', 'important');
  }
  function paintStrikeMenu(menu, button) {
    var side = button.dataset.side === 'PE' ? 'PE' : 'CE';
    menu.replaceChildren();
    var pack = expiryList(lastChain || {});
    var currentExpiry = chainExpiry || pack.current || '';
    if (pack.list.length) {
      var tabs = document.createElement('div');
      tabs.className = 'kiteStrikeExpiries';
      pack.list.forEach(function (iso) {
        var tab = document.createElement('button');
        tab.type = 'button';
        tab.textContent = expiryLabel(iso, pack.list);
        if (iso === currentExpiry) tab.className = 'is-on';
        tab.onclick = function (event) {
          event.stopPropagation();
          chainExpiry = iso;
          loadStrikes(iso);
        };
        tabs.append(tab);
      });
      menu.append(tabs);
    }
    var rows = chainRows.filter(function (row) {
      return row && row[side] && Number(row.strike) > 0;
    }).sort(function (a, b) { return Number(a.strike) - Number(b.strike); });
    if (!rows.length) {
      var empty = document.createElement('p');
      empty.className = 'kiteStrikeEmpty';
      empty.textContent = lastChain ? 'The broker option chain is empty.' : 'Loading the broker option chain…';
      menu.append(empty);
      return;
    }
    var table = document.createElement('table');
    table.className = 'kiteStrikeTable';
    var head = document.createElement('tr');
    ['Strike', 'LTP', 'Chg %', 'OI'].forEach(function (name) {
      var th = document.createElement('th');
      th.textContent = name;
      head.append(th);
    });
    table.append(head);
    var spot = Number(lastChain && lastChain.spot);
    var placed = false;
    rows.forEach(function (row, index) {
      var leg = row[side] || {};
      var tr = document.createElement('tr');
      if (String(row.strike) === strikeValue(button)) tr.className = 'is-on';
      function cell(text, cls) {
        var td = document.createElement('td');
        td.textContent = text;
        if (cls) td.className = cls;
        tr.append(td);
      }
      cell(strikeText(row.strike) + ' ' + side, 'strike ' + side.toLowerCase());
      cell(chainPrice(leg.ltp), 'ltp ' + side.toLowerCase());
      var change = Number(leg.change_percent);
      cell(Number.isFinite(change) ? (change > 0 ? '+' : '') + change.toFixed(2) + '%' : '—', Number.isFinite(change) ? (change > 0 ? 'up' : change < 0 ? 'down' : '') : '');
      cell(leg.oi == null || leg.oi === '' ? '—' : oiText(leg.oi), '');
      tr.onclick = function (event) {
        event.stopPropagation();
        strikeLock[side] = String(row.strike);
        strikeValue(button, row.strike);
        rememberPrice(side, leg.ltp);
        menu.hidden = true;
        button.setAttribute('aria-expanded', 'false');
        onStrike(side, row.strike);
      };
      table.append(tr);
      var next = rows[index + 1];
      if (!placed && Number.isFinite(spot) && next && spot >= Number(row.strike) && spot < Number(next.strike)) {
        var spotRow = document.createElement('tr');
        spotRow.className = 'kiteSpotRow';
        var spotCell = document.createElement('td');
        spotCell.colSpan = 4;
        var pill = document.createElement('span');
        pill.className = 'kiteSpot';
        pill.textContent = spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        spotCell.append(pill);
        spotRow.append(spotCell);
        table.append(spotRow);
        placed = true;
      }
    });
    menu.append(table);
    var current = menu.querySelector('tr.is-on');
    if (current) menu.scrollTop = Math.max(0, current.offsetTop - 80);
  }
  function strikeControl(side) {
    var wrap = document.createElement('div');
    wrap.className = 'kiteStrikePop';
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'kiteStrike';
    button.dataset.side = side;
    button.dataset.value = '';
    button.setAttribute('aria-haspopup', 'listbox');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-label', (side === 'CE' ? 'Call' : 'Put') + ' strike');
    var menu = document.createElement('div');
    menu.className = 'kiteStrikeMenu';
    menu.hidden = true;
    menu.kiteButton = button;
    menu.addEventListener('click', function (event) { event.stopPropagation(); });
    button.addEventListener('click', function (event) {
      event.preventDefault();
      event.stopPropagation();
      var opening = menu.hidden;
      closeStrikeMenus();
      if (!opening) return;
      menu.hidden = false;
      button.setAttribute('aria-expanded', 'true');
      paintStrikeMenu(menu, button);
      placeStrikeMenu(menu, button);
      if (!chainRows.length) loadStrikes();
    });
    wrap.append(button, menu);
    paintStrikeFace(button);
    return wrap;
  }
  function ensureOption(select, strike) {
    if (!select || !(Number(strike) > 0)) return;
    strikeValue(select, strike);
  }
  function fillStrikes(rows) {
    chainRows = rows || [];
    document.querySelectorAll('.kiteStrike').forEach(paintStrikeFace);
    document.querySelectorAll('.kiteStrikeMenu').forEach(function (menu) {
      if (menu.hidden) return;
      var button = strikeButton(menu);
      if (!button) return;
      paintStrikeMenu(menu, button);
      placeStrikeMenu(menu, button);
    });
  }
  function priceText(value) {
    var n = Number(value);
    return n > 0 ? n.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—';
  }
  function ticketHost(side) {
    return side === 'CE' ? call : put;
  }
  function parseKitePrice(text) {
    var n = Number(String(text || '').replace(/[^\d.]/g, ''));
    return Number.isFinite(n) && n > 0 ? n : 0;
  }
  function nativeEntryControls(card) {
    if (!card) return null;
    var box = card.querySelector('.entry-options');
    if (!box) return null;
    var select = box.querySelector('select');
    var inputs = box.querySelectorAll('input');
    return { select: select, trigger: inputs[0] || null, price: inputs[1] || null };
  }
  function applyKiteEntryMode(host) {
    if (!host) return;
    var mode = host.querySelector('.kiteOrderType');
    var price = host.querySelector('.kiteLimitPrice');
    var limit = mode && mode.value !== 'MARKET';
    if (price) {
      price.disabled = !limit;
      price.classList.toggle('is-disabled', !limit);
      price.toggleAttribute('hidden', !limit);
    }
    var card = host.querySelector('.order-card, .exec');
    if (card) card.dataset.kiteEntryType = limit ? 'LIMIT' : 'MARKET';
  }
  function syncKiteEntryToNative(host) {
    if (!host) return;
    var card = host.querySelector('.order-card, .exec');
    if (!card) return;
    var mode = host.querySelector('.kiteOrderType');
    var priceInput = host.querySelector('.kiteLimitPrice');
    var isMarket = mode && mode.value === 'MARKET';
    card.dataset.kiteEntryType = isMarket ? 'MARKET' : 'LIMIT';
    var native = nativeEntryControls(card);
    if (!native || !native.select) return;
    if (isMarket) {
      native.select.value = 'MARKET';
      if (native.trigger) native.trigger.value = '';
      if (native.price) native.price.value = '';
    } else {
      native.select.value = 'SL_LIMIT';
      var amount = parseKitePrice(priceInput && priceInput.value);
      if (amount > 0) {
        if (native.price) native.price.value = String(amount);
        if (native.trigger) native.trigger.value = String(amount);
      }
    }
    native.select.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function ensureKiteEntryControls(host, side) {
    var limit = host.querySelector('.kiteLimit');
    if (!limit) return;
    if (!limit.querySelector('.kiteOrderType')) {
      var mode = document.createElement('select');
      mode.className = 'kiteOrderType';
      mode.setAttribute('aria-label', side + ' order type');
      mode.innerHTML = '<option value="MARKET">Market</option><option value="LIMIT">Limit</option>';
      mode.value = 'LIMIT';
      limit.replaceChildren(mode);
      var price = document.createElement('input');
      price.type = 'text';
      price.inputMode = 'decimal';
      price.className = 'kiteLimitPrice';
      price.setAttribute('aria-label', side + ' limit price');
      price.placeholder = '—';
      price.addEventListener('input', function () { price.dataset.userEdited = '1'; });
      limit.append(price);
      mode.addEventListener('change', function () {
        applyKiteEntryMode(host);
        syncKiteEntryToNative(host);
      });
    }
    var price = host.querySelector('.kiteLimitPrice');
    if (price && price.tagName === 'B') {
      var input = document.createElement('input');
      input.type = 'text';
      input.inputMode = 'decimal';
      input.className = 'kiteLimitPrice';
      input.setAttribute('aria-label', side + ' limit price');
      input.placeholder = '—';
      input.value = (price.textContent || '').trim() === '—' ? '' : (price.textContent || '').trim();
      input.addEventListener('input', function () { input.dataset.userEdited = '1'; });
      price.replaceWith(input);
    }
    applyKiteEntryMode(host);
  }
  function hookKiteEntryButtons(host) {
    if (!host || host.dataset.kiteEntryHook === '1') return;
    host.dataset.kiteEntryHook = '1';
    host.querySelectorAll('.manual-buy, .manual-sell, .buy, .sell').forEach(function (button) {
      button.addEventListener('click', function () {
        syncKiteEntryToNative(host);
      }, true);
    });
  }
  function rememberPrice(side, ltp) {
    var price = ticketHost(side).querySelector('.kiteLimitPrice');
    if (!price || !(Number(ltp) > 0) || price.dataset.userEdited === '1') return;
    var text = priceText(ltp);
    price.dataset.chain = text;
    if (price.tagName === 'INPUT') {
      if (price.value !== text) price.value = text;
    } else setText(price, text);
  }
  function chooseChain(side, row) {
    if (!row || !row[side]) return;
    var select = document.querySelector('.kiteStrike[data-side="' + side + '"]');
    if (!select) return;
    strikeValue(select, row.strike);
    rememberPrice(side, row[side].ltp);
    onStrike(side, row.strike);
  }
  function expiryLabel(value, list) {
    var iso = String(value || '').slice(0, 10);
    var parts = iso.split('-');
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var month = months[Number(parts[1]) - 1];
    if (parts.length !== 3 || !month || !parts[2]) return String(value || '');
    var base = String(Number(parts[2])) + ' ' + month + ' ' + parts[0];
    if (!list || !list.length) return base;
    var monthKey = iso.slice(0, 7);
    var last = '';
    list.forEach(function (item) {
      var day = String(item || '').slice(0, 10);
      if (day.slice(0, 7) === monthKey && day > last) last = day;
    });
    return last && iso !== last ? base + ' W' : base;
  }
  window.shivExpiryLabel = expiryLabel;
  function expiryList(data) {
    var list = [];
    var raw = data && Array.isArray(data.expiries) ? data.expiries : [];
    raw.forEach(function (value) {
      var iso = String(value || '').slice(0, 10);
      if (/^\d{4}-\d{2}-\d{2}$/.test(iso) && list.indexOf(iso) < 0) list.push(iso);
    });
    var current = data && data.expiry ? String(data.expiry).slice(0, 10) : '';
    if (current && list.indexOf(current) < 0) list.unshift(current);
    return { list: list, current: current && list.indexOf(current) >= 0 ? current : (list[0] || '') };
  }
  function fillExpirySelect(select, list, current) {
    if (!select || !list.length) return;
    var keep = select.value;
    select.replaceChildren();
    list.forEach(function (value) {
      select.add(new Option(expiryLabel(value, list), value));
    });
    if (current && list.indexOf(current) >= 0) select.value = current;
    else if (keep && list.indexOf(keep) >= 0) select.value = keep;
    else select.value = list[0];
  }
  var lastChain = null;
  var chainExpiry = '';
  var chainView = 'all';
  var oiSeen = {};
  function chainPrice(value) {
    var n = Number(value);
    return Number.isFinite(n) && n > 0 ? n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
  }
  function oiText(value) {
    var n = Number(value);
    if (!Number.isFinite(n)) return '—';
    var abs = Math.abs(n);
    var sign = n < 0 ? '-' : '';
    if (abs >= 10000000) return sign + (abs / 10000000).toFixed(2) + ' Cr';
    if (abs >= 100000) return sign + (abs / 100000).toFixed(2) + ' L';
    return n.toLocaleString('en-IN');
  }
  function oiTone(key, value) {
    var n = Number(value);
    if (!Number.isFinite(n)) return '';
    var prev = oiSeen[key];
    if (!prev) {
      oiSeen[key] = { value: n, tone: '' };
      return '';
    }
    if (prev.value === n) return prev.tone;
    var tone = n > prev.value ? 'up' : 'down';
    oiSeen[key] = { value: n, tone: tone };
    return tone;
  }
  function renderChain(data) {
    var rows = data && Array.isArray(data.rows) ? data.rows.filter(function (row) {
      return row && Number(row.strike) > 0 && (row.CE || row.PE);
    }) : [];
    if (data && (data.expiry || (data.expiries && data.expiries.length))) lastChain = data;
    fillStrikes(rows);
    var pack = expiryList(data || lastChain);
    var source = data || lastChain || {};
    var indexNode = document.getElementById('index');
    var indexName = source.index || (indexNode && indexNode.value) || 'NIFTY';
    var expiryKey = chainExpiry || pack.current || '';
    chainHost.replaceChildren();
    var bar = document.createElement('div');
    bar.className = 'kiteChainBar';
    var indexSelect = document.createElement('select');
    indexSelect.className = 'kiteChainIndex';
    indexSelect.setAttribute('aria-label', 'Index');
    var names = [];
    if (indexNode) {
      Array.prototype.forEach.call(indexNode.options, function (option) {
        var value = option.value || option.textContent;
        if (value && names.indexOf(value) < 0) names.push(value);
      });
    }
    if (!names.length) names = [indexName];
    names.forEach(function (name) { indexSelect.add(new Option(name, name)); });
    if (names.indexOf(indexName) >= 0) indexSelect.value = indexName;
    indexSelect.addEventListener('change', function () {
      chainExpiry = '';
      if (indexNode) {
        indexNode.value = indexSelect.value;
        indexNode.dispatchEvent(new Event('change', { bubbles: true }));
      } else loadStrikes();
    });
    var expirySelect = document.createElement('select');
    expirySelect.className = 'kiteChainExpiry';
    expirySelect.setAttribute('aria-label', 'Option chain expiry');
    fillExpirySelect(expirySelect, pack.list, expiryKey);
    expirySelect.addEventListener('change', function () {
      chainExpiry = expirySelect.value;
      loadStrikes(expirySelect.value);
    });
    var showOi = chainView !== 'ltp';
    var showLtp = chainView !== 'oi';
    var switcher = document.createElement('div');
    switcher.className = 'kiteChainSwitch';
    switcher.setAttribute('aria-label', 'Chain columns');
    function metricButton(text, mode) {
      var button = document.createElement('button');
      button.type = 'button';
      button.textContent = text;
      var on = chainView === mode || (chainView === 'all' && mode === 'ltp');
      if (on) button.className = 'is-on';
      button.setAttribute('aria-pressed', String(chainView === mode || (mode === 'ltp' && chainView === 'all' && false)));
      button.onclick = function () {
        chainView = chainView === mode ? 'all' : mode;
        if (lastChain) renderChain(lastChain);
      };
      return button;
    }
    switcher.append(metricButton('LTP', 'ltp'), metricButton('OI', 'oi'));
    var callSide = document.createElement('span');
    callSide.className = 'kiteSide call';
    callSide.textContent = 'CALL';
    var putSide = document.createElement('span');
    putSide.className = 'kiteSide put';
    putSide.textContent = 'PUT';
    bar.append(indexSelect, expirySelect, callSide, switcher, putSide);
    chainHost.append(bar);
    fillExpirySelect(document.getElementById('chainExpiry'), pack.list, expiryKey);
    fillExpirySelect(document.getElementById('ml-chain-expiry'), pack.list, expiryKey);
    if (!rows.length) {
      var empty = document.createElement('p');
      empty.className = 'kiteChainEmpty';
      empty.textContent = 'The broker option chain is empty. The market is closed.';
      chainHost.append(empty);
      return;
    }
    var table = document.createElement('table');
    table.className = 'kiteChainTable';
    var sideRow = document.createElement('tr');
    sideRow.className = 'kiteSideRow';
    function sideHead(text, span, cls) {
      if (!span) return;
      var th = document.createElement('th');
      th.colSpan = span;
      th.className = cls;
      th.textContent = text;
      sideRow.append(th);
    }
    var callSpan = (showOi ? 1 : 0) + (showLtp ? 1 : 0);
    sideHead('CALL', callSpan, 'call');
    sideHead('', 1, 'strike');
    sideHead('PUT', callSpan, 'put');
    var head = document.createElement('tr');
    function colHead(text, cls) {
      var th = document.createElement('th');
      th.textContent = text;
      th.className = cls;
      head.append(th);
    }
    if (showOi) colHead('Call OI', 'call');
    if (showLtp) colHead('Call LTP', 'call');
    colHead('Strike', 'strike');
    if (showLtp) colHead('Put LTP', 'put');
    if (showOi) colHead('Put OI', 'put');
    table.append(sideRow, head);
    var colCount = head.children.length;
    var spot = Number(source.spot);
    var spotPlaced = false;
    rows.forEach(function (row, index) {
      var tr = document.createElement('tr');
      tr.dataset.strike = String(row.strike);
      function cell(text, cls, side) {
        var td = document.createElement('td');
        td.textContent = text;
        td.className = cls;
        td.onclick = function () {
          if (side) chooseChain(side, row);
          else {
            if (row.CE) chooseChain('CE', row);
            if (row.PE) chooseChain('PE', row);
          }
        };
        tr.append(td);
      }
      var stamp = String(source.as_of || '') + '|' + indexName + '|' + expiryKey + '|' + row.strike;
      if (showOi) cell(oiText(row.CE && row.CE.oi), 'call oi ' + oiTone(stamp + '|CE', row.CE && row.CE.oi), 'CE');
      if (showLtp) cell(chainPrice(row.CE && row.CE.ltp), 'call ltp', 'CE');
      cell(strikeText(row.strike), 'strike', '');
      if (showLtp) cell(chainPrice(row.PE && row.PE.ltp), 'put ltp', 'PE');
      if (showOi) cell(oiText(row.PE && row.PE.oi), 'put oi ' + oiTone(stamp + '|PE', row.PE && row.PE.oi), 'PE');
      table.append(tr);
      var next = rows[index + 1];
      if (!spotPlaced && next && Number.isFinite(spot) && spot >= Number(row.strike) && spot < Number(next.strike)) {
        var spotRow = document.createElement('tr');
        spotRow.className = 'kiteSpotRow';
        var spotCell = document.createElement('td');
        spotCell.colSpan = colCount;
        var pill = document.createElement('span');
        pill.className = 'kiteSpot';
        pill.textContent = spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        spotCell.append(pill);
        spotRow.append(spotCell);
        table.append(spotRow);
        spotPlaced = true;
      }
    });
    chainHost.append(table);
  }
  function loadStrikes(expiryOverride) {
    if (typeof expiryOverride === 'string') chainExpiry = expiryOverride;
    var indexNode = document.getElementById('index');
    var expiryNode = document.getElementById('expirySelect') || document.getElementById('expiry');
    var index = indexNode && indexNode.value ? indexNode.value : 'NIFTY';
    var expiry = chainExpiry || (expiryNode && expiryNode.value) || '';
    var url = '/mc325/api/option-chain?index=' + encodeURIComponent(index);
    if (expiry) url += '&expiry=' + encodeURIComponent(expiry);
    fetch(url, { credentials: 'same-origin', cache: 'no-store' }).then(function (res) {
      return res.ok ? res.json() : null;
    }).then(function (data) {
      if (data && data.error) data = null;
      renderChain(data);
    }).catch(function () { renderChain(lastChain); });
  }
  function onStrike(side, value) {
    if (!(Number(value) > 0)) return;
    var picked = chainRows.find(function (item) { return String(item.strike) === String(value); });
    if (picked && picked[side]) rememberPrice(side, picked[side].ltp);
    if (!multi) {
      var otherSide = side === 'CE' ? 'PE' : 'CE';
      var other = document.querySelector('.kiteStrike[data-side="' + otherSide + '"]');
      window['mc325Strike' + side] = Number(value);
      if (other && Number(strikeValue(other)) > 0) window['mc325Strike' + otherSide] = Number(strikeValue(other));
      window.mc325SelectedStrike = 0;
      var expiry = document.getElementById('expirySelect');
      if (expiry) expiry.dispatchEvent(new Event('change', { bubbles: true }));
      return;
    }
    var row = chainRows.find(function (item) { return String(item.strike) === String(value); });
    var contract = row && row[side];
    if (!contract || typeof window.shivSelectContract !== 'function') return;
    var expiryNode = document.getElementById('expiry');
    var indexNode = document.getElementById('index');
    window.shivSelectContract(side, Object.assign({}, contract, {
      expiry: (expiryNode && expiryNode.value) || contract.expiry,
      strike: Number(row.strike),
      index: (indexNode && indexNode.value) || contract.index
    }));
    var box = document.getElementById('exec' + side);
    var opener = box && box.querySelector('[data-chart]');
    if (opener) opener.click();
  }
  function brokerName(text) {
    var name = String(text || '').replace(/\s+/g, ' ').trim();
    if (/zerodha/i.test(name)) return 'Zerodha';
    if (/angel/i.test(name)) return 'Angel';
    return name;
  }
  function brokerSource() {
    return document.querySelector('.manual-brokers') || document.querySelector('.brokers');
  }
  function brokerChecks() {
    var host = el('div', '', 'kiteBrokers');
    var source = brokerSource();
    if (!source) return host;
    source.querySelectorAll('label').forEach(function (label) {
      var input = label.querySelector('input');
      if (!input) return;
      var box = document.createElement('label');
      box.className = 'kiteCheck';
      var mirror = document.createElement('input');
      mirror.type = 'checkbox';
      mirror.checked = input.checked;
      mirror.dataset.account = input.value || '';
      mirror.dataset.broker = brokerName(label.textContent);
      mirror.addEventListener('change', function () {
        if (input.checked !== mirror.checked) {
          input.checked = mirror.checked;
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }
        document.querySelectorAll('.kiteCheck input').forEach(function (peer) {
          if (peer.dataset.broker === mirror.dataset.broker) peer.checked = mirror.checked;
        });
      });
      var full = brokerName(label.textContent);
      var span = document.createElement('span');
      span.textContent = /zerodha/i.test(full) ? 'Z' : /angel/i.test(full) ? 'A' : full.slice(0, 1).toUpperCase();
      box.title = full;
      mirror.title = full;
      span.title = full;
      box.append(mirror, span);
      host.append(box);
    });
    return host;
  }
  function labelName(label, text) {
    if (!label) return;
    var name = label.querySelector('.kiteSlName');
    if (!name) {
      name = document.createElement('span');
      name.className = 'kiteSlName';
      label.insertBefore(name, label.firstChild);
    }
    name.textContent = text;
    Array.prototype.forEach.call(label.childNodes, function (node) {
      if (node.nodeType === 3) node.textContent = '';
    });
  }
  function fillRow2(card) {
    if (!card) return;
    if (card.dataset.kiteRow2 === '1') {
      dressTrail(card);
      return;
    }
    var row2 = card.querySelector('.kiteRow2');
    if (!row2) {
      row2 = el('div', '', 'kiteRow2');
      var row = card.querySelector('.kiteRow');
      if (row) row.insertAdjacentElement('afterend', row2);
      else card.insertBefore(row2, card.firstChild);
    }
    var stop = card.querySelector('input[aria-label$="initial protective stop"], input[aria-label$="initial SL points"]');
    var stopLabel = stop ? stop.closest('label') : null;
    var apply = null;
    card.querySelectorAll('button').forEach(function (button) {
      if (apply || button.closest('.kiteActions')) return;
      var text = (button.textContent || '').replace(/\s+/g, ' ').trim();
      if (text === 'Apply SL' || text === 'Arm SL') apply = button;
    });
    if (apply && stopLabel && stopLabel.contains(apply)) apply.remove();
    if (apply) apply.textContent = 'Apply SL';
    if (stopLabel) labelName(stopLabel, 'Initial SL');
    card.querySelectorAll('.portfolio-mtm-button, .separate-mtm-row').forEach(function (node) {
      node.hidden = true;
      node.setAttribute('aria-hidden', 'true');
    });
    var trail = card.querySelector('.manual-trail-toggle');
    var mtm = card.querySelector('.kiteMtm');
    if (!mtm) {
      mtm = document.createElement('button');
      mtm.type = 'button';
      mtm.className = 'kiteMtm';
      mtm.textContent = 'MTM off';
    }
    if (!mtm.classList.contains('kiteMtm')) mtm.classList.add('kiteMtm');
    noteMtm(mtm);
    if (mtm.dataset.kiteMtm !== '1') {
      mtm.dataset.kiteMtm = '1';
      mtm.addEventListener('click', function (event) {
        event.preventDefault();
        event.stopImmediatePropagation();
        openMtmSettings();
        refreshMtmQuiet();
      }, true);
    }
    var exits = card.querySelector('.manual-exits, .quick-exits');
    [stopLabel, trail, mtm, exits, apply].forEach(function (node) {
      if (node) row2.append(node);
    });
    card.dataset.kiteRow2 = '1';
    dressTrail(card);
  }
  function noteMtm(button) {
    var text = (button.textContent || '').replace(/\s+/g, ' ').trim();
    if (/^MTM Trail\b/.test(text)) button.dataset.native = text;
    var open = document.getElementById('mtm-open');
    if (open && open.textContent && /^[✓ ]*MTM Trail\b/.test(open.textContent.replace(/\s+/g, ' ').trim())) button.dataset.native = open.textContent.replace(/\s+/g, ' ').trim();
  }
  function mtmIsOn(button) {
    var open = document.getElementById('mtm-open');
    if (open && open.dataset.enabled === 'true') return true;
    if (open && open.dataset.enabled === 'false') return false;
    var native = button.dataset.native || '';
    if (/·\s*[1-9]/.test(native) || /✓/.test(native)) return true;
    if (native === 'MTM Trail' || /Off/.test(native)) return false;
    return button.classList.contains('is-on');
  }
  function mtmFieldsFor(account) {
    var key = account === 'kite_main' ? 'zerodha' : account === 'angelone_main' ? 'angel' : String(account || '').toLowerCase();
    var enable = null;
    document.querySelectorAll('input[aria-label$="MTM enabled"]').forEach(function (input) {
      if ((input.getAttribute('aria-label') || '').toLowerCase().indexOf(key) >= 0) enable = input;
    });
    if (!enable) return null;
    var root = enable.closest('fieldset, .mtm-row') || enable.parentElement;
    function field(part) {
      var found = null;
      if (!root) return null;
      root.querySelectorAll('input').forEach(function (input) {
        var label = ((input.getAttribute('aria-label') || '') + ' ' + (input.dataset.field || '')).toLowerCase();
        if (label.indexOf(part) >= 0) found = input;
      });
      return found;
    }
    return { enable: enable, activation: field('activation'), stop: field('initial'), gap: field('gap') };
  }
  function ticketBrokerOn(account) {
    var on = false;
    document.querySelectorAll('.kiteCheck input').forEach(function (input) {
      if (!input.checked) return;
      if (input.dataset.account === account) on = true;
      var name = input.dataset.broker || '';
      if (account === 'kite_main' && (/zerodha/i.test(name) || name === 'kite_main')) on = true;
      if (account === 'angelone_main' && (/angel/i.test(name) || name === 'angelone_main')) on = true;
    });
    return on;
  }
  function ticketAnyBroker() {
    return !!document.querySelector('.kiteCheck input:checked');
  }
  function refreshMtmQuiet() {
    fetch('/mc325/api/manual/mtm', { credentials: 'same-origin', cache: 'no-store' }).then(function (res) {
      return res.ok ? res.json() : null;
    }).then(function (data) {
      if (!data || !Array.isArray(data.accounts)) return;
      var on = data.accounts.some(function (row) { return row.enabled; });
      if (mtmCacheOn === on) {
        var sample = document.querySelector('.kiteMtm');
        if (sample && sample.classList.contains('is-on') === on) return;
      }
      mtmCacheOn = on;
      document.querySelectorAll('.kiteMtm').forEach(function (button) {
        button.classList.toggle('is-on', on);
        var text = on ? 'MTM on' : 'MTM off';
        if (button.textContent !== text) button.textContent = text;
        button.title = on ? 'MTM trail is on' : 'MTM trail is off';
      });
      var open = document.getElementById('mtm-open');
      if (open) open.dataset.enabled = String(on);
    }).catch(function () {});
  }
  function toggleMtm(button) {
    if (button.dataset.busy === '1') return;
    button.dataset.busy = '1';
    var turnOn = !mtmIsOn(button);
    fetch('/mc325/api/manual/mtm', { credentials: 'same-origin', cache: 'no-store' }).then(function (res) {
      return res.ok ? res.json() : null;
    }).then(function (data) {
      var accounts = data && data.accounts ? data.accounts : [];
      accounts.forEach(function (row) {
        var fields = mtmFieldsFor(row.account);
        if (!fields) return;
        if (fields.activation && row.activation != null) fields.activation.value = row.activation;
        if (fields.stop && row.initial_stop != null) fields.stop.value = row.initial_stop;
        if (fields.gap && row.gap != null) fields.gap.value = row.gap;
        fields.enable.checked = !!(turnOn && row.selected !== false && ticketBrokerOn(row.account));
      });
      var willOn = !!(turnOn && accounts.some(function (row) { return row.selected !== false && ticketBrokerOn(row.account); }));
      var save = document.querySelector('.mtm-dialog [data-save], #save-mtm');
      if (save && accounts.length) save.click();
      button.dataset.native = willOn ? 'MTM Trail · 1' : 'MTM Trail';
      var open = document.getElementById('mtm-open');
      if (open) open.dataset.enabled = String(willOn);
      mtmCacheOn = willOn;
      document.querySelectorAll('.kiteMtm').forEach(function (btn) {
        btn.classList.toggle('is-on', willOn);
        var text = willOn ? 'MTM on' : 'MTM off';
        if (btn.textContent !== text) btn.textContent = text;
      });
    }).catch(function () {
      refreshMtmQuiet();
    }).then(function () {
      button.dataset.busy = '';
    });
  }
  function dressTrail(card) {
    if (!card) return;
    var trail = card.querySelector('.manual-trail-toggle');
    if (!trail) return;
    var input = trail.querySelector('input');
    var span = trail.querySelector('span');
    if (!span) {
      span = document.createElement('span');
      trail.appendChild(span);
    }
    var on = !!(input && input.checked);
    trail.classList.toggle('is-on', on);
    var text = on ? 'Trail on' : 'Trail off';
    if (span.textContent !== text) span.textContent = text;
    if (input && input.dataset.kiteTrail !== '1') {
      input.dataset.kiteTrail = '1';
      input.addEventListener('change', function () { dressTrail(card); });
    }
    if (trail.dataset.kiteTrailOpen !== '1') {
      trail.dataset.kiteTrailOpen = '1';
      trail.addEventListener('click', function (event) {
        if (event.target.closest('.manual-trail-save, .manual-trail-bar')) return;
        event.preventDefault();
        event.stopPropagation();
        openTrailSettings(card);
      }, true);
    }
  }
  function dressTickets() {
    var added = false;
    [['CE', call], ['PE', put]].forEach(function (spec) {
      var host = spec[1];
      var card = host.querySelector('.order-card, .exec');
      if (!card) return;
      if (card.querySelector('.kiteRow')) {
        ensureKiteEntryControls(spec[1], spec[0]);
        hookKiteEntryButtons(spec[1]);
        fillRow2(card);
        return;
      }
      fillRow2(card);
      added = true;
      var row = el('div', '', 'kiteRow');
      row.append(brokerChecks());
      var strikePop = strikeControl(spec[0]);
      var limit = el('span', '', 'kiteLimit');
      var mode = document.createElement('select');
      mode.className = 'kiteOrderType';
      mode.setAttribute('aria-label', spec[0] + ' order type');
      mode.innerHTML = '<option value="MARKET">Market</option><option value="LIMIT">Limit</option>';
      mode.value = 'LIMIT';
      var price = document.createElement('input');
      price.type = 'text';
      price.inputMode = 'decimal';
      price.className = 'kiteLimitPrice';
      price.setAttribute('aria-label', spec[0] + ' limit price');
      price.placeholder = '—';
      price.addEventListener('input', function () { price.dataset.userEdited = '1'; });
      mode.addEventListener('change', function () {
        applyKiteEntryMode(spec[1]);
        syncKiteEntryToNative(spec[1]);
      });
      limit.append(mode, price);
      var note = el('span', '', 'kiteLotNote');
      note.textContent = '1 Lot = — qty';
      var lots = card.querySelector('input[aria-label$="lots"]');
      var minus = card.querySelector('[data-minus]');
      var plus = card.querySelector('[data-plus]');
      if (lots && !plus) {
        minus = document.createElement('button');
        minus.type = 'button';
        minus.className = 'kiteStep';
        minus.textContent = '−';
        minus.setAttribute('aria-label', 'Decrease lots');
        plus = document.createElement('button');
        plus.type = 'button';
        plus.className = 'kiteStep';
        plus.textContent = '+';
        plus.setAttribute('aria-label', 'Increase lots');
        function step(delta) {
          var next = Math.max(1, (parseInt(lots.value, 10) || 1) + delta);
          lots.value = String(next);
          lots.dispatchEvent(new Event('input', { bubbles: true }));
          lots.dispatchEvent(new Event('change', { bubbles: true }));
          paintLot(card);
        }
        minus.onclick = function () { step(-1); };
        plus.onclick = function () { step(1); };
      }
      var stepper = el('span', '', 'kiteStepper');
      if (minus) stepper.append(minus);
      if (lots) stepper.append(lots);
      if (plus) stepper.append(plus);
      var actions = el('div', '', 'kiteActions');
      card.querySelectorAll('.manual-buy, .manual-sell, .buy, .sell').forEach(function (button) {
        actions.append(button);
      });
      var block = el('div', '', 'kiteBlock');
      block.hidden = true;
      row.append(strikePop, limit, stepper, note, actions);
      card.insertBefore(block, card.firstChild);
      card.insertBefore(row, card.firstChild);
      applyKiteEntryMode(spec[1]);
      hookKiteEntryButtons(spec[1]);
      fillRow2(card);
    });
    if (added && chainRows.length) fillStrikes(chainRows);
    paintLimits();
    paintLots();
    dressButtons();
    paintBlocks();
    paintBrokerNotes();
  }
  function setText(node, value) {
    if (node && node.textContent !== value) node.textContent = value;
  }
  function paintLimits() {
    [['CE', call], ['PE', put]].forEach(function (spec) {
      var price = spec[1].querySelector('.kiteLimitPrice');
      if (!price) return;
      var source = document.getElementById('price' + spec[0]);
      var text = source ? source.textContent : '';
      if (!text || text.trim() === '—') {
        var ltp = spec[1].querySelector('[data-ltp]');
        text = ltp ? (ltp.textContent || '').replace(/^LTP\s*/i, '') : '';
      }
      var mode = spec[1].querySelector('.kiteOrderType');
      if (mode && mode.value === 'MARKET') return;
      if (price.dataset.userEdited === '1') return;
      var chainPrice = price.dataset.chain;
      if (chainPrice && text && text.trim() === chainPrice) delete price.dataset.chain;
      var next = price.dataset.chain || '';
      if (!next && text && text.trim() && text.trim() !== '—' && text.trim() !== '-') next = text.trim();
      if (price.tagName === 'INPUT') {
        if (price.value !== next) price.value = next;
      } else if (price.textContent !== next) price.textContent = next;
    });
    document.querySelectorAll('.kiteChainTable tr[data-strike]').forEach(function (tr) {
      var strike = tr.dataset.strike;
      var picked = false;
      document.querySelectorAll('.kiteStrike').forEach(function (select) {
        if (strikeValue(select) && strikeValue(select) === strike) picked = true;
      });
      tr.classList.toggle('is-picked', picked);
    });
  }
  function paintBlocks() {
    var result = document.querySelector('.manual-result');
    var text = (result && result.textContent || '').replace(/\s+/g, ' ').trim();
    var blocked = /block|unavailable|closed|reject|not allowed|sign in/i.test(text);
    [call, put].forEach(function (host) {
      var block = host.querySelector('.kiteBlock');
      if (!block) return;
      if (!blocked) {
        block.hidden = true;
        block.textContent = '';
        return;
      }
      block.hidden = false;
      setText(block, text.slice(0, 160));
    });
  }
  function paintBrokerNotes() {
    var msg = ticketAnyBroker() ? '' : 'Select broker';
    [call, put].forEach(function (host) {
      var card = host.querySelector('.order-card, .exec');
      if (!card) return;
      var note = card.querySelector('.kiteBrokerNote');
      if (!note) {
        note = el('div', '', 'kiteBrokerNote');
        card.append(note);
      }
      note.hidden = !msg;
      setText(note, msg);
    });
  }
  function paintLot(card) {
    var note = card.querySelector('.kiteLotNote');
    if (!note) return;
    var lots = card.querySelector('input[aria-label$="lots"]');
    var qtyNode = card.querySelector('.manual-quantity b, .qty');
    var count = Number(lots && lots.value);
    var qty = Number(String(qtyNode && qtyNode.textContent || '').replace(/[^\d.]/g, ''));
    setText(note, count > 0 && qty > 0 ? '1 Lot = ' + Math.round(qty / count) + ' qty' : '1 Lot = — qty');
  }
  function paintLots() {
    [call, put].forEach(function (host) {
      host.querySelectorAll('.order-card, .exec').forEach(paintLot);
    });
  }
  function compactReq(n) {
    if (!(n >= 0)) return '';
    if (n >= 100000) return '₹' + (n / 100000).toFixed(2) + 'L';
    if (n >= 1000) return '₹' + (n / 1000).toFixed(2) + 'K';
    return '₹' + n.toFixed(2);
  }
  function marginAmounts(text) {
    var found = [];
    String(text || '').replace(/₹\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(Cr|[KkLl])?/g, function (_, num, unit) {
      var n = Number(String(num).replace(/,/g, ''));
      if (!isFinite(n)) return '';
      var u = (unit || '').toLowerCase();
      if (u === 'k') n *= 1000;
      else if (u === 'l') n *= 100000;
      else if (u === 'cr') n *= 10000000;
      found.push(n);
      return '';
    });
    return found;
  }
  function buttonMarginLine(button) {
    var stored = button.dataset.reqMargin || '';
    if (stored && /^Req\.\s/.test(stored)) return stored;
    var small = button.querySelector('small');
    var raw = small ? small.textContent : '';
    if (/^Req\.\s/.test(raw)) return raw;
    var amounts = marginAmounts(raw || button.textContent || '');
    if (amounts.length) return 'Req. ' + compactReq(Math.max.apply(null, amounts));
    return '';
  }
  function dressButton(button) {
    if (button.dataset.kiteBtn === '1' && button.dataset.kiteSig === (button.dataset.reqMargin || '') + '|' + (button.classList.contains('sell') || button.classList.contains('manual-sell') ? 'S' : 'B')) return;
    var ticket = button.closest('#kiteCall, #kitePut');
    var name = ticket && ticket.id === 'kitePut' ? 'PUT' : 'CALL';
    var sell = button.classList.contains('sell') || button.classList.contains('manual-sell');
    var label = (sell ? 'SELL ' : 'BUY ') + name;
    var margin = buttonMarginLine(button);
    var small = button.querySelector('small');
    if (!small) {
      small = document.createElement('small');
      button.appendChild(small);
    }
    var main = button.querySelector('.kiteBtnMain');
    if (!main) {
      main = document.createElement('span');
      main.className = 'kiteBtnMain';
      button.insertBefore(main, button.firstChild);
    }
    Array.prototype.forEach.call(button.childNodes, function (node) {
      if (node !== main && node !== small && node.nodeType === 3) node.textContent = '';
    });
    if (main.textContent !== label) main.textContent = label;
    if (small.textContent !== margin) small.textContent = margin;
    small.hidden = !margin;
    button.dataset.kiteBtn = '1';
    button.dataset.kiteSig = (button.dataset.reqMargin || '') + '|' + (sell ? 'S' : 'B');
  }
  function dressButtons() {
    [call, put].forEach(function (host) {
      host.querySelectorAll('.manual-buy, .manual-sell, .buy, .sell').forEach(dressButton);
    });
  }
  function syncButtonMargin(button) {
    if (!button || !button.dataset.kiteBtn) return;
    var margin = buttonMarginLine(button);
    var sig = (button.dataset.reqMargin || '') + '|' + (button.classList.contains('sell') || button.classList.contains('manual-sell') ? 'S' : 'B');
    if (button.dataset.kiteSig === sig) return;
    var small = button.querySelector('small');
    if (!small) return;
    if (small.textContent !== margin) small.textContent = margin;
    small.hidden = !margin;
    button.dataset.kiteSig = sig;
  }
  function paintTicketDynamic() {
    paintLimits();
    paintLots();
    [call, put].forEach(function (host) {
      host.querySelectorAll('.manual-buy, .manual-sell, .buy, .sell').forEach(syncButtonMargin);
    });
    paintBlocks();
    paintBrokerNotes();
  }
  var ticketDressLock = false;
  new MutationObserver(function () {
    if (ticketDressLock) return;
    var need = false;
    [call, put].forEach(function (host) {
      var card = host.querySelector('.order-card, .exec');
      if (card && !card.querySelector('.kiteRow')) need = true;
    });
    if (!need) return;
    ticketDressLock = true;
    try {
      dressTickets();
    } finally {
      ticketDressLock = false;
    }
  }).observe(tickets, { childList: true });
  ticketPaintTimer = setInterval(paintTicketDynamic, 1200);
  dressTickets();
  if (!tickets.dataset.kiteTicketHooks) {
    tickets.dataset.kiteTicketHooks = '1';
    tickets.addEventListener('click', function (event) {
      var mtm = event.target.closest('.kiteMtm');
      if (mtm) {
        event.preventDefault();
        event.stopPropagation();
        openMtmSettings();
        return;
      }
      var trail = event.target.closest('.kiteRow2 .manual-trail-toggle');
      if (!trail || event.target.closest('.manual-trail-save, .manual-trail-bar')) return;
      var card = trail.closest('.order-card, .exec');
      if (!card) return;
      event.preventDefault();
      event.stopPropagation();
      openTrailSettings(card);
    }, true);
  }
  [call, put].forEach(function (host) {
    host.querySelectorAll('.manual-buy, .manual-sell, .buy, .sell').forEach(function (button) {
      new MutationObserver(function () { syncButtonMargin(button); }).observe(button, { attributes: true, attributeFilter: ['data-req-margin'] });
    });
  });
  refreshMtmQuiet();
  setInterval(refreshMtmQuiet, 30000);
  loadStrikes();
  setInterval(loadStrikes, 60000);
  ['index', 'expirySelect', 'expiry'].forEach(function (id) {
    var node = document.getElementById(id);
    if (node) node.addEventListener('change', function () { chainExpiry = ''; loadStrikes(); });
  });
  ['chainExpiry', 'ml-chain-expiry'].forEach(function (id) {
    var node = document.getElementById(id);
    if (!node) return;
    node.addEventListener('change', function () {
      chainExpiry = node.value;
      loadStrikes(node.value);
    });
  });
  var nativeChain = document.getElementById('optionChainDialog');
  if (nativeChain) nativeChain.addEventListener('close', function () {
    if (!lastChain) return;
    var pack = expiryList(lastChain);
    fillExpirySelect(document.getElementById('chainExpiry'), pack.list, chainExpiry || pack.current);
  });
  document.addEventListener('click', function (event) {
    var row = event.target.closest && event.target.closest('#chainTable tbody tr');
    if (!row) return;
    var strike = row.getAttribute('data-strike');
    if (!strike) return;
    ['CE', 'PE'].forEach(function (side) {
      window['mc325Strike' + side] = Number(strike);
      var select = document.querySelector('.kiteStrike[data-side="' + side + '"]');
      if (!select) return;
      ensureOption(select, strike);
    });
  }, false);
  document.addEventListener('click', function (event) {
    var cell = event.target.closest && event.target.closest('#chain-rows td');
    if (!cell || !cell.parentElement) return;
    var strike = cell.parentElement.getAttribute('data-strike');
    if (!strike) return;
    var index = Array.prototype.indexOf.call(cell.parentElement.children, cell);
    var side = index >= 3 ? 'PE' : 'CE';
    event.preventDefault();
    event.stopImmediatePropagation();
    var select = document.querySelector('.kiteStrike[data-side="' + side + '"]');
    if (!select) return;
    ensureOption(select, strike);
    onStrike(side, strike);
  }, true);
  document.addEventListener('click', function () { closeStrikeMenus(); });
  function fillChartHost() {
    var host = document.getElementById('kiteCharts');
    if (!host || host.clientHeight < 80) return;
    var grid = host.querySelector('.grid, #charts');
    if (grid) {
      grid.style.setProperty('height', host.clientHeight + 'px', 'important');
      grid.style.setProperty('min-height', host.clientHeight + 'px', 'important');
    }
    host.querySelectorAll('.panel, .chart-card').forEach(function (panel) {
      if (panel.hidden) return;
      panel.style.setProperty('height', host.clientHeight + 'px', 'important');
      panel.style.setProperty('min-height', '0', 'important');
      panel.style.setProperty('overflow', 'hidden', 'important');
    });
    host.querySelectorAll('.chart, .chart-pane').forEach(function (node) {
      var panel = node.closest('.panel, .chart-card') || host;
      var used = 0;
      Array.prototype.forEach.call(panel.children, function (child) {
        if (child === node || child.contains(node)) return;
        if (window.getComputedStyle(child).display === 'none') return;
        used += child.offsetHeight;
      });
      var height = Math.max(160, panel.clientHeight - used);
      node.style.setProperty('height', height + 'px', 'important');
      node.style.setProperty('min-height', '0', 'important');
    });
    if (window.mc325Charts) {
      ['CE', 'REF', 'PE'].forEach(function (id) {
        var node = document.getElementById('chart' + id);
        var slot = window.mc325Charts[id];
        if (!node || !slot || !slot.chart || node.clientHeight < 40) return;
        try { slot.chart.resize(node.clientWidth, node.clientHeight); } catch (err) {}
      });
    }
  }
  var fills = 0;
  var fillTimer = setInterval(function () {
    fillChartHost();
    if (++fills > 24) clearInterval(fillTimer);
  }, 400);
  window.addEventListener('resize', function () { requestAnimationFrame(fillChartHost); });
  function bindChartLayout() {
    var host = document.getElementById('kiteCharts');
    if (!host || host.dataset.kiteLayout === '1') return;
    host.dataset.kiteLayout = '1';
    var resizeDrag = null;
    var frame = 0;
    var focusId = 'REF';
    function gridOf() {
      return host.querySelector('.grid, #charts');
    }
    function panelsOf(grid) {
      return Array.prototype.filter.call(grid.children, function (node) {
        if (!node || node.hidden) return false;
        if (!node.classList.contains('panel') && !node.classList.contains('chart-card')) return false;
        return window.getComputedStyle(node).display !== 'none';
      });
    }
    function panelChartId(panel) {
      if (!panel) return '';
      if (panel.querySelector('#chartCE')) return 'CE';
      if (panel.querySelector('#chartREF')) return 'REF';
      if (panel.querySelector('#chartPE')) return 'PE';
      var label = panel.querySelector('.chart-contract-label');
      var text = label ? label.textContent : '';
      if (/\bCE\b/.test(text)) return 'CE';
      if (/\bPE\b/.test(text)) return 'PE';
      if (/SPOT/i.test(text)) return 'REF';
      return '';
    }
    function applyWidths(grid, panels, widths) {
      var sum = widths.reduce(function (total, width) { return total + width; }, 0) || 1;
      var cols = widths.map(function (width) { return 'minmax(0,' + (width / sum) + 'fr)'; }).join(' ');
      var detail = {};
      panels.forEach(function (panel, index) {
        var id = panelChartId(panel);
        if (id === 'CE' || id === 'REF' || id === 'PE') detail[id] = widths[index] / sum;
      });
      if (detail.CE || detail.REF || detail.PE) grid.dispatchEvent(new CustomEvent('kite-set-weights', { detail: detail }));
      if (grid.id === 'charts') grid.style.setProperty('--kite-cols', cols);
      else grid.style.setProperty('--chart-columns', cols);
      if (!frame) frame = requestAnimationFrame(function () { frame = 0; fillChartHost(); });
    }
    function setChartFocus(id) {
      if (!id) return;
      focusId = id;
      host.querySelectorAll('.panel, .chart-card').forEach(function (panel) {
        panel.classList.toggle('kite-chart-selected', panelChartId(panel) === id);
      });
      document.querySelectorAll('.chart-choices button[data-chart]').forEach(function (button) {
        button.classList.toggle('kite-tab-on', button.getAttribute('data-chart') === id);
        button.setAttribute('aria-pressed', String(button.getAttribute('data-chart') === id));
      });
      [['chart-side-ce', 'CE'], ['chart-side-spot', 'REF'], ['chart-side-pe', 'PE']].forEach(function (pair) {
        var input = document.getElementById(pair[0]);
        if (!input || !input.parentElement) return;
        input.parentElement.classList.toggle('kite-tab-on', pair[1] === id);
      });
    }
    var installEdgesLock = false;
    function installEdges() {
      if (installEdgesLock) return;
      var grid = gridOf();
      if (!grid) return;
      installEdgesLock = true;
      try {
        var panels = panelsOf(grid);
        panels.forEach(function (panel, index) {
          if (!panel.querySelector('.kiteChartEdgeL')) {
            var left = document.createElement('div');
            left.className = 'kiteChartEdge kiteChartEdgeL';
            left.setAttribute('aria-hidden', 'true');
            left.dataset.edge = 'left';
            var right = document.createElement('div');
            right.className = 'kiteChartEdge kiteChartEdgeR';
            right.setAttribute('aria-hidden', 'true');
            right.dataset.edge = 'right';
            panel.append(left, right);
          }
          var showLeft = index > 0;
          var showRight = index < panels.length - 1;
          panel.querySelectorAll('.kiteChartEdgeL').forEach(function (node) {
            if (node.hidden === showLeft) node.hidden = !showLeft;
          });
          panel.querySelectorAll('.kiteChartEdgeR').forEach(function (node) {
            if (node.hidden === showRight) node.hidden = !showRight;
          });
        });
      } finally {
        installEdgesLock = false;
      }
    }
    function beginResize(event, edge, panel) {
      if (event.button !== 0 || window.innerWidth < 851) return;
      var grid = gridOf();
      if (!grid) return;
      var panels = panelsOf(grid);
      var index = panels.indexOf(panel);
      if (index < 0) return;
      var pair = edge === 'left' ? [index - 1, index] : [index, index + 1];
      if (pair[0] < 0 || pair[1] >= panels.length) return;
      event.preventDefault();
      event.stopPropagation();
      var widths = panels.map(function (node) { return node.getBoundingClientRect().width; });
      resizeDrag = {
        id: event.pointerId,
        x: event.clientX,
        grid: grid,
        panels: panels,
        widths: widths,
        pair: pair
      };
      document.body.classList.add('kite-chart-resize');
      if (event.target.setPointerCapture) event.target.setPointerCapture(event.pointerId);
    }
    host.addEventListener('pointerdown', function (event) {
      var edge = event.target.closest && event.target.closest('.kiteChartEdge');
      if (edge) {
        var panel = edge.closest('.panel, .chart-card');
        beginResize(event, edge.dataset.edge || 'right', panel);
        return;
      }
      if (event.target.closest('button, input, select, textarea, a, label, .drawing-editor, .kiteStrikeMenu, .kiteChartEdge')) return;
      var panel = event.target.closest('.panel, .chart-card');
      if (!panel || !host.contains(panel)) return;
      var id = panelChartId(panel);
      if (id) setChartFocus(id);
    }, false);
    window.addEventListener('pointermove', function (event) {
      if (!resizeDrag || event.pointerId !== resizeDrag.id) return;
      event.preventDefault();
      var dx = event.clientX - resizeDrag.x;
      var widths = resizeDrag.widths.slice();
      var a = resizeDrag.pair[0];
      var b = resizeDrag.pair[1];
      var total = widths[a] + widths[b];
      var minW = Math.min(140, total * 0.18);
      var nextA = Math.max(minW, Math.min(total - minW, widths[a] + dx));
      widths[a] = nextA;
      widths[b] = total - nextA;
      resizeDrag.x = event.clientX;
      resizeDrag.widths = widths;
      applyWidths(resizeDrag.grid, resizeDrag.panels, widths);
    }, true);
    function endResize(event) {
      if (!resizeDrag || (event && event.pointerId !== resizeDrag.id)) return;
      resizeDrag = null;
      document.body.classList.remove('kite-chart-resize');
    }
    window.addEventListener('pointerup', endResize, true);
    window.addEventListener('pointercancel', endResize, true);
    document.querySelectorAll('.chart-choices button[data-chart]').forEach(function (button) {
      button.addEventListener('click', function (event) {
        var id = button.getAttribute('data-chart');
        if (id) setChartFocus(id);
      });
    });
    [['chart-side-ce', 'CE'], ['chart-side-spot', 'REF'], ['chart-side-pe', 'PE']].forEach(function (pair) {
      var input = document.getElementById(pair[0]);
      if (!input) return;
      input.addEventListener('change', function () { if (input.checked) setChartFocus(pair[1]); });
      if (input.parentElement) {
        input.parentElement.addEventListener('click', function () { setChartFocus(pair[1]); });
      }
    });
    installEdges();
    setChartFocus('REF');
    if (window.ResizeObserver) {
      new ResizeObserver(function () {
        if (installEdgesLock) return;
        installEdges();
      }).observe(host);
    }
    new MutationObserver(function () {
      if (installEdgesLock) return;
      installEdges();
    }).observe(host, { childList: true, attributes: true, attributeFilter: ['class', 'hidden'] });
  }
  bindChartLayout();
  var late = document.createElement('style');
  late.textContent = 'html body.kite-clean .order-card>:not(.kiteRow):not(.kiteRow2):not(.kiteBlock),html body.kite-clean .exec>:not(.kiteRow):not(.kiteRow2):not(.kiteBlock),html body.kite-clean .manual-heading,html body.kite-clean .manual-brokers,html body.kite-clean .manual-note,html body.kite-clean .manual-badge,html body.kite-clean .manual-trade,html body.kite-clean .manual-card-header,html body.kite-clean .manual-input-row,html body.kite-clean .manual-size-line,html body.kite-clean .manual-quantity,html body.kite-clean .separate-mtm-row,html body.kite-clean .manual-inline-status,html body.kite-clean .manual-accounts,html body.kite-clean .manual-card-details,html body.kite-clean .manual-trail-group,html body.kite-clean .manual-trail-bar,html body.kite-clean .levels,html body.kite-clean .chip,html body.kite-clean .manual-result,html body.kite-clean .manual-hint,html body.kite-clean .card-target,html body.kite-clean .entry-options,html body.kite-clean .card-bottom{display:none!important;}'
    + 'html body.kite-clean #kiteTickets{min-height:132px!important;height:auto!important;max-height:none!important;padding:8px 10px 14px!important;box-sizing:border-box!important;overflow:visible!important;align-items:stretch!important;grid-template-columns:minmax(0,1fr) max-content minmax(0,1fr)!important;}'
    + 'html body.kite-clean .kiteRow{display:grid!important;grid-template-columns:auto 120px minmax(150px,auto) minmax(68px,auto) minmax(0,0.25fr) minmax(332px,1.25fr)!important;align-items:center!important;gap:4px!important;min-height:60px!important;height:auto!important;max-height:none!important;overflow:visible!important;background:#fff!important;min-width:0!important;}'
    + 'html body.kite-clean .kiteLotNote{display:none!important;}'
    + 'html body.kite-clean .kiteCheck{gap:2px!important;font-size:12px!important;font-weight:700!important;}html body.kite-clean .kiteCheck input{width:13px!important;height:13px!important;flex:0 0 13px!important;}'
    + 'html body.kite-clean .kiteStrike{width:136px!important;min-width:136px!important;}'
    + 'html body.kite-clean .order-card>.kiteRow2.kiteRow2,html body.kite-clean .exec>.kiteRow2.kiteRow2{display:flex!important;align-items:center!important;gap:8px!important;min-height:36px!important;height:auto!important;max-height:none!important;overflow:visible!important;background:#fff!important;flex-wrap:nowrap!important;}html body.kite-clean .kiteRow2{display:flex!important;align-items:center!important;gap:8px!important;min-height:36px!important;height:auto!important;max-height:none!important;overflow:visible!important;background:#fff!important;flex-wrap:nowrap!important;}'
    + 'html body.kite-clean .kiteRow2 .manual-exits,html body.kite-clean .kiteRow2 .quick-exits,html body.kite-clean .kiteRow2 label:not(.manual-trail-toggle),html body.kite-clean .kiteRow2 label:has(input):not(.manual-trail-toggle),html body.kite-clean .kiteRow2>button:not(.kiteMtm){display:inline-flex!important;align-items:center!important;gap:4px!important;background:transparent!important;color:#222!important;white-space:nowrap!important;overflow:visible!important;height:auto!important;max-height:none!important;width:auto!important;font-size:12px!important;}'
    + 'html body.kite-clean .kiteRow2 .manual-trail-toggle,html body.kite-clean .kiteRow2 .kiteMtm{position:relative!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;height:26px!important;min-height:26px!important;padding:0 10px!important;border:1px solid #c5ced8!important;border-radius:2px!important;background:#d8dee6!important;color:#1f2937!important;font-size:12px!important;font-weight:650!important;cursor:pointer!important;}'
    + 'html body.kite-clean .kiteRow2 .manual-trail-toggle input{position:absolute!important;opacity:0!important;width:1px!important;height:1px!important;pointer-events:none!important;}'
    + 'html body.kite-clean .kiteRow2 .manual-trail-toggle.is-on,html body.kite-clean .kiteRow2 .kiteMtm.is-on{background:#067044!important;color:#fff!important;border-color:#067044!important;}'
    + 'html body.kite-clean .kiteRow2 .manual-trail-bar{display:none!important;}html body.kite-clean .kiteRow2>*{flex:0 0 auto!important;overflow:visible!important;max-width:none!important;}'
    + 'html body.kite-clean .kiteRow2 .manual-exits button,html body.kite-clean .kiteRow2 .quick-exits button{display:inline-flex!important;height:24px!important;padding:0 6px!important;white-space:nowrap!important;}'
    + 'html body.kite-clean .kiteRow2{padding-left:6px!important;padding-right:2px!important;}'
    + 'html body.kite-clean .kiteBrokerNote{width:100%!important;margin:0!important;padding:0 4px 2px!important;text-align:center!important;font-size:11px!important;font-weight:550!important;color:#64748b!important;line-height:1.2!important;}'
    + 'html body.kite-clean .kiteBrokerNote[hidden]{display:none!important;}'
    + 'html body.kite-clean #kiteCall .exec,html body.kite-clean #kitePut .exec,html body.kite-clean #kiteCall .order-card,html body.kite-clean #kitePut .order-card{padding:0!important;gap:6px!important;margin:0!important;height:auto!important;max-height:none!important;overflow:visible!important;background:#fff!important;}'
    + 'html body.kite-multi #ce-strikes .exec~.exec,html body.kite-multi #pe-strikes .exec~.exec{display:none!important;}'
    + 'html body.kite-clean #kiteCall,html body.kite-clean #kitePut{background:#fff!important;padding:4px 6px 6px!important;overflow:hidden!important;min-width:0!important;height:auto!important;max-height:none!important;border-radius:6px!important;}'
    + 'html body.kite-clean #kiteCall{border:2px solid #9ed9b8!important;}'
    + 'html body.kite-clean #kitePut{border:2px solid #f0b4bc!important;}'
    + 'html body.kite-clean #kiteCall aside,html body.kite-clean #kitePut aside,html body.kite-clean #ce-strikes,html body.kite-clean #pe-strikes{max-height:none!important;height:auto!important;overflow:visible!important;}'
    + 'html body.kite-clean #kitePnl{overflow:visible!important;width:max-content!important;min-width:132px!important;max-width:none!important;margin:0 8px!important;padding:8px 14px!important;border:1px solid #d5dde6!important;border-radius:8px!important;background:#fff!important;box-shadow:0 1px 3px rgba(15,23,42,.08)!important;align-self:center!important;}'
    + 'html body.kite-clean #kitePnl>span,html body.kite-clean #kitePnlValue{overflow:visible!important;white-space:nowrap!important;display:block!important;}'
    + 'html body.kite-multi #centre-pnl{display:none!important;}'
    + 'html body.kite-clean .side-title{display:none!important;}'
    + 'html body.kite-multi #ce-strikes,html body.kite-multi #pe-strikes,html body.kite-multi #kiteCall aside,html body.kite-multi #kitePut aside{display:block!important;margin:0!important;padding:0!important;border:0!important;background:transparent!important;}'
    + 'html body.kite-clean #holdExitBar,html body.kite-clean .toolbar,html body.kite-clean .context,html body.kite-clean #kiteHold{display:none!important;}'
    + 'html body.kite-multi #kitePills label{font-size:0!important;}'
    + 'html body.kite-multi #kitePills .kiteWord{font-size:11px!important;}'
    + 'html body.kite-clean .kiteActions{display:grid!important;grid-template-columns:minmax(158px,1fr) minmax(158px,1fr)!important;width:100%!important;min-width:332px!important;gap:8px!important;margin:0!important;}'
    + 'html body.kite-clean .kiteActions>button{box-sizing:border-box!important;width:100%!important;min-width:158px!important;max-width:none!important;height:58px!important;min-height:58px!important;max-height:none!important;flex:none!important;overflow:visible!important;display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:center!important;gap:2px!important;white-space:nowrap!important;text-overflow:clip!important;padding:5px 10px!important;font-size:12px!important;font-weight:700!important;line-height:1.2!important;letter-spacing:0!important;}'
    + 'html body.kite-clean .kiteActions>button .kiteBtnMain{display:block!important;white-space:nowrap!important;overflow:visible!important;text-overflow:clip!important;font-size:12px!important;font-weight:700!important;line-height:1.15!important;}'
    + 'html body.kite-clean .kiteActions>button small{display:block!important;white-space:nowrap!important;overflow:visible!important;text-overflow:clip!important;font-size:10px!important;font-weight:550!important;max-width:none!important;line-height:1.1!important;opacity:.92!important;}'
    + 'html body.kite-clean .drawing-editor{position:absolute!important;top:4px!important;left:4px!important;right:auto!important;width:max-content!important;max-width:calc(100% - 96px)!important;display:flex!important;flex-wrap:wrap!important;overflow:visible!important;z-index:30!important;}'
    + 'html body.kite-clean .drawing-editor[hidden]{display:none!important;}'
    + 'html body.kite-clean .drawing-editor label,html body.kite-clean .drawing-editor button,html body.kite-clean .drawing-editor input,html body.kite-clean .drawing-editor select{white-space:nowrap!important;overflow:visible!important;text-overflow:clip!important;line-height:normal!important;}'
    + 'html body.kite-clean .chart-size-handle{display:none!important;}'
    + 'html body.kite-clean #kiteCharts .panel,html body.kite-clean #kiteCharts .chart-card{position:relative!important;}'
    + 'html body.kite-clean .kiteChartEdge{position:absolute!important;top:0!important;bottom:0!important;width:10px!important;z-index:25!important;touch-action:none!important;background:transparent!important;}'
    + 'html body.kite-clean .kiteChartEdgeL{left:-5px!important;cursor:ew-resize!important;}'
    + 'html body.kite-clean .kiteChartEdgeR{right:-5px!important;cursor:ew-resize!important;}'
    + 'html body.kite-clean .kiteChartEdge:hover,html body.kite-clean .kiteChartEdge:focus-visible{background:rgba(36,89,168,.18)!important;}'
    + 'html body.kite-clean .panel.kite-chart-selected,html body.kite-clean .chart-card.kite-chart-selected{outline:2px solid #2459a8!important;outline-offset:-2px!important;}'
    + 'html body.kite-clean .chart-choices button.kite-tab-on,html body.kite-clean #kitePills label.kite-tab-on{background:#eef4ff!important;}'
    + 'html body.kite-chart-resize,html body.kite-chart-resize .kiteChartEdge{cursor:ew-resize!important;}'
    + 'html body.kite-clean #kiteClean .kiteTheme{position:relative!important;}'
    + 'html body.kite-clean #kiteClean .kiteMenu,html body.kite-clean #kiteClean .screen-theme-menu{position:absolute!important;right:0!important;top:calc(100% + 4px)!important;z-index:1200!important;min-width:168px!important;padding:6px!important;display:grid!important;gap:4px!important;background:var(--screen-surface,#fff)!important;color:var(--ink,#243348)!important;border:1px solid var(--screen-edge,#c8d1de)!important;border-radius:8px!important;box-shadow:0 8px 24px rgba(15,23,42,.18)!important;}'
    + 'html body.kite-clean #kiteClean .kiteMenu[hidden],html body.kite-clean #kiteClean .screen-theme-menu[hidden]{display:none!important;}'
    + 'html body.kite-clean #kiteClean .kiteMenu button,html body.kite-clean #kiteClean .screen-theme-menu button{text-align:left!important;background:var(--screen-alt,#edf1f6)!important;color:var(--ink,#243348)!important;border:1px solid var(--screen-edge,#c8d1de)!important;border-radius:6px!important;min-height:30px!important;padding:6px 10px!important;font-size:12px!important;font-weight:600!important;}'
    + 'html body.kite-clean #kiteClean .kiteMenu button[aria-checked=true],html body.kite-clean #kiteClean .screen-theme-menu button[aria-checked=true]{outline:2px solid #3785d5!important;outline-offset:-2px!important;background:var(--screen-surface,#fff)!important;}'
    + 'html body.kite-clean #kiteSettingsPop{position:fixed!important;inset:0!important;z-index:1300!important;background:rgba(15,23,42,.35)!important;display:flex!important;align-items:center!important;justify-content:center!important;padding:16px!important;}'
    + 'html body.kite-clean #kiteSettingsPop[hidden]{display:none!important;}'
    + 'html body.kite-clean .kiteSettingsSheet{position:relative!important;max-width:min(520px,96vw)!important;background:var(--screen-surface,#fff)!important;color:var(--ink,#243348)!important;border:1px solid var(--screen-edge,#c8d1de)!important;border-radius:10px!important;padding:12px 12px 10px!important;box-shadow:0 10px 28px rgba(15,23,42,.22)!important;}'
    + 'html body.kite-clean .kiteSettingsClose{position:absolute!important;right:8px!important;top:6px!important;min-width:28px!important;min-height:28px!important;border:0!important;background:transparent!important;color:var(--ink,#243348)!important;font-size:16px!important;}'
    + 'html body.kite-clean #kiteSettingsPop .manual-trail-bar,html body.kite-clean .manual-trail-bar.kite-settings-open{display:flex!important;flex-wrap:wrap!important;gap:8px!important;align-items:center!important;background:transparent!important;border:0!important;padding:4px 0!important;}'
    + 'html body.kite-clean #kiteSettingsPop .manual-trail-bar label,html body.kite-clean .manual-trail-bar.kite-settings-open label{font-size:12px!important;font-weight:600!important;color:var(--ink,#243348)!important;display:inline-flex!important;align-items:center!important;gap:4px!important;}'
    + 'html body.kite-clean #kiteSettingsPop .manual-trail-bar label,html body.kite-clean #kiteSettingsPop .manual-trail-bar select,html body.kite-clean #kiteSettingsPop .manual-trail-bar input,html body.kite-clean #kiteSettingsPop .manual-trail-bar button,html body.kite-clean .manual-trail-bar.kite-settings-open label,html body.kite-clean .manual-trail-bar.kite-settings-open select,html body.kite-clean .manual-trail-bar.kite-settings-open input,html body.kite-clean .manual-trail-bar.kite-settings-open button{background:var(--screen-alt,#edf1f6)!important;color:var(--ink,#243348)!important;border:1px solid var(--screen-edge,#c8d1de)!important;}'
    + 'html body.kite-clean dialog.mtm-dialog{display:block!important;}'
    + 'html body.kite-clean dialog.mtm-dialog:not([open]){display:none!important;}'
    + 'html body.kite-clean .kiteLimit{display:inline-flex!important;align-items:center!important;gap:4px!important;min-width:0!important;margin:0!important;color:#1f2937!important;}'
    + 'html body.kite-clean .kiteRow .kiteOrderType{display:inline-block!important;visibility:visible!important;opacity:1!important;height:26px!important;min-width:76px!important;max-width:none!important;padding:0 6px!important;font-size:12px!important;font-weight:650!important;line-height:24px!important;border:1px solid #c5ced8!important;border-radius:2px!important;background:#fff!important;color:#1f2937!important;-webkit-appearance:auto!important;appearance:auto!important;}'
    + 'html body.kite-clean .kiteRow .kiteOrderType option{color:#1f2937!important;background:#fff!important;font-size:12px!important;}'
    + 'html body.kite-clean .kiteLimitPrice{box-sizing:border-box!important;width:72px!important;height:26px!important;padding:0 6px!important;font-size:12px!important;font-weight:650!important;border:1px solid #c5ced8!important;border-radius:2px!important;background:#fff!important;color:#1f2937!important;}'
    + 'html body.kite-clean .kiteLimitPrice.is-disabled,html body.kite-clean .kiteLimitPrice:disabled{opacity:.45!important;}'
    + 'html body.kite-clean .kiteLimitPrice[hidden]{display:none!important;}'
    + 'html body.kite-clean #kiteCharts .grid>.panel,html body.kite-clean #kiteCharts #charts>.chart-card{display:flex!important;flex-direction:column!important;height:100%!important;min-height:0!important;align-items:stretch!important;}'
    + 'html body.kite-clean #kiteCharts .grid>.panel>.chart,html body.kite-clean #kiteCharts #charts .chart-pane{flex:1 1 auto!important;min-height:0!important;height:auto!important;width:100%!important;}'
    + 'html body.kite-clean #kiteCharts #charts .chart-head,html body.kite-clean #kiteCharts #charts .chart-foot{flex:0 0 auto!important;}'
    + 'html body.kite-clean #kiteCharts .panel>.panelTop,html body.kite-clean #kiteCharts .panel>.ohlc{top:4px!important;min-height:14px!important;line-height:1.2!important;}';
  document.body.appendChild(late);
  window.fitKiteCharts = fitKiteCharts;
  parkSummary();
})();
