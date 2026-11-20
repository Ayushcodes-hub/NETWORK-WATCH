
const API_BASE = (window.NETWORK_WATCH_API || "").replace(/\/+$/, "");
const $ = (id) => document.getElementById(id);

const COLORS = {
    TCP: "#37e0c0",
    UDP: "#69a9ff",
    DNS: "#aa91ff",
    TLS: "#f4bd62",
    ICMP: "#ff829b",
    OTHER: "#64758c"
};

let latestProtocols = [];
let refreshInProgress = false;
let toastTimer = null;
let captureStarting = false;
let captureStopping = false;

async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, options);

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error(`Invalid server response (${response.status})`);
    }

    if (!response.ok) {
        throw new Error(data.detail || data.error || `API error ${response.status}`);
    }

    return data;
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[char]);
}

function formatNumber(value) {
    return Number(value || 0).toLocaleString("en-IN");
}

function formatBytes(bytes) {
    let value = Number(bytes || 0);

    if (value < 1024) return `${value.toFixed(0)} B`;
    if (value < 1024 ** 2) return `${(value / 1024).toFixed(2)} KB`;
    if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(2)} MB`;

    return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function formatTime(value) {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return "—";

    return date.toLocaleTimeString();
}

function showToast(message) {
    const toast = $("toast");

    if (!toast) return;

    toast.textContent = message;
    toast.classList.add("show");

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, 2800);
}

function updateClock() {
    const clock = $("clock");

    if (clock) {
        clock.textContent = new Date().toLocaleTimeString();
    }
}

function displayInterfaceName(device) {
    const match = device.match(/NPF_\{([^}]+)\}/i);

    if (!match) return device;

    const guid = match[1].toLowerCase();

    if (guid === "989d2192-81ea-4ccd-a902-9aff69629a12") {
        return "WiFi — Qualcomm Wireless Adapter";
    }

    return `Network adapter — ${guid.slice(0, 8)}`;
}

async function loadCaptureInterfaces() {
    const selector = $("interfaceSelect");

    try {
        const result = await api("/api/capture/interfaces");

        selector.innerHTML = "";

        if (result.error && !result.interfaces?.length) {
            selector.innerHTML =
                `<option value="">Capture adapter error</option>`;

            showToast(result.error);
            return;
        }

        const interfaces = result.interfaces || [];

        if (!interfaces.length) {
            selector.innerHTML =
                `<option value="">No adapters found</option>`;
            return;
        }

        interfaces.forEach(device => {
            const option = document.createElement("option");

            // Actual Npcap device identifier sent to the backend.
            option.value = device;

            // Friendly name displayed to the user.
            option.textContent = displayInterfaceName(device);

            selector.appendChild(option);
        });

        // Backend places the default adapter first.
        const preferred = result.default_interface;

        if (preferred) {
            selector.value = preferred;
        }

    } catch (error) {
        console.error("Adapter loading failed:", error);

        selector.innerHTML =
            `<option value="">Unable to load adapters</option>`;

        showToast("Could not load capture adapters.");
    }
}

function drawProtocolChart(protocols) {
    const canvas = $("protocolChart");

    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    const size = Math.max(180, Math.floor(canvas.clientWidth || 190));
    const dpr = window.devicePixelRatio || 1;

    canvas.width = size * dpr;
    canvas.height = size * dpr;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const center = size / 2;
    const radius = size * 0.39;
    const lineWidth = size * 0.105;

    ctx.clearRect(0, 0, size, size);

    ctx.beginPath();
    ctx.arc(center, center, radius, 0, Math.PI * 2);
    ctx.strokeStyle = "#233245";
    ctx.lineWidth = lineWidth;
    ctx.stroke();

    const total = protocols.reduce(
        (sum, item) => sum + Number(item.count || 0), 0
    );

    $("chartTotal").textContent = formatNumber(total);

    if (!total) {
        $("protocolLegend").innerHTML =
            `<div class="empty-state">Waiting for traffic...</div>`;
        return;
    }

    let start = -Math.PI / 2;

    for (const item of protocols) {
        const count = Number(item.count || 0);
        const angle = (count / total) * Math.PI * 2;

        ctx.beginPath();
        ctx.arc(center, center, radius, start, start + angle);
        ctx.strokeStyle = COLORS[item.protocol] || COLORS.OTHER;
        ctx.lineWidth = lineWidth;
        ctx.lineCap = "butt";
        ctx.stroke();

        start += angle;
    }

    $("protocolLegend").innerHTML = protocols.map(item => {
        const protocol = escapeHTML(item.protocol);
        const color = COLORS[item.protocol] || COLORS.OTHER;

        return `
            <div class="legend-item">
                <span class="legend-name">
                    <span class="legend-dot" style="background:${color}"></span>
                    ${protocol}
                </span>
                <strong>${formatNumber(item.count)}</strong>
            </div>
        `;
    }).join("");
}

function renderAlerts(items) {
    $("sidebarAlertCount").textContent = formatNumber(items.length);

    if (!items.length) {
        $("alertsTable").innerHTML =
            `<tr><td colspan="5" class="empty-state">No alerts recorded yet.</td></tr>`;
        return;
    }

    $("alertsTable").innerHTML = items.map(item => `
        <tr>
            <td>
                <span class="severity ${escapeHTML(item.severity)}">
                    ${escapeHTML(item.severity)}
                </span>
            </td>
            <td>${escapeHTML(item.title)}</td>
            <td>${escapeHTML(item.description)}</td>
            <td>${escapeHTML(item.evidence)}</td>
            <td>${formatTime(item.timestamp)}</td>
        </tr>
    `).join("");
}

function renderConnections(items) {
    $("connectionCount").textContent = formatNumber(items.length);

    if (!items.length) {
        $("connectionsTable").innerHTML =
            `<tr><td colspan="6" class="empty-state">No connections available.</td></tr>`;
        return;
    }

    $("connectionsTable").innerHTML = items.slice(0, 100).map(item => `
        <tr>
            <td>${escapeHTML(item.process)}</td>
            <td>${escapeHTML(item.pid ?? "—")}</td>
            <td><span class="protocol-badge">${escapeHTML(item.protocol)}</span></td>
            <td>${escapeHTML(item.local_ip)}:${escapeHTML(item.local_port ?? "—")}</td>
            <td>${escapeHTML(item.remote_ip || "—")}:${escapeHTML(item.remote_port ?? "—")}</td>
            <td>${escapeHTML(item.status)}</td>
        </tr>
    `).join("");
}

function renderEvents(items) {
    if (!items.length) {
        $("eventsTable").innerHTML =
            `<tr><td colspan="7" class="empty-state">No packet events found.</td></tr>`;
        return;
    }

    $("eventsTable").innerHTML = items.map(item => `
        <tr>
            <td><span class="protocol-badge">${escapeHTML(item.protocol)}</span></td>
            <td>${escapeHTML(item.src_ip)}:${escapeHTML(item.src_port ?? "—")}</td>
            <td>${escapeHTML(item.dst_ip)}:${escapeHTML(item.dst_port ?? "—")}</td>
            <td>${formatBytes(item.packet_size)}</td>
            <td>${escapeHTML(item.direction)}</td>
            <td>${escapeHTML(item.dns_query || "—")}</td>
            <td>${formatTime(item.timestamp)}</td>
        </tr>
    `).join("");
}

function renderInterfaces(items) {
    if (!items.length) {
        $("interfacesTable").innerHTML =
            `<tr><td colspan="6" class="empty-state">No interfaces found.</td></tr>`;
        return;
    }

    $("interfacesTable").innerHTML = items.map(item => `
        <tr>
            <td>${escapeHTML(item.name)}</td>
            <td>
                <span class="${item.is_up ? "state-up" : "state-down"}">
                    ${item.is_up ? "● UP" : "● DOWN"}
                </span>
            </td>
            <td>${escapeHTML(item.ipv4)}</td>
            <td>${formatNumber(item.speed_mbps)} Mbps</td>
            <td>${formatBytes(item.bytes_sent)}</td>
            <td>${formatBytes(item.bytes_recv)}</td>
        </tr>
    `).join("");
}

function updateCaptureControls(status) {
    const running = status.capture_running;

    $("startButton").disabled = running || captureStarting || captureStopping;
    $("stopButton").disabled = !running || captureStopping;
    $("interfaceSelect").disabled = running || captureStarting || captureStopping;

    $("systemDot").style.background = running ? "#37e0c0" : "#f4bd62";

    $("systemState").textContent = running
        ? "CAPTURE ACTIVE"
        : "SYSTEM ONLINE";

    $("captureMessage").textContent = running
        ? `Capturing traffic on ${displayInterfaceName(status.capture_interface || "")}`
        : (status.capture_error
            ? `Capture error: ${status.capture_error}`
            : "Select a network adapter to begin monitoring.");
}

async function refreshDashboard() {
    if (refreshInProgress) return;

    refreshInProgress = true;

    try {
        const [
            status,
            analytics,
            alertResult,
            connectionResult,
            interfaceResult
        ] = await Promise.all([
            api("/api/status"),
            api("/api/analytics"),
            api("/api/alerts?limit=100"),
            api("/api/connections"),
            api("/api/interfaces")
        ]);

        $("packetCount").textContent = formatNumber(status.packets);
        $("totalBytes").textContent = formatBytes(status.bytes);
        $("uploadBytes").textContent = formatBytes(status.upload_bytes);
        $("downloadBytes").textContent = formatBytes(status.download_bytes);

        $("tcpCount").textContent = formatNumber(status.tcp);
        $("udpCount").textContent = formatNumber(status.udp);
        $("dnsCount").textContent = formatNumber(status.dns);
        $("tlsCount").textContent = formatNumber(status.tls);

        $("alertCount").textContent = formatNumber(alertResult.alerts.length);

        updateCaptureControls(status);

        latestProtocols = analytics.protocols || [];

        drawProtocolChart(latestProtocols);
        renderAlerts(alertResult.alerts || []);
        renderConnections(connectionResult.connections || []);
        renderInterfaces(interfaceResult.interfaces || []);

        $("lastUpdated").textContent =
            `UPDATED ${new Date().toLocaleTimeString()}`;

    } catch (error) {
        console.error("Dashboard refresh failed:", error);
        $("systemState").textContent = "API CONNECTION ERROR";
    } finally {
        refreshInProgress = false;
    }
}

async function loadEvents() {
    const search = $("eventSearch").value.trim();
    const protocol = $("protocolFilter").value;

    const params = new URLSearchParams({
        limit: "150",
        search,
        protocol
    });

    try {
        const result = await api(`/api/events?${params}`);
        renderEvents(result.events || []);
    } catch (error) {
        console.error("Event loading failed:", error);
    }
}

async function loadSystemInterfaces() {
    try {
        const result = await api("/api/interfaces");
        renderInterfaces(result.interfaces || []);
    } catch (error) {
        console.error("Interface loading failed:", error);
    }
}

async function startCapture() {
    if (captureStarting || captureStopping) return;

    const interfaceName = $("interfaceSelect").value;

    if (!interfaceName) {
        showToast("Please select a network adapter.");
        return;
    }

    captureStarting = true;
    $("startButton").disabled = true;
    $("interfaceSelect").disabled = true;
    $("captureMessage").textContent = "Starting packet capture...";

    try {
        const result = await api("/api/capture/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ interface: interfaceName })
        });

        if (result.error) {
            showToast(`Capture failed: ${result.error}`);
        } else {
            showToast("Packet capture started successfully.");
        }

        await refreshDashboard();

    } catch (error) {
        showToast(`Could not start capture: ${error.message}`);
    } finally {
        captureStarting = false;
        await refreshDashboard();
    }
}

async function stopCapture() {
    if (captureStopping || captureStarting) return;

    captureStopping = true;
    $("stopButton").disabled = true;

    try {
        const result = await api("/api/capture/stop", {
            method: "POST"
        });

        showToast(result.message || "Capture stopped.");

    } catch (error) {
        showToast(`Could not stop capture: ${error.message}`);
    } finally {
        captureStopping = false;
        await refreshDashboard();
    }
}

function initializeNavigation() {
    document.querySelectorAll(".nav-item").forEach(link => {
        link.addEventListener("click", () => {
            document.querySelectorAll(".nav-item").forEach(item =>
                item.classList.remove("active")
            );

            link.classList.add("active");
        });
    });
}

async function initialize() {
    updateClock();
    initializeNavigation();

    $("startButton").addEventListener("click", startCapture);
    $("stopButton").addEventListener("click", stopCapture);

    $("eventSearch").addEventListener("input", loadEvents);
    $("protocolFilter").addEventListener("change", loadEvents);

    await loadCaptureInterfaces();
    await refreshDashboard();
    await loadEvents();

    setInterval(updateClock, 1000);
    setInterval(refreshDashboard, 2500);
    setInterval(loadEvents, 5000);
    setInterval(loadSystemInterfaces, 15000);

    window.addEventListener("resize", () => {
        drawProtocolChart(latestProtocols);
    });
}

initialize();



