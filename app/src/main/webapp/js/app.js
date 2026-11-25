'use strict';

/* =====================================================================
   Restaurant Review Platform - front end
   Plain JavaScript, no libraries. It talks to the REST API with fetch().
   The page is served by the same WAR as the API, so the address is
   relative ("api/...") and no CORS setup is needed.

   Security notes:
   - Text that comes from users (reviews, names) is only ever inserted with
     textContent / text nodes (see h()), never with innerHTML, so it cannot
     inject HTML or scripts.
   - The JWT is kept in sessionStorage (it disappears when the tab closes).
   ===================================================================== */

const API = 'api';
const PAGE_SIZE = 20;

const state = {
    token: null,
    user: null,                 // { id, username }
    restaurants: [],
    favorites: new Set(),       // ids of the restaurants saved by the logged user
    ratings: new Map(),         // restaurantId -> Promise of the rating summary
    view: 'all',                // 'all' | 'favorites'
    shown: PAGE_SIZE,
    firstLoad: true,
};

/* ---------------------------------------------------------------- helpers */

/** Creates an element. Text children are added as text nodes (safe). */
function h(tag, props, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
        if (value === null || value === undefined || value === false) continue;
        if (key === 'class') node.className = value;
        else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
        else if (value === true) node.setAttribute(key, '');
        else node.setAttribute(key, value);
    }
    for (const child of children.flat()) {
        if (child === null || child === undefined || child === false) continue;
        node.append(child.nodeType ? child : document.createTextNode(String(child)));
    }
    return node;
}

const $ = (selector) => document.querySelector(selector);

function storageGet(key) {
    try { return sessionStorage.getItem(key); } catch (e) { return null; }
}
function storageSet(key, value) {
    try {
        if (value === null) sessionStorage.removeItem(key);
        else sessionStorage.setItem(key, value);
    } catch (e) { /* storage not available: the session just will not survive a reload */ }
}

class ApiError extends Error {
    constructor(status, message) {
        super(message);
        this.status = status;
    }
}

/** Calls the API. With auth:true it sends the JWT and handles an expired session. */
async function api(path, { method = 'GET', body, auth = false } = {}) {
    const headers = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (auth && state.token) headers.Authorization = 'Bearer ' + state.token;

    let response;
    try {
        response = await fetch(`${API}/${path}`, {
            method,
            headers,
            body: body === undefined ? undefined : JSON.stringify(body),
        });
    } catch (e) {
        throw new ApiError(0, 'Cannot reach the server. Check that it is running and try again.');
    }

    if (response.status === 204) return null;

    let data = null;
    try { data = await response.json(); } catch (e) { /* empty or not JSON */ }

    if (!response.ok) {
        let message = 'Something went wrong (error ' + response.status + ').';
        if (data && data.error) message = data.error;
        else if (data && Array.isArray(data.errors)) message = data.errors.join('. ');

        if (response.status === 401 && auth && state.token) {
            signOut();
            openAuth('login', 'Your session ended. Sign in again to continue.');
        }
        throw new ApiError(response.status, message);
    }
    return data;
}

function formatDate(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function stars(n) {
    return h('span', { class: 'stars', role: 'img', 'aria-label': `${n} out of 5` },
        '★'.repeat(n), h('span', { class: 'off' }, '★'.repeat(5 - n)));
}

function price(n) {
    return h('span', { class: 'price', role: 'img', 'aria-label': `Price level ${n} of 4` },
        h('span', { class: 'on' }, '$'.repeat(n)), h('span', { class: 'off' }, '$'.repeat(4 - n)));
}

let toastTimer = null;
function toast(message) {
    const node = $('#toast');
    node.textContent = message;
    // popover puts the message above open dialogs; old browsers just skip it
    if (typeof node.showPopover === 'function' && !node.matches(':popover-open')) node.showPopover();
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        if (typeof node.hidePopover === 'function' && node.matches(':popover-open')) node.hidePopover();
    }, 3200);
}

/* ---------------------------------------------------------------- session */

function setSession(token, user) {
    state.token = token;
    state.user = user;
    storageSet('rr_token', token);
    storageSet('rr_user', user ? JSON.stringify(user) : null);
    renderAccount();
}

function signOut() {
    state.favorites = new Set();
    if (state.view === 'favorites') state.view = 'all';
    setSession(null, null);
    render();
}

async function loadFavorites() {
    if (!state.user) return;
    try {
        const list = await api(`users/${state.user.id}/favorites`, { auth: true });
        state.favorites = new Set(list.map((r) => r.id));
    } catch (e) { /* the list still works without the hearts */ }
}

async function signIn(username, password) {
    const data = await api('auth/login', { method: 'POST', body: { username, password } });
    setSession(data.token, { id: data.user.id, username: data.user.username });
    await loadFavorites();
    render();
}

function renderAccount() {
    const box = $('#account');
    box.replaceChildren();
    if (state.user) {
        box.append(
            h('span', {}, 'Signed in as ', h('strong', {}, state.user.username)),
            h('button', { type: 'button', class: 'btn-link', onclick: () => { signOut(); toast('Signed out.'); } }, 'Sign out'));
    } else {
        box.append(h('button', { type: 'button', class: 'btn', onclick: () => openAuth('login') }, 'Sign in'));
    }
    $('#tab-favorites').hidden = !state.user;
}

/* ------------------------------------------------------------------ list */

async function loadRestaurants() {
    const list = $('#list');
    $('#count').textContent = 'Loading restaurants...';
    try {
        const data = await api('restaurants');
        state.restaurants = data.slice().sort((a, b) => a.name.localeCompare(b.name));
        fillFilterOptions();
        render();
    } catch (e) {
        $('#count').textContent = '';
        list.replaceChildren(h('li', { class: 'empty' },
            h('p', {}, e.message),
            h('button', { type: 'button', class: 'btn', onclick: loadRestaurants }, 'Try again')));
    }
}

function fillFilterOptions() {
    const fill = (selector, values) => {
        const select = $(selector);
        const current = select.value;
        select.replaceChildren(h('option', { value: '' }, 'Any'),
            ...[...new Set(values)].sort((a, b) => a.localeCompare(b)).map((v) => h('option', { value: v }, v)));
        select.value = current;
    };
    fill('#f-cuisine', state.restaurants.map((r) => r.cuisine));
    fill('#f-city', state.restaurants.map((r) => r.city));
}

function filteredRestaurants() {
    const q = $('#f-q').value.trim().toLowerCase();
    const cuisine = $('#f-cuisine').value;
    const city = $('#f-city').value;
    return state.restaurants.filter((r) =>
        (state.view === 'all' || state.favorites.has(r.id))
        && (!cuisine || r.cuisine === cuisine)
        && (!city || r.city === city)
        && (!q || `${r.name} ${r.cuisine} ${r.city}`.toLowerCase().includes(q)));
}

function fetchRating(id) {
    if (!state.ratings.has(id)) {
        state.ratings.set(id, api(`restaurants/${id}/rating`).catch((e) => { state.ratings.delete(id); throw e; }));
    }
    return state.ratings.get(id);
}

function ratingContent(summary) {
    if (!summary || summary.totalReviews === 0) return h('span', { class: 'none' }, 'No reviews yet');
    return [h('span', { class: 'star', 'aria-hidden': 'true' }, '★ '),
        summary.averageRating.toFixed(1), ' ',
        h('small', {}, `(${summary.totalReviews} ${summary.totalReviews === 1 ? 'review' : 'reviews'})`)];
}

function render() {
    const list = $('#list');
    const all = filteredRestaurants();
    const visible = all.slice(0, state.shown);
    const favoritesView = state.view === 'favorites';

    $('#tab-all').setAttribute('aria-current', favoritesView ? 'false' : 'page');
    $('#tab-favorites').setAttribute('aria-current', favoritesView ? 'page' : 'false');
    $('#page-title').textContent = favoritesView ? 'My favorites' : 'Restaurants';
    $('#page-lede').textContent = favoritesView
        ? 'The places you saved, in one list.'
        : 'Read what diners think, rate the places you have been to and save your favorites.';
    $('#count').textContent = all.length === 1 ? '1 restaurant' : `${all.length} restaurants`;
    list.classList.toggle('first-load', state.firstLoad);

    if (visible.length === 0) {
        list.replaceChildren(h('li', { class: 'empty' }, emptyMessage()));
        $('#more').replaceChildren();
        return;
    }

    list.replaceChildren(...visible.map((r, i) => entry(r, i)));
    state.firstLoad = false;

    const more = $('#more');
    more.replaceChildren();
    if (all.length > visible.length) {
        more.append(h('button', {
            type: 'button', class: 'btn',
            onclick: () => { state.shown += PAGE_SIZE; render(); },
        }, `Show more (${all.length - visible.length} left)`));
    }
}

function emptyMessage() {
    const filtering = $('#f-q').value || $('#f-cuisine').value || $('#f-city').value;
    if (filtering) {
        return [h('p', {}, 'No restaurant matches these filters.'),
            h('button', { type: 'button', class: 'btn-link', onclick: clearFilters }, 'Clear filters')];
    }
    if (state.view === 'favorites') {
        return h('p', {}, 'You have not saved any restaurant yet. Open one and choose Save to favorites.');
    }
    return h('p', {}, 'There are no restaurants yet. Use Add restaurant to create the first one.');
}

function clearFilters() {
    $('#f-q').value = '';
    $('#f-cuisine').value = '';
    $('#f-city').value = '';
    state.shown = PAGE_SIZE;
    render();
}

function entry(restaurant, index) {
    const ratingNode = h('span', { class: 'entry-rating' }, '...');
    fetchRating(restaurant.id)
        .then((summary) => ratingNode.replaceChildren(...[ratingContent(summary)].flat()))
        .catch(() => ratingNode.replaceChildren(h('span', { class: 'none' }, 'Rating unavailable')));

    const button = h('button', { type: 'button', class: 'entry', onclick: () => openDetail(restaurant) },
        h('span', { class: 'entry-name' }, restaurant.name,
            state.favorites.has(restaurant.id)
                ? h('span', { class: 'saved-mark', role: 'img', 'aria-label': 'Saved to favorites' }, '♥') : null),
        h('span', { class: 'entry-leader', 'aria-hidden': 'true' }),
        ratingNode,
        h('span', { class: 'entry-meta' }, `${restaurant.cuisine} in ${restaurant.city}`),
        h('span', { class: 'entry-price' }, price(restaurant.priceRange)));

    const li = h('li', {}, button);
    li.style.setProperty('--i', Math.min(index, 12));
    return li;
}

/* ---------------------------------------------------------------- dialogs */

function wireDialog(dialog) {
    dialog.addEventListener('click', (event) => {
        if (event.target === dialog || event.target.hasAttribute('data-close')) dialog.close();
    });
}
['#dlg-auth', '#dlg-add', '#dlg-detail'].forEach((selector) => wireDialog($(selector)));

function setBusy(form, busy) {
    form.querySelectorAll('button[type="submit"]').forEach((b) => { b.disabled = busy; });
}
function showError(form, message) {
    form.querySelector('.form-error').textContent = message || '';
}
function formData(form) {
    return Object.fromEntries(new FormData(form).entries());
}

/* ----- sign in / register ----- */

function openAuth(mode, notice) {
    const dialog = $('#dlg-auth');
    setAuthMode(mode);
    const box = $('#auth-notice');
    box.textContent = notice || '';
    box.hidden = !notice;
    document.querySelectorAll('#dlg-auth .form-error').forEach((e) => { e.textContent = ''; });
    if (!dialog.open) dialog.showModal();
}

function setAuthMode(mode) {
    const login = mode === 'login';
    $('#auth-title').textContent = login ? 'Sign in' : 'Create account';
    $('#seg-login').setAttribute('aria-selected', String(login));
    $('#seg-register').setAttribute('aria-selected', String(!login));
    $('#form-login').hidden = !login;
    $('#form-register').hidden = login;
}
$('#seg-login').addEventListener('click', () => setAuthMode('login'));
$('#seg-register').addEventListener('click', () => setAuthMode('register'));

$('#form-login').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const { username, password } = formData(form);
    if (!username.trim() || !password) { showError(form, 'Enter your username and password.'); return; }
    showError(form, '');
    setBusy(form, true);
    try {
        await signIn(username.trim(), password);
        form.reset();
        $('#dlg-auth').close();
        toast('Signed in.');
    } catch (e) {
        showError(form, e.status === 401 ? 'Wrong username or password.' : e.message);
    } finally {
        setBusy(form, false);
    }
});

$('#form-register').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const { username, email, password } = formData(form);
    showError(form, '');
    setBusy(form, true);
    try {
        await api('auth/register', { method: 'POST', body: { username: username.trim(), email: email.trim(), password } });
        await signIn(username.trim(), password);
        form.reset();
        $('#dlg-auth').close();
        toast('Account created. You are signed in.');
    } catch (e) {
        showError(form, e.status === 409 ? 'That username or email is already registered.' : e.message);
    } finally {
        setBusy(form, false);
    }
});

/* ----- add restaurant ----- */

$('#btn-add').addEventListener('click', () => {
    if (!state.user) { openAuth('login', 'Sign in to add a restaurant.'); return; }
    showError($('#form-add'), '');
    $('#dlg-add').showModal();
});

$('#form-add').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = formData(form);
    showError(form, '');
    setBusy(form, true);
    try {
        const created = await api('restaurants', {
            method: 'POST', auth: true,
            body: {
                name: data.name.trim(), cuisine: data.cuisine.trim(), city: data.city.trim(),
                address: data.address.trim(), priceRange: Number(data.priceRange),
            },
        });
        state.restaurants.push(created);
        state.restaurants.sort((a, b) => a.name.localeCompare(b.name));
        fillFilterOptions();
        render();
        form.reset();
        $('#dlg-add').close();
        toast(`${created.name} was added.`);
    } catch (e) {
        if (e.status === 401) { $('#dlg-add').close(); return; }
        showError(form, e.status === 409 ? 'That restaurant is already registered at this address.' : e.message);
    } finally {
        setBusy(form, false);
    }
});

/* ----- restaurant detail ----- */

async function openDetail(restaurant) {
    const dialog = $('#dlg-detail');
    const root = $('#detail');
    root.replaceChildren(h('h2', { id: 'detail-title' }, restaurant.name), h('p', { class: 'detail-info' }, 'Loading...'));
    if (!dialog.open) dialog.showModal();
    await refreshDetail(restaurant);
}

async function refreshDetail(restaurant) {
    const root = $('#detail');
    try {
        state.ratings.delete(restaurant.id);
        const [summary, reviews] = await Promise.all([
            fetchRating(restaurant.id),
            api(`reviews?restaurantId=${restaurant.id}`),
        ]);
        reviews.sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
        renderDetail(root, restaurant, summary, reviews);
    } catch (e) {
        root.replaceChildren(
            h('div', { class: 'dlg-head' }, h('h2', { id: 'detail-title' }, restaurant.name),
                h('button', { type: 'button', class: 'btn-close', 'data-close': true }, 'Close')),
            h('p', { class: 'form-error' }, e.message));
    }
}

$('#dlg-detail').addEventListener('close', () => render());   // refresh hearts and ratings in the list

function renderDetail(root, restaurant, summary, reviews) {
    const mine = state.user ? reviews.find((r) => r.userId === state.user.id) : null;

    const favoriteButton = h('button', {
        type: 'button', class: 'btn btn-fav',
        'aria-pressed': String(state.favorites.has(restaurant.id)),
        onclick: (event) => toggleFavorite(restaurant, event.currentTarget),
    }, state.favorites.has(restaurant.id) ? 'Saved to favorites' : 'Save to favorites');

    const counts = summary.ratingCounts || {};
    const bars = h('div', { class: 'bars' });
    for (let star = 5; star >= 1; star--) {
        const n = Number(counts[String(star)] || 0);
        const percent = summary.totalReviews ? Math.round((n / summary.totalReviews) * 100) : 0;
        const fill = h('i');
        fill.style.width = percent + '%';
        bars.append(h('span', {}, `${star} ${star === 1 ? 'star' : 'stars'}`), h('span', { class: 'bar' }, fill), h('span', { class: 'n' }, String(n)));
    }

    root.replaceChildren(
        h('div', { class: 'detail-head' },
            h('div', {},
                h('h2', { id: 'detail-title' }, restaurant.name),
                h('p', { class: 'detail-info' }, `${restaurant.cuisine} in ${restaurant.city}. ${restaurant.address}.`)),
            h('button', { type: 'button', class: 'btn-close', 'data-close': true }, 'Close')),
        h('div', { class: 'detail-actions' },
            price(restaurant.priceRange),
            state.user ? favoriteButton
                : h('button', { type: 'button', class: 'btn', onclick: () => openAuth('login', 'Sign in to save favorites and write reviews.') }, 'Sign in to save')),
        h('div', { class: 'rating-block' },
            h('div', { class: 'rating-big' },
                summary.totalReviews ? summary.averageRating.toFixed(1) : '-',
                h('small', {}, summary.totalReviews === 1 ? '1 review' : `${summary.totalReviews} reviews`)),
            bars),
        h('h3', { class: 'section-title' }, mine ? 'Your review' : 'Write a review'),
        mine ? h('div', { id: 'mine-slot' }, ownReview(restaurant, mine)) : newReviewBlock(restaurant),
        h('h3', { class: 'section-title' }, 'What diners say'),
        reviewList(reviews.filter((r) => !mine || r.id !== mine.id), !!mine));
}

function reviewList(reviews, hasMine) {
    if (reviews.length === 0) {
        return h('p', { class: 'empty' }, hasMine ? 'No other reviews yet.' : 'No reviews yet. Be the first to write one.');
    }
    return h('div', {}, reviews.map((r) => reviewItem(r, false)));
}

function reviewItem(review, isMine) {
    return h('article', { class: 'review' + (isMine ? ' mine' : '') },
        h('div', { class: 'review-top' },
            h('strong', {}, review.username), stars(review.rating),
            h('time', { datetime: review.createdAt }, formatDate(review.createdAt))),
        review.comment ? h('p', {}, review.comment) : null);
}

function newReviewBlock(restaurant) {
    if (!state.user) {
        return h('p', {}, h('button', {
            type: 'button', class: 'btn-link',
            onclick: () => openAuth('login', 'Sign in to write a review.'),
        }, 'Sign in'), ' to write a review.');
    }
    return reviewForm(restaurant, null);
}

function ownReview(restaurant, review) {
    const slot = h('div', {});
    const show = () => slot.replaceChildren(
        reviewItem(review, true),
        h('div', { class: 'review-actions' },
            h('button', { type: 'button', class: 'btn-link', onclick: () => slot.replaceChildren(reviewForm(restaurant, review, show)) }, 'Edit your review')));
    show();
    return slot;
}

function reviewForm(restaurant, existing, onCancel) {
    const uid = 'rf' + Math.random().toString(36).slice(2, 8);
    const radios = [];
    for (let value = 5; value >= 1; value--) {
        radios.push(
            h('input', { type: 'radio', name: 'rating', id: `${uid}-${value}`, value: String(value), checked: existing && existing.rating === value }),
            h('label', { for: `${uid}-${value}`, title: `${value} ${value === 1 ? 'star' : 'stars'}` }, '★',
                h('span', { class: 'visually-hidden', style: 'position:absolute;left:-9999px' }, `${value} ${value === 1 ? 'star' : 'stars'}`)));
    }
    const comment = h('textarea', { name: 'comment', maxlength: '1000', id: uid + '-c' }, existing && existing.comment ? existing.comment : '');
    const counter = h('p', { class: 'char-count', 'aria-hidden': 'true' }, `${comment.value.length} / 1000`);
    comment.addEventListener('input', () => { counter.textContent = `${comment.value.length} / 1000`; });

    const error = h('p', { class: 'form-error', role: 'alert' });
    const submit = h('button', { type: 'submit', class: 'btn btn-primary' }, existing ? 'Save changes' : 'Post review');

    const form = h('form', { class: 'stack review-form', novalidate: true },
        h('fieldset', { style: 'border:0;padding:0;margin:0' },
            h('legend', { style: 'color:var(--muted);font-size:.9rem;margin-bottom:.3rem;padding:0' }, 'Your rating'),
            h('div', { class: 'star-input' }, radios)),
        h('div', { class: 'field' }, h('label', { for: uid + '-c', style: 'color:var(--muted);font-size:.9rem' }, 'Comment (optional)'), comment, counter),
        error,
        h('div', { class: 'row' }, submit,
            onCancel ? h('button', { type: 'button', class: 'btn', onclick: onCancel }, 'Cancel') : null));

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const chosen = form.querySelector('input[name="rating"]:checked');
        if (!chosen) { error.textContent = 'Choose a rating from 1 to 5 stars.'; return; }
        error.textContent = '';
        submit.disabled = true;
        try {
            const body = { rating: Number(chosen.value), comment: comment.value.trim() };
            if (existing) {
                await api(`reviews/${existing.id}`, { method: 'PUT', auth: true, body });
                toast('Review updated.');
            } else {
                await api('reviews', { method: 'POST', auth: true, body: { restaurantId: restaurant.id, ...body } });
                toast('Review posted.');
            }
            await refreshDetail(restaurant);
        } catch (e) {
            if (e.status === 401) { $('#dlg-detail').close(); return; }
            error.textContent = e.status === 409 ? 'You already reviewed this restaurant.' : e.message;
            submit.disabled = false;
        }
    });
    return form;
}

async function toggleFavorite(restaurant, button) {
    const saved = state.favorites.has(restaurant.id);
    button.disabled = true;
    try {
        await api(`users/${state.user.id}/favorites/${restaurant.id}`, { method: saved ? 'DELETE' : 'POST', auth: true });
        if (saved) state.favorites.delete(restaurant.id); else state.favorites.add(restaurant.id);
        button.setAttribute('aria-pressed', String(!saved));
        button.textContent = saved ? 'Save to favorites' : 'Saved to favorites';
        toast(saved ? 'Removed from favorites.' : 'Saved to favorites.');
    } catch (e) {
        if (e.status === 409) {                    // already saved on the server
            state.favorites.add(restaurant.id);
            button.setAttribute('aria-pressed', 'true');
            button.textContent = 'Saved to favorites';
        } else if (e.status !== 401) {
            toast(e.message);
        }
    } finally {
        button.disabled = false;
    }
}

/* ------------------------------------------------------- events and start */

$('#tab-all').addEventListener('click', () => { state.view = 'all'; state.shown = PAGE_SIZE; render(); });
$('#tab-favorites').addEventListener('click', () => { state.view = 'favorites'; state.shown = PAGE_SIZE; render(); });
$('#filters').addEventListener('input', () => { state.shown = PAGE_SIZE; render(); });
$('#filters').addEventListener('submit', (event) => event.preventDefault());

async function start() {
    renderAccount();
    const token = storageGet('rr_token');
    const savedUser = storageGet('rr_user');
    if (token && savedUser) {
        try {
            state.token = token;
            const me = await api('auth/me', { auth: true });
            setSession(token, { id: me.id, username: me.username });
            await loadFavorites();
        } catch (e) {
            if (e.status !== 0) setSession(null, null);
        }
    }
    await loadRestaurants();
}
start();
