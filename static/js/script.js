const $ = (id) => document.getElementById(id);
let savedEvents = [];
let savedHomePostalCode = '';

function setMessage(id, text, isError = false) {
  $(id).textContent = text;
  $(id).classList.toggle('error', isError);
}
function num(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
function normaliseEvent(raw) {
  const ai = raw.ai_scores || raw.AI_Scores || {};
  const career = num(raw.career_relevance ?? ai.career_relevance);
  const learning = num(raw.learning_value ?? ai.learning_value);
  const networking = num(raw.networking_value ?? ai.networking_value);
  const scores = [career, learning, networking];
  const score = num(raw.event_value ?? raw.total_value ?? ai.total_value) ?? (scores.every(v => v !== null) ? scores.reduce((a, b) => a + b, 0) : null);
  return {
    name: raw.event_name || 'Untitled event',
    description: raw.event_description || '',
    recommendation: String(raw.recommendation || 'UNKNOWN').toUpperCase(),
    reason: raw.reason || '',
    aiReasoning: raw.ai_reasoning || '',
    score, career, learning, networking
  };
}
function badgeClass(rec) {
  return rec === 'MAYBE' ? 'maybe' : rec === 'SKIP' ? 'skip' : '';
}
function showResult(raw) {
  const event = normaliseEvent(raw);
  $('result-empty').hidden = true;
  $('result-data').hidden = false;
  $('result-label').textContent = 'ANALYSED';
  $('result-badge').textContent = event.recommendation;
  $('result-badge').className = 'result-badge ' + badgeClass(event.recommendation);
  $('result-score').textContent = event.score === null ? 'Score unavailable' : `${event.score}/15`;
  $('result-reason').textContent = event.reason;
  $('score-career').textContent = event.career === null ? '—' : `${event.career}/5`;
  $('score-learning').textContent = event.learning === null ? '—' : `${event.learning}/5`;
  $('score-networking').textContent = event.networking === null ? '—' : `${event.networking}/5`;
  $('ai-reason').textContent = event.aiReasoning;
}
function renderHistory() {
  const keyword = $('history-search').value.trim().toLowerCase();
  const filtered = savedEvents.map(normaliseEvent).filter(e => (e.name + ' ' + e.description).toLowerCase().includes(keyword)).reverse();
  $('event-count').textContent = `${savedEvents.length} event${savedEvents.length === 1 ? '' : 's'}`;
  const container = $('history-list');
  container.replaceChildren();
  if (!filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-history';
    empty.textContent = savedEvents.length ? 'No events match your search.' : 'Your analysed events will appear here. Start with an event on the left! ✿';
    container.append(empty);
    return;
  }
  filtered.forEach(event => {
    const card = document.createElement('article');
    card.className = 'history-item';
    const top = document.createElement('div'); top.className = 'history-top';
    const name = document.createElement('strong'); name.textContent = event.name;
    const score = document.createElement('span'); score.className = 'history-score'; score.textContent = event.score === null ? '—' : `${event.score}/15`;
    top.append(name, score);
    const description = document.createElement('p'); description.textContent = event.description.length > 130 ? event.description.slice(0, 130) + '…' : event.description;
    const bottom = document.createElement('div'); bottom.className = 'history-bottom';
    const badge = document.createElement('span'); badge.className = 'mini-tag ' + badgeClass(event.recommendation); badge.textContent = event.recommendation;
    bottom.append(badge);
    card.append(top, description, bottom);
    container.append(card);
  });
}
async function api(path, method = 'GET', data) {
  const response = await fetch(path, {
    method,
    headers: data ? {'Content-Type': 'application/json'} : {},
    body: data ? JSON.stringify(data) : undefined
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed.');
  return result;
}
function selectTab(which) {
  ['history', 'profile'].forEach(tab => {
    const active = tab === which;
    $('tab-' + tab).classList.toggle('selected', active);
    $('tab-' + tab).setAttribute('aria-selected', String(active));
    $(tab + '-panel').hidden = !active;
  });
}
$('tab-history').addEventListener('click', () => selectTab('history'));
$('tab-profile').addEventListener('click', () => selectTab('profile'));
$('history-search').addEventListener('input', renderHistory);

$('event-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const button = $('analyse-button');
  button.disabled = true;
  $('result-data').hidden = true;
  $('result-empty').hidden = false;
  $('result-label').textContent = 'ANALYSING';
  renderTravelEstimate(null);
  setMessage('form-message', 'Analysing your event...');
  try {
    const result = await api('/api/analyse', 'POST', {
      event_name: $('event-name').value.trim(),
      event_description: $('event-description').value.trim(),
      venue_name: $('venue-name').value.trim(),
      venue_address: $('venue-address').value.trim(),
      workload: document.querySelector('input[name="workload"]:checked').value,
      travel: collectTravelInputs()
    });
    showResult(result.event);
    renderTravelEstimate(result.travel);
    savedEvents = result.events || [...savedEvents, result.event];
    renderHistory();
    setMessage('form-message', '✓ Recommendation generated and saved!');
  } catch (err) {
    $('result-data').hidden = true;
    $('result-empty').hidden = false;
    $('result-label').textContent = 'ANALYSIS FAILED';
    renderTravelEstimate(null);
    setMessage('form-message', err.message, true);
  }
  finally { button.disabled = false; }
});

$('profile-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  setMessage('profile-message', 'Saving profile...');
  try {
    const result = await api('/api/profile', 'POST', {
      field_of_study: $('study-field').value.trim(),
      interests: $('interests').value.split(',').map(s => s.trim()).filter(Boolean),
      home_postal_code: $('home-postal-code').value.trim()
    });
    savedHomePostalCode = result.profile.home_postal_code || '';
    $('home-postal-code').value = savedHomePostalCode;
    updateGeoVisibility();
    setMessage('profile-message', '✓ Profile saved!');
  } catch (err) { setMessage('profile-message', err.message, true); }
});
/*saved information to be loaded */
async function loadState() {
  try {
    const state = await api('/api/state');
    const profile = state.profile || {};
    $('study-field').value = profile.field_of_study || '';
    $('interests').value = Array.isArray(profile.interests) ? profile.interests.join(', ') : '';
    savedHomePostalCode = profile.home_postal_code || '';
    $('home-postal-code').value = savedHomePostalCode;
    updateGeoVisibility();
    savedEvents = state.events || [];
    renderHistory();
  } catch (err) { setMessage('form-message', err.message, true); }
}
loadState();


// filtering, event details annd analytics
(() => {
  'use strict';

  const byId = (id) => document.getElementById(id);
  const historyPanel = byId('history-panel');
  const profilePanel = byId('profile-panel');
  const tabBar = document.querySelector('.tab-bar');
  const rightPanel = document.querySelector('.right-panel');
  if (!historyPanel || !profilePanel || !tabBar || !rightPanel) return;

  // Additional filter controls, alongside the existing keyword search.
  const filters = document.createElement('div');
  filters.className = 'ew-filter-row';
  filters.innerHTML = `
    <label class="ew-filter-field" for="ew-recommendation-filter">
      Recommendation
      <select id="ew-recommendation-filter">
        <option value="ALL">All recommendations</option>
        <option value="ATTEND">ATTEND</option>
        <option value="MAYBE">MAYBE</option>
        <option value="SKIP">SKIP</option>
      </select>
    </label>
    <label class="ew-filter-field" for="ew-min-score">
      Minimum score (out of 15)
      <input id="ew-min-score" type="number" min="0" max="15" step="1" value="0">
    </label>
    <button id="ew-clear-filters" class="ew-clear-button" type="button">Clear filters</button>`;
  byId('history-search').insertAdjacentElement('afterend', filters);

  // Third tab, next to existing History and Profile tabs.
  const analyticsTab = document.createElement('button');
  analyticsTab.type = 'button';
  analyticsTab.id = 'tab-analytics';
  analyticsTab.className = 'tab';
  analyticsTab.setAttribute('role', 'tab');
  analyticsTab.setAttribute('aria-selected', 'false');
  analyticsTab.setAttribute('aria-controls', 'analytics-panel');
  analyticsTab.textContent = '▤ Analytics';
  tabBar.append(analyticsTab);

  const analyticsPanel = document.createElement('section');
  analyticsPanel.id = 'analytics-panel';
  analyticsPanel.hidden = true;
  analyticsPanel.setAttribute('role', 'tabpanel');
  analyticsPanel.setAttribute('aria-labelledby', 'tab-analytics');
  analyticsPanel.innerHTML = `
    <div class="section-heading"><div><span class="eyebrow">YOUR EVENTS AT A GLANCE</span>
      <h2>Event analytics</h2></div></div>
    <div id="ew-analytics-content" aria-live="polite"></div>`;
  rightPanel.insertBefore(analyticsPanel, rightPanel.querySelector('.panel-footer'));

  // A reusable detail dialog. All event data is written as text, never HTML.
  const overlay = document.createElement('div');
  overlay.id = 'ew-detail-overlay';
  overlay.className = 'ew-overlay';
  overlay.hidden = true;
  overlay.innerHTML = `
    <div class="ew-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="ew-detail-title" tabindex="-1">
      <div class="ew-detail-top"><span class="eyebrow">ANALYSED EVENT</span>
        <button id="ew-detail-close" type="button" aria-label="Close event details">✕</button></div>
      <h2 id="ew-detail-title"></h2>
      <div id="ew-detail-body"></div>
    </div>`;
  document.body.append(overlay);
  let previousFocus = null;
  const closeDetails = () => {
    overlay.hidden = true;
    document.body.classList.remove('ew-dialog-open');
    if (previousFocus && previousFocus.isConnected) previousFocus.focus();
  };
  byId('ew-detail-close').addEventListener('click', closeDetails);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) closeDetails();
  });
  document.addEventListener('keydown', (event) => {
    if (overlay.hidden) return;
    if (event.key === 'Escape') closeDetails();
    if (event.key === 'Tab') {
      // Only one focusable control inside the dialog.
      event.preventDefault();
      byId('ew-detail-close').focus();
    }
  });

  const addText = (parent, label, value) => {
    if (value === undefined || value === null || value === '') return;
    const section = document.createElement('div');
    section.className = 'ew-detail-field';
    const heading = document.createElement('strong');
    heading.textContent = label;
    const content = document.createElement('p');
    content.textContent = String(value);
    section.append(heading, content);
    parent.append(section);
  };

  function openDetails(raw) {
    const e = normaliseEvent(raw);
    previousFocus = document.activeElement;
    byId('ew-detail-title').textContent = e.name;
    const container = byId('ew-detail-body');
    container.replaceChildren();
    const scoreLine = document.createElement('div');
    scoreLine.className = 'ew-detail-summary';
    const badge = document.createElement('span');
    badge.className = 'mini-tag ' + badgeClass(e.recommendation);
    badge.textContent = e.recommendation;
    const total = document.createElement('strong');
    total.textContent = e.score === null ? 'Score unavailable' : `${e.score}/15`;
    scoreLine.append(badge, total);
    container.append(scoreLine);

    const rawAi = raw.ai_scores || raw.AI_Scores || {};
    addText(container, 'Description', e.description);
    addText(container, 'Venue', raw.venue_name);
    addText(container, 'Address', raw.venue_address);
    addText(container, 'Destination postal code', raw.destination_postal_code);
    addText(container, 'Category', raw.event_category ?? raw.category ?? rawAi.event_category);
    addText(container, 'Workload', raw.workload);
    addText(container, 'Priority', raw.priority ?? raw.event_priority);
    addText(container, 'Career relevance', e.career === null ? 'Not available' : `${e.career}/5`);
    addText(container, 'Learning value', e.learning === null ? 'Not available' : `${e.learning}/5`);
    addText(container, 'Networking value', e.networking === null ? 'Not available' : `${e.networking}/5`);
    addText(container, 'Recommendation reason', e.reason);
    addText(container, 'AI reasoning', e.aiReasoning);
    const journey = document.createElement('section');
    journey.className = 'geo-travel-result';
    const journeyHeading = document.createElement('h3');
    journeyHeading.textContent = 'Estimate when analysed';
    const journeyContent = document.createElement('div');
    renderTravelContent(journeyContent, raw.travel_snapshot, true);
    journey.append(journeyHeading, journeyContent);
    container.append(journey);

    overlay.hidden = false;
    document.body.classList.add('ew-dialog-open');
    byId('ew-detail-close').focus();
  }

  const scoreAsNumber = (score) => (typeof score === 'number' && Number.isFinite(score) ? score : null);
  const labelFor = (raw) => String(raw.event_category ?? raw.category ?? raw.ai_scores?.event_category ?? raw.AI_Scores?.event_category ?? 'Uncategorised').trim() || 'Uncategorised';
  const workloadFor = (raw) => {
    const w = String(raw.workload || '').trim().toLowerCase();
    return w === 'low' ? 'Low' : w === 'medium' ? 'Medium' : w === 'high' ? 'High' : 'Other';
  };

  // Preserve savedEvents, normaliseEvent and API loading from the original script.
  // Extend the existing renderer so new records also appear immediately.
  renderHistory = function () {
    const keyword = byId('history-search').value.trim().toLocaleLowerCase();
    const recommendation = byId('ew-recommendation-filter').value;
    const minInput = byId('ew-min-score');
    const minScore = Math.min(15, Math.max(0, Number(minInput.value) || 0));
    const records = savedEvents.map((raw) => ({ raw, event: normaliseEvent(raw) }));
    const matched = records.filter(({ raw, event }) => {
      const text = `${event.name} ${event.description} ${labelFor(raw)} ${event.reason}`.toLocaleLowerCase();
      return text.includes(keyword) &&
        (recommendation === 'ALL' || event.recommendation === recommendation) &&
        (event.score !== null && event.score >= minScore || minScore === 0 && event.score === null);
    }).reverse();
    byId('event-count').textContent = `${savedEvents.length} event${savedEvents.length === 1 ? '' : 's'}`;
    const list = byId('history-list');
    list.replaceChildren();
    if (!matched.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-history';
      empty.textContent = savedEvents.length ? 'No events match your filters.' : 'Your analysed events will appear here. Start with an event on the left!';
      list.append(empty);
    }
    for (const {raw, event} of matched) {
      const card = document.createElement('article');
      card.className = 'history-item';
      const top = document.createElement('div');
      top.className = 'history-top';
      const name = document.createElement('strong');
      name.textContent = event.name;
      const score = document.createElement('span');
      score.className = 'history-score';
      score.textContent = event.score === null ? '—' : `${event.score}/15`;
      top.append(name, score);
      const desc = document.createElement('p');
      desc.textContent = event.description.length > 130 ? `${event.description.slice(0, 130)}…` : event.description;
      const bottom = document.createElement('div');
      bottom.className = 'history-bottom';
      const badge = document.createElement('span');
      badge.className = 'mini-tag ' + badgeClass(event.recommendation);
      badge.textContent = event.recommendation;
      const details = document.createElement('button');
      details.type = 'button';
      details.className = 'ew-detail-button';
      details.textContent = 'View details ↗';
      details.addEventListener('click', () => openDetails(raw));
      bottom.append(badge, details);
      card.append(top, desc, bottom);
      const venueDetails = [raw.venue_name, raw.venue_address, raw.destination_postal_code].filter(Boolean);
      if (venueDetails.length) {
        const venue = document.createElement('p');
        venue.className = 'geo-history-venue';
        venue.textContent = venueDetails.join(' · ');
        card.insertBefore(venue, bottom);
      }
      list.append(card);
    }
    renderAnalytics();
  };

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = String(content);
    return node;
  }

  function makeSection(title) {
    const s = element('section', 'ew-analytics-section');
    s.append(element('h3', '', title));
    return s;
  }

  function renderAnalytics() {
    const root = byId('ew-analytics-content');
    root.replaceChildren();
    const records = savedEvents.map((raw) => ({ raw, value: normaliseEvent(raw) }));
    if (!records.length) {
      root.append(element('p', 'empty-history', 'Analyse an event to see your analytics here.'));
      return;
    }
    const total = records.length;
    const counts = {ATTEND: 0, MAYBE: 0, SKIP: 0};
    for (const {value} of records) if (Object.hasOwn(counts, value.recommendation)) counts[value.recommendation]++;
    const attendance = total ? (counts.ATTEND / total * 100).toFixed(1) : '0.0';
    const overview = makeSection('Overview');
    const stats = element('div', 'ew-stat-grid');
    [['Analysed events', total], ['Attendance rate', `${attendance}%`], ['ATTEND', counts.ATTEND], ['MAYBE', counts.MAYBE], ['SKIP', counts.SKIP]].forEach(([label, val]) => {
      const stat = element('div', 'ew-stat');
      stat.append(element('span', '', label), element('strong', '', val));
      stats.append(stat);
    });
    overview.append(stats);
    root.append(overview);

    const category = makeSection('Category distribution');
    const categoryCounts = new Map();
    records.forEach(({raw}) => {
      const key = labelFor(raw);
      categoryCounts.set(key, (categoryCounts.get(key) || 0) + 1);
    });
    Array.from(categoryCounts.entries()).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0])).forEach(([name, count]) => {
      const row = element('div', 'ew-category-row');
      row.append(element('span', '', name), element('strong', '', `${count} · ${(count / total * 100).toFixed(1)}%`));
      const track = element('div', 'ew-bar-track');
      const bar = element('div', 'ew-bar-fill');
      bar.style.width = `${count / total * 100}%`;
      track.append(bar);
      category.append(row, track);
    });
    root.append(category);

    const workload = makeSection('Workload vs recommendation');
    const table = element('table', 'ew-matrix');
    const thead = document.createElement('thead');
    const header = document.createElement('tr');
    ['Workload', 'ATTEND', 'MAYBE', 'SKIP', 'Total'].forEach((label) => header.append(element('th', '', label)));
    thead.append(header);
    table.append(thead);
    const tbody = document.createElement('tbody');
    ['Low', 'Medium', 'High'].forEach((w) => {
      const matching = records.filter(({raw}) => workloadFor(raw) === w);
      const tr = document.createElement('tr');
      tr.append(element('th', '', w));
      ['ATTEND', 'MAYBE', 'SKIP'].forEach((rec) => tr.append(element('td', '', matching.filter(({value}) => value.recommendation === rec).length)));
      tr.append(element('td', '', matching.length));
      tbody.append(tr);
    });
    table.append(tbody);
    const scroll = element('div', 'ew-table-scroll');
    scroll.append(table);
    workload.append(scroll);
    root.append(workload);

    const averages = makeSection('Average scores');
    const fields = [['Career relevance', 'career'], ['Learning value', 'learning'], ['Networking value', 'networking'], ['Total event value', 'score']];
    for (const [label, key] of fields) {
      const scores = records.map(({value}) => scoreAsNumber(value[key])).filter((n) => n !== null);
      const average = scores.length ? (scores.reduce((a,b) => a+b, 0) / scores.length).toFixed(1) : '—';
      const maximum = key === 'score' ? 15 : 5;
      const row = element('div', 'ew-average-row');
      row.append(element('span', '', label), element('strong', '', `${average} / ${maximum}`));
      averages.append(row);
    }
    root.append(averages);
  }

  // Keep the existing two tabs working, and add a third without changing original JS.
  const originalSelectTab = selectTab;
  selectTab = function (which) {
    if (which === 'analytics') {
      historyPanel.hidden = true;
      profilePanel.hidden = true;
      analyticsPanel.hidden = false;
      ['history', 'profile'].forEach((name) => {
        const tab = byId(`tab-${name}`);
        tab.classList.remove('selected');
        tab.setAttribute('aria-selected', 'false');
      });
      analyticsTab.classList.add('selected');
      analyticsTab.setAttribute('aria-selected', 'true');
      renderAnalytics();
    } else {
      originalSelectTab(which);
      analyticsPanel.hidden = true;
      analyticsTab.classList.remove('selected');
      analyticsTab.setAttribute('aria-selected', 'false');
    }
  };
  analyticsTab.addEventListener('click', () => selectTab('analytics'));

  byId('ew-recommendation-filter').addEventListener('change', renderHistory);
  byId('ew-min-score').addEventListener('input', renderHistory);
  byId('ew-clear-filters').addEventListener('click', () => {
    byId('history-search').value = '';
    byId('ew-recommendation-filter').value = 'ALL';
    byId('ew-min-score').value = '0';
    renderHistory();
  });

  // Runs immediately for initial display. The original script's async loadState()
  // calls the enhanced renderHistory() when MongoDB data finishes loading.
  renderHistory();
})();

/* new geolocation fields */
function updateGeoVisibility() {
  const originChoice = $('geo-origin-choice');
  const hasSavedHome = /^[0-9]{6}$/.test(savedHomePostalCode);
  originChoice.querySelector('option[value="home"]').disabled = !hasSavedHome;
  if (originChoice.value === 'home' && !hasSavedHome) {
    originChoice.value = 'skip';
  }
  const choice = originChoice.value;
  const enabled = choice !== 'skip';
  $('geo-fields').hidden = !enabled;
  $('geo-alternate-field').hidden = choice !== 'alternate';
  const hint = $('geo-home-message');
  hint.hidden = choice !== 'home';
  if (choice === 'home') {
    hint.textContent = `Using your saved home postal code: ${savedHomePostalCode}`;
  }
  $('geo-origin-postal').required = choice === 'alternate';
  $('geo-destination-postal').required = enabled;
  $('geo-event-start').required = enabled;
}
$('geo-origin-choice').addEventListener('change', updateGeoVisibility);
updateGeoVisibility();

function collectTravelInputs() {
  const choice = $('geo-origin-choice').value;
  if (choice === 'skip') return { origin_choice: 'skip' };
  const postal = $('geo-destination-postal').value.trim();
  const start = $('geo-event-start').value;
  const origin = $('geo-origin-postal').value.trim();
  if (choice === 'home' && !/^[0-9]{6}$/.test(savedHomePostalCode)) {
    throw new Error('Save a 6-digit home postal code in My Profile, or choose another starting point.');
  }
  if (choice === 'alternate' && !/^[0-9]{6}$/.test(origin)) {
    throw new Error('Enter a valid 6-digit starting postal code.');
  }
  if (!/^[0-9]{6}$/.test(postal)) {
    throw new Error('Enter a valid 6-digit event location postal code.');
  }
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(start)) {
    throw new Error('Choose the event start date and time (Singapore time).');
  }
  return {
    origin_choice: choice,
    ...(choice === 'alternate' ? { origin_postal_code: origin } : {}),
    destination_postal_code: postal,
    event_start: start + ':00+08:00'
  };
}

function formatGeoNumber(value, unit) {
  const n = Number(value);
  return value === null || value === undefined || !Number.isFinite(n)
    ? 'Unavailable' : `${Number(n.toFixed(1))} ${unit}`;
}
function formatGeoDate(value) {
  if (!value) return 'Unavailable';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return 'Unavailable';
  return new Intl.DateTimeFormat('en-SG', {
    timeZone: 'Asia/Singapore', day: 'numeric', month: 'short', year: 'numeric',
    hour: 'numeric', minute: '2-digit', hour12: true
  }).format(d);
}
function renderTravelEstimate(travel) {
  const section = $('geo-travel-result');
  const content = $('geo-travel-content');
  section.hidden = !travel || travel.status === 'SKIPPED';
  renderTravelContent(content, travel);
}

function renderTravelContent(content, travel, historical = false) {
  content.replaceChildren();
  if (!travel || travel.status === 'SKIPPED') {
    if (historical) {
      const message = document.createElement('p');
      message.className = 'geo-hint';
      message.textContent = travel
        ? 'Travel planning was skipped for this event.'
        : 'Travel details were not saved for this event.';
      content.append(message);
    }
    return;
  }
  const add = (name, value) => {
    const line = document.createElement('div');
    line.className = 'geo-result-line';
    const label = document.createElement('span');
    label.textContent = name;
    const valueText = document.createElement('strong');
    valueText.textContent = value;
    line.append(label, valueText);
    content.append(line);
  };
  if (travel.status !== 'AVAILABLE') {
    const message = document.createElement('p');
    message.className = 'geo-unavailable';
    message.textContent = travel.error_message || 'Journey estimate is unavailable.';
    content.append(message);
    return;
  }
  const timeCards = document.createElement('div');
  timeCards.className = 'geo-time-cards';
  for (const [labelText, value] of [
    ['Suggested leave-by', travel.recommended_departure],
    ['Estimated arrival', travel.estimated_arrival]
  ]) {
    const card = document.createElement('div');
    card.className = 'geo-time-card';
    const label = document.createElement('span');
    label.textContent = labelText;
    const time = document.createElement('strong');
    time.textContent = formatGeoDate(value);
    card.append(label, time);
    timeCards.append(card);
  }
  content.append(timeCards);
  const note = document.createElement('p');
  note.className = 'geo-hint';
  note.textContent = historical
    ? 'Saved estimate in Singapore time. Transit schedules may have changed.'
    : 'Estimated times use Singapore time (UTC+08:00).';
  content.append(note);
  add('Travel mode', 'Public transport (OneMap)');
  add('Distance', formatGeoNumber(travel.distance_km, 'km'));
  add('Duration', formatGeoNumber(travel.duration_minutes, 'min'));
  if (!historical) {
    const heading = document.createElement('h4');
    heading.textContent = 'Journey steps';
    content.append(heading);
    if (Array.isArray(travel.legs) && travel.legs.length) {
      const steps = document.createElement('ol');
      steps.className = 'geo-journey-steps';
      const modes = {WALK: 'Walk', BUS: 'Bus', SUBWAY: 'MRT', RAIL: 'Rail', TRAM: 'Tram', FERRY: 'Ferry'};
      travel.legs.forEach(leg => {
        if (!leg || typeof leg !== 'object') return;
        const step = document.createElement('li');
        const title = document.createElement('strong');
        title.textContent = (modes[leg.mode] || 'Travel') + (leg.route ? ` · ${leg.route}` : '');
        const places = document.createElement('p');
        places.textContent = `${leg.from_name || 'Start unavailable'} → ${leg.to_name || 'End unavailable'}`;
        const measurements = document.createElement('small');
        measurements.textContent = `${formatGeoNumber(leg.duration_minutes, 'min')} · ${formatGeoNumber(leg.distance_km, 'km')}`;
        step.append(title, places, measurements);
        steps.append(step);
      });
      content.append(steps);
      const privacy = document.createElement('p');
      privacy.className = 'geo-hint';
      privacy.textContent = 'Journey steps are shown for this analysis only and are not saved in History.';
      content.append(privacy);
    } else {
      const message = document.createElement('p');
      message.className = 'geo-hint';
      message.textContent = 'Step-by-step journey details are unavailable for this estimate.';
      content.append(message);
    }
  }
  if (travel.arrival_buffer_minutes !== null) {
    add('Arrival buffer', formatGeoNumber(travel.arrival_buffer_minutes, 'min'));
  }
  if (travel.preferred_travel_limit_minutes != null) {
    add('Preferred travel limit', formatGeoNumber(travel.preferred_travel_limit_minutes, 'min'));
  }
  if (travel.feasibility === 'LONG_JOURNEY') {
    const warning = document.createElement('p');
    warning.className = 'geo-warning';
    warning.textContent = 'This is a long journey compared with the preferred travel limit.';
    content.append(warning);
  }
  const warnings = Array.isArray(travel.warning_codes) ? travel.warning_codes : [];
  if (warnings.includes('EVENT_START_MISSED') || warnings.includes('BUFFER_MISSED')) {
    const warning = document.createElement('p');
    warning.className = 'geo-warning';
    warning.textContent = warnings.includes('EVENT_START_MISSED')
      ? 'Estimated arrival is after the event starts.'
      : 'Estimated arrival may miss the recommended early-arrival buffer.';
    content.append(warning);
  }
}
