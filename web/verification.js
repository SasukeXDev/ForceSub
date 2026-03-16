const context = window.VERIFICATION_CONTEXT || {};
const card = document.getElementById("verification-card");
const progressFill = document.getElementById("progress-fill");
const steps = Array.from(document.querySelectorAll("#steps-list .step"));
const watchAdBtn = document.getElementById("watch-ad-btn");
const loading = document.getElementById("loading");
const continueLink = document.getElementById("continue-link");
const statusText = document.getElementById("status-text");

const STEP_COUNT = 4;
const LIBTL_SCRIPT_SRC = "//libtl.com/sdk.js";
const LIBTL_FUNCTION_NAME = "show_10739699";

const applyTheme = () => {
  const tg = window.Telegram?.WebApp;
  if (!tg) return;

  tg.ready();
  const params = tg.themeParams || {};
  const root = document.documentElement;

  if (params.bg_color) root.style.setProperty("--bg-start", params.bg_color);
  if (params.secondary_bg_color) root.style.setProperty("--bg-end", params.secondary_bg_color);
  if (params.text_color) root.style.setProperty("--text-main", params.text_color);
  if (params.hint_color) root.style.setProperty("--text-muted", params.hint_color);
  if (params.button_color) root.style.setProperty("--primary", params.button_color);

  if (params.bg_color) {
    root.style.setProperty("--card-bg", `${params.bg_color}e0`);
  }
};

const setStep = (index) => {
  const clamped = Math.max(1, Math.min(index, STEP_COUNT));
  steps.forEach((step, i) => {
    step.classList.toggle("active", i + 1 === clamped);
    step.classList.toggle("done", i + 1 < clamped);
  });
  progressFill.style.width = `${(clamped / STEP_COUNT) * 100}%`;
};

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const setStatus = (message, isError = false) => {
  statusText.textContent = message;
  statusText.classList.toggle("error", isError);
};

const ensureSdkScript = () => {
  const existing = document.querySelector(`script[src='${LIBTL_SCRIPT_SRC}']`);
  if (existing) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = LIBTL_SCRIPT_SRC;
    script.dataset.zone = "10739699";
    script.dataset.sdk = LIBTL_FUNCTION_NAME;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Unable to load ad sdk"));
    document.head.appendChild(script);
  });
};

const mountCustomScriptTag = () => {
  const scriptOrZone = context.interstitialScript || "";
  if (!scriptOrZone) return;

  if (scriptOrZone.toLowerCase().includes("<script")) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(scriptOrZone, "text/html");
    const tags = doc.querySelectorAll("script");
    tags.forEach((tag) => {
      const script = document.createElement("script");
      for (const attr of tag.attributes) {
        script.setAttribute(attr.name, attr.value);
      }
      script.textContent = tag.textContent;
      document.body.appendChild(script);
    });
    return;
  }

  const sdk = document.createElement("script");
  sdk.async = true;
  sdk.src = "https://a.monetag.com/script.js";
  sdk.dataset.zone = scriptOrZone;
  document.body.appendChild(sdk);
};

const triggerSdkAd = async () => {
  const showFn = window[LIBTL_FUNCTION_NAME];
  if (typeof showFn !== "function") {
    throw new Error("Ad function is not ready");
  }

  const result = showFn();
  if (result && typeof result.then === "function") {
    await result;
  }
};

const runFlow = async () => {
  watchAdBtn.disabled = true;
  continueLink.classList.add("hidden");
  setStatus("Preparing secure ad verification...");
  loading.classList.remove("hidden");
  setStep(2);

  try {
    await ensureSdkScript();
    mountCustomScriptTag();

    setStatus("Loading ad network...");
    await wait(650);
    setStep(3);

    setStatus("Showing ad...");
    await triggerSdkAd();

    await wait(700);
    loading.classList.add("hidden");
    setStep(4);
    setStatus("Verification complete. Continue to unlock your file.");
    continueLink.href = context.interstitialDoneUrl || "#";
    continueLink.classList.remove("hidden");
  } catch (error) {
    loading.classList.add("hidden");
    watchAdBtn.disabled = false;
    setStep(2);
    setStatus(error?.message || "Could not load ad. Please try again.", true);
  }
};

watchAdBtn.addEventListener("click", runFlow);

window.addEventListener("DOMContentLoaded", () => {
  applyTheme();
  setStep(1);
  setStatus("Tap \"Watch Ad\" to start verification.");
  setTimeout(() => card.classList.add("entered"), 60);
});
