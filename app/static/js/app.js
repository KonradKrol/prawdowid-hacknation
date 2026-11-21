// Prawdomir — ulepszenia interfejsu. Wszystko działa też bez JavaScriptu.

for (const form of document.querySelectorAll("[data-check-form]")) {
  const area = form.querySelector("textarea");
  const counter = form.querySelector("[data-count]");
  const update = () => { if (counter) counter.textContent = area.value.length; };
  area?.addEventListener("input", update);
  update();

  const examples = form.querySelector("[data-examples]");
  if (examples) {
    examples.hidden = false;
    examples.addEventListener("click", (e) => {
      const chip = e.target.closest("[data-example]");
      if (!chip) return;
      area.value = chip.dataset.example;
      update();
      area.focus();
    });
  }

  form.addEventListener("submit", (e) => {
    if (!area.value.trim()) {
      e.preventDefault();
      area.setAttribute("aria-invalid", "true");
      area.focus();
      return;
    }
    const body = form.querySelector("[data-form-body]");
    const progress = form.querySelector("[data-progress]");
    if (!progress) return;
    // Pokazujemy postęp; przeglądarka wysyła formularz normalnie i przejdzie do wyniku.
    progress.hidden = false;
    body.style.display = "none";
    const steps = [...progress.querySelectorAll("[data-step]")];
    let i = 0;
    const tick = () => {
      steps.forEach((s, n) => {
        s.classList.toggle("is-done", n < i);
        s.classList.toggle("is-active", n === i);
      });
      if (i < steps.length - 1) { i += 1; setTimeout(tick, 1800); }
    };
    tick();
  });
}

for (const btn of document.querySelectorAll("[data-copy]")) {
  if (!navigator.clipboard) continue;
  btn.hidden = false;
  btn.addEventListener("click", async () => {
    const label = btn.querySelector("[data-copy-label]");
    try {
      await navigator.clipboard.writeText(btn.dataset.copy);
      label.textContent = "Skopiowano";
    } catch {
      label.textContent = "Nie udało się skopiować";
    }
    setTimeout(() => { label.textContent = "Skopiuj krótką odpowiedź"; }, 2500);
  });
}

// Ułatwienia dostępu: rozmiar tekstu, wersja kontrastowa, czytanie na głos. Wybór zapamiętany w przeglądarce.
const a11y = document.querySelector("[data-a11y]");
if (a11y) {
  a11y.hidden = false;
  const root = document.documentElement;
  const store = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
                  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* brak pamięci */ } } };

  const sizes = [...a11y.querySelectorAll("[data-a11y-size]")];
  const setSize = (size) => {
    root.classList.remove("a11y-size-m", "a11y-size-l");
    if (size !== "s") root.classList.add(`a11y-size-${size}`);
    sizes.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.a11ySize === size)));
    store.set("pw-size", size);
  };
  setSize(store.get("pw-size") || "s");
  sizes.forEach((b) => b.addEventListener("click", () => setSize(b.dataset.a11ySize)));

  const contrast = a11y.querySelector("[data-a11y-toggle='contrast']");
  const setContrast = (on) => {
    root.classList.toggle("a11y-contrast", on);
    contrast.setAttribute("aria-pressed", String(on));
    store.set("pw-contrast", on ? "1" : "0");
  };
  setContrast(store.get("pw-contrast") === "1");
  contrast.addEventListener("click", () => setContrast(contrast.getAttribute("aria-pressed") !== "true"));

  const read = a11y.querySelector("[data-a11y-read]");
  if ("speechSynthesis" in window && read) {
    read.hidden = false;
    const icon = read.querySelector("use");
    const idle = () => { icon.setAttribute("href", "#i-speaker"); read.setAttribute("aria-label", "Czytaj na głos"); read.title = "Czytaj na głos"; };
    read.addEventListener("click", () => {
      if (speechSynthesis.speaking) { speechSynthesis.cancel(); idle(); return; }
      const main = document.querySelector("main");
      const text = [...main.querySelectorAll("h1, .hv__word, .hv__why, .card__word, .card__quote, .card__reason, .proof__quote, .note, .ask__label, .hero__lead, .state__msg, .bubble p")]
        .map((el) => el.innerText.trim()).filter(Boolean).join(". ");
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "pl-PL";
      u.rate = 0.95;
      u.onend = idle;
      icon.setAttribute("href", "#i-stopsq");
      read.setAttribute("aria-label", "Zatrzymaj czytanie");
      read.title = "Zatrzymaj czytanie";
      speechSynthesis.speak(u);
    });
  }
}
