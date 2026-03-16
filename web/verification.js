const context = window.VERIFICATION_CONTEXT || {};
const card = document.getElementById("verification-card");
const progressFill = document.getElementById("progress-fill");
const steps = Array.from(document.querySelectorAll("#steps-list .step"));
const watchAdBtn = document.getElementById("watch-ad-btn");
const loading = document.getElementById("loading");
const continueLink = document.getElementById("continue-link");

const STEP_COUNT = 4;

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
  if (params.button_text_color) root.style.setProperty("--button-text", params.button_text_color);

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

const mountScriptTag = () => {
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

const runFlow = async () => {
  watchAdBtn.disabled = true;
  loading.classList.remove("hidden");
  setStep(2);

  await wait(500);
  mountScriptTag();

  setStep(3);
  await wait(1600);

  loading.classList.add("hidden");
  setStep(4);

  continueLink.href = context.interstitialDoneUrl || "#";
  continueLink.classList.remove("hidden");
};

watchAdBtn.addEventListener("click", runFlow);

window.addEventListener("DOMContentLoaded", () => {
  applyTheme();
  setStep(1);
  setTimeout(() => card.classList.add("entered"), 60);
});
