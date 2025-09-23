// --- config ---
const API = "/api";
let owner = localStorage.getItem("owner") || "";
let watchTimer = null;
let watching = "";
let watchChart = null;
let otpExpected = null;
let otpCreatedTs = 0;
let otpTimer = null;
let otpMode = false;
const MAX_POINTS = 300;
const seriesCache = new Map();
const CACHE_KEY = (owner) => `chartCache:${owner}`;

// --- dom helpers ---
const $ = (id) => document.getElementById(id);
const log = (...xs) => {
	const line = [new Date().toLocaleDateString(), ...xs].join(" ");
	$("log").textContent = line + "\n" + $("log").textContent;
};
const setOwnerBadge = () =>
	$("ownerBadge").textContent = owner ? `${owner}` : "(no user set)";

function nowS() {
	return (Date.now() / 1000);
}
function isExpired(otpCreatedTs, ttlSec = 60) {
	return (nowS() - otpCreatedTs) > ttlSec;
}
function ctEquals(a, b) {
	if (a.length !== b.length) return false;
	let r = 0;
	for (let i = 0; i < a.length; i++) {
		r |= a.charCodeAt(i) ^ b.charCodeAt(i);
	}
	return r === 0;
}

function ensureWatchChart() {
	if (watchChart) return watchChart;
	const ctx = document.getElementById("watchChart");
	if (!ctx || !window.Chart) return null;

	watchChart = new Chart(ctx, {
		type: "line",
		data: {
			labels: [],
			datasets: [{
				label: "Last Price",
				data: [],
				borderWidth: 2,
				pointRadius: 0,
				tension: 0.2,
			}],
		},
		options: {
			animation: false,
			responsive: true,
			maintainAspectRatio: false,
			scales: {
				x: {
					ticks: { maxTicksLimit: 6 },
					grid: { display: false },
				},
				y: { ticks: { maxTicksLimit: 6 } },
			},
			plugins: {
				legend: { display: false },
				tooltip: { mode: "index", intersect: false },
				annotation: {
					annotations: {
						entry: {
							type: "line",
							yMin: 0,
							yMax: 0,
							borderColor:
								"rgba(34,197,94,.9)",
							borderWidth: 1,
							label: {
								enabled: true,
								content: "Entry",
								position:
									"start",
							},
							display: false,
						},
						sell: {
							type: "line",
							yMin: 0,
							yMax: 0,
							borderColor:
								"rgba(239,68,68,.9)",
							borderWidth: 1,
							label: {
								enabled: true,
								content: "Sell",
								position:
									"start",
							},
							display: false,
						},
					},
				},
			},
		},
	});
	return watchChart;
}

function renderOptions(selectId, symbols, { placeholder } = {}) {
	const sel = $(selectId);
	if (!sel) return;
	const current = sel.value;
	const opts = [];
	if (placeholder) opts.push(`<option value="">${placeholder}</option>`);
	for (const s of symbols) {
		opts.push(`<option value="${s}">${s}</option>`);
	}
	sel.innerHTML = opts.join("");
	if (current && symbols.includes(current)) sel.value = current;
}
function saveOwner() {
	owner = $("owner").value.trim();
	localStorage.setItem("owner", owner);
	setOwnerBadge();
	log("owner set ->", owner);
}

function showView(name) {
	const inLogin = name === "login" || name === "otpCode";
	const inOtp = name === "otpCode";
	const inDash = name === "dashboard" || name !== "start";
	$("view-login").classList.toggle("hidden", !inLogin);
	$("tabbar").classList.toggle("hidden", inLogin);
	$("view-dashboard").classList.toggle(
		"hidden",
		!inDash || name === "settings",
	);
	$("view-settings").classList.toggle("hidden", name !== "settings");

	$("otpCode").classList.toggle("hidden", !inOtp);
	const otpLabel = document.querySelector('label[for="otpCode"]');
	if (otpLabel) otpLabel.classList.toggle("hidden", !inOtp);
	$("btnLogin").classList.toggle("hidden", !inOtp);
	$("btnSendCode").classList.toggle("hidden", inOtp);

	$("NewTrader").classList.toggle("hidden", name !== "start");
	$("btnNewTrader").classList.toggle("hidden", name === "start");
}
function changeTab(name) {
	document.querySelectorAll(".tab").forEach((tab) => {
		tab.classList.remove("active");
	});
	if (name == "dashboard") {
		$("tab-dashboard").classList.add("active");
	} else if (name == "settings") {
		$("tab-settings").classList.add("active");
	}
}

function setOwner(owner) {
	localStorage.setItem("owner", owner);
	$("ownerBadge").textContent = `Logged in as ${owner}`;
	showView("dashboard");
}

function getOwner() {
	return localStorage.getItem("owner") || "";
}

function logout() {
	localStorage.removeItem("owner");
	owner = "";
	if (watchTimer) {
		clearInterval(watchTimer);
		watchTimer = null;
	}
	watching = "";
	setOwnerBadge();
	showView("login");
}

window.addEventListener("DOMContentLoaded", () => {
	const btnBack = $("btnBack");
	try {
		if (owner) {
			$("owner").value = owner;
			setOwnerBadge();
			showView("dashboard");
			changeTab("dashboard");
			loadSymbols();
			listTraders();
		} else {
			showView("login");
		}
		$("btnSendCode").onclick = async (e) => {
			e.preventDefault();
			const owner = $("owner").value.trim();
			if (!owner) {
				alert("Enter your email");
				return;
			}
			try {
				const _codeCall = await api("/login/send", {
					email: owner,
				});
				otpMode = true;
				showView("otpCode");
			} catch (e) {
				log("otp request err ->", e.message);
				alert("Could not send code. Try again in a moment.");
			}
		};

		$("btnLogin").onclick = async (e) => {
			e.preventDefault();
			if (otpMode) {
				const owner = $("owner").value.trim();
				const input = document.getElementById("otpCode")
					.value.trim();
				if (!input) {
					alert("Enter the One-Time Code you received in your email");
					return;
				}
				const check = await api("/login/check", {
					email: owner,
					code: input,
				});
				if (!check) return;
				const verified = check?.ok;
				if (!verified) {
					return alert(
						"Code Verification failed",
					);
				}
				if (verified) {
					otpMode = false;
					saveOwner();
					showView("dashboard");
					changeTab("dashboard");
					loadSymbols();
					listTraders();
					return;
				}
			}
		};

		const logoutbtn = $("btnLogout");
		if (logoutbtn) {
			logoutbtn.onclick = () => {
				logout();
				changeTab("none");
			};
		}

		const btnNewTrader = $("btnNewTrader");
		if (btnNewTrader) {
			btnNewTrader.onclick = () => {
				showView("start");
			};
		}

		const startBtn = $("btnStart");
		if (startBtn) {
			startBtn.onclick = () => {
				start();
				showView("dashboard");
			};
		}
		const stopBtn = $("btnStop");
		if (stopBtn) {
			stopBtn.onclick = () => {
				stop();
			};
		}

		const addCoinBtn = $("btnAddSymbol");
		if (addCoinBtn) {
			addCoinBtn.onclick = () => {
				new_coin();
			};
		}
		const btnSettings = $("tab-settings");
		if (btnSettings) {
			btnSettings.onclick = () => {
				showView("settings");
				changeTab("settings");
			};
		}

		const btnDash = $("tab-dashboard");
		if (btnDash) {
			btnDash.onclick = () => {
				showView("dashboard");
				changeTab("dashboard");
			};
		}

		if (btnBack) {
			btnBack.onclick = () => {
				showView("dashboard");
				changeTab("dashboard");
			};
		}

		if (!btnBack) {
			console.log("no back button registered");
		}
	} catch (e) {
		console.error(e);
	}
});

// --- fetch helper ---
async function api(path, payload) {
	if (payload && typeof payload !== "object") {
		throw new Error("payload must be an object");
	}
	try {
		const res = await fetch(`${API}${path}`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload || {}),
		});
		const text = await res.text();
		const data = (() => {
			try {
				return JSON.parse(text);
			} catch {
				return null;
			}
		})();
		if (!res.ok) {
			const detail = data?.detail ?? data ?? text ??
				res.statusText;
			throw new Error(
				`HTTP ${res.status}: ${
					typeof detail === "string"
						? detail
						: JSON.stringify(detail)
				}`,
			);
		}
		return data ?? {};
	} catch (e) {
		console.error(`API error`, path, e);
		throw e;
	}
}

async function loadSymbols() {
	try {
		const { symbols = [] } = await api("/symbols", {});
		renderOptions("symbolSelect", symbols, {
			placeholder: "Select symbol...",
		});
		log("symbols ->", symbols.join(", ") || ("none"));
	} catch (e) {
		log("symbols err ->", e.message);
	}
}

// --- actions ---
async function listTraders() {
	if (!owner) return alert("Set username first");
	try {
		const { traders = [] } = await api("/traders/list", { owner });

		renderTraderNav(traders);
		let sym = restoreWatch();
		if (!sym || !traders.includes(sym)) {
			sym = traders[0] || "";
		}
		if (sym) {
			watching = sym;
			statusWatching(sym);
			rememberWatch(sym);
			showSymbolInChart(sym);
			setRefresh();
		}

		renderOptions("traderList", traders);
		log("list ok ->", traders.join(", ") || "(none)");
	} catch (e) {
		log("list err ->", e.message);
	}
}

async function start() {
	if (!owner) return alert("Set Username First");
	const symbol = $("symbolSelect").value.trim();
	const strategy = $("strategySelect").value.trim() || "base";
	const fund_amnt = $("fundAmnt").value.trim() || "100";
	if (!symbol) return alert("No symbol selected");
	try {
		const data = await api("/traders/start", {
			owner,
			symbol,
			strategy,
			fund_amnt,
		});
		log("start ok ->", JSON.stringify(data));
	} catch (e) {
		log("start err ->", e.message);
	}
	listTraders();
}

async function stop() {
	if (!owner) return alert("Username Required");
	const symbol = watching;
	if (!symbol) return alert("Symbol required");
	try {
		const data = await api("/traders/stop", { owner, symbol });
	} catch (e) {
		log("stop err -> ", e.message);
	}
	listTraders();
}

async function new_coin() {
	if (!owner) return alert("Username required");
	const symbol = $("newSymbol").value.trim();
	if (!symbol) return alert("Symbol Required");
	try {
		const data = await api("/traders/add_coin", {
			owner,
			coin: symbol.toUpperCase(),
		});
		log("added coin ->", JSON.stringify(data));
	} catch (e) {
		log("add err ->", e.message);
	}
	listTraders();
}

// --- All functions related to the graph ---
async function statusWatching(sym) {
	sym = sym || watching;
	if (!owner || !sym) return;

	const { status = {} } = await api("/traders/status", {
		owner,
		symbol: sym,
	});
	// Chart Fields, data the graph pulls to generate
	$("watchSymbolLabel").textContent = status.symbol || sym;
	$("watchStage").textContent = status.stage || "-";
	$("watchPrice").textContent = status.last_price ?? "-";
	$("watchEntry").textContent = status.entry_price ?? "not set";
	$("watchSell").textContent = status.sell_limit ?? "not set";
	$("watchBalance").textContent = status.balance ?? "-";
	$("watchQty").textContent = status.quantity ?? "-";

	const price = Number(status.last_price);
	if (Number.isFinite(price)) {
		const ts = new Date().toLocaleTimeString([], { hour12: false });
		appendPoint(sym, ts, price);
	}
	const ch = ensureWatchChart();
	if (!ch) return;

	if (sym === watching) {
		const s = getSeries(sym);
		ch.data.labels = s.labels;
		ch.data.datasets[0].data = s.data;
	}

	updateLimitLines(watchChart, status);
	ch.update("none");
}

function showSymbolInChart(sym) {
	const ch = ensureWatchChart();
	if (!ch) return;
	const s = getSeries(sym);
	ch.data.labels = s.labels;
	ch.data.datasets[0].data = s.data;
	ch.update("none");
}

function getSeries(sym) {
	if (!seriesCache.has(sym)) {
		seriesCache.set(sym, { labels: [], data: [] });
	}
	return seriesCache.get(sym);
}

function appendPoint(sym, ts, price) {
	const s = getSeries(sym);
	s.labels.push(ts);
	s.data.push(price);
	if (s.data.length > MAX_POINTS) {
		s.data.shift();
		s.labels.shift();
	}
}

function setRefresh() {
	const ms = 1000;
	if (watchTimer) {
		clearInterval(watchTimer);
		watchTimer = null;
	}
	if (ms > 0 && watching) {
		statusWatching(watching);
		watchTimer = setInterval(() => statusWatching(watching), ms);
	}
}

const LAST_WATCH_KEY = "lastWatchSymbol";
function rememberWatch(sym) {
	if (!sym) return;
	localStorage.setItem(LAST_WATCH_KEY, sym);
	watching = sym;
}

function restoreWatch() {
	return localStorage.getItem(LAST_WATCH_KEY) || "";
}

function renderTraderNav(traders) {
	const ul = $("traderNav");
	if (!ul) return;

	const current = restoreWatch();
	ul.innerHTML = traders.map((sym) =>
		`<li data-sym="${sym}" class="${
			sym === current ? "active" : ""
		}">
            ${sym}
        </li>`
	).join("");

	ul.querySelectorAll("li").forEach((li) => {
		li.addEventListener("click", () => {
			const sym = li.getAttribute("data-sym");
			ul.querySelectorAll("li").forEach((n) =>
				n.classList.remove("active")
			);
			li.classList.add("active");
			rememberWatch(sym);
			watching = sym;
			statusWatching(sym);
			showSymbolInChart(sym);
			setRefresh();
		});
	});
}

function askLogin() {
	const name = prompt("Enter your username");
	if (name) {
		saveOwner(name);
		setOwnerBadge();
		loadSymbols();
		listTraders();
		let sym = restoreWatch() || traders[0];
		if (sym) {
			watching = sym;
			showSymbolInChart(sym);
			setRefresh();
		}
		showView("dashboard");
	} else {
		alert("Login required");
		askLogin();
	}
}

function updateLimitLines(chart, status) {
	const ann = chart.options.plugins.annotation.annotations;

	if (Number.isFinite(status.entry_price)) {
		ann.entry.yMin = ann.entry.yMax = status.entry_price;
		ann.entry.display = true;
	} else {
		ann.entry.display = false;
	}

	if (Number.isFinite(status.sell_limit)) {
		ann.sell.yMin = ann.sell.yMax = status.sell_limit;
		ann.sell.display = true;
	} else {
		ann.sell.display = false;
	}
}

// --- boot ---
(function init() {
	if (owner) $("owner").value = owner;
	setOwnerBadge();
})();
