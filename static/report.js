class CameraManager {
    constructor() {
        this.stream = null;
        this.videoElement = null;
        this.canvas = document.createElement("canvas");
        this.startToken = 0;
    }

    async _cleanup() {
        const video = this.videoElement;
        const stream = this.stream;

        this.videoElement = null;
        this.stream = null;

        if (video) {
            try {
                video.pause();
            } catch (e) {}
        }

        if (stream) {
            for (const track of stream.getTracks()) {
                try {
                    track.stop();
                } catch (e) {}
            }
        }

        if (video) {
            try {
                video.srcObject = null;
            } catch (e) {}

            try {
                video.load();
            } catch (e) {}
        }
    }

    async start(videoElement, constraints = {}) {
        if (!videoElement) return null;

        const token = ++this.startToken;

        await this._cleanup();

        if (token !== this.startToken) return null;

        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { ideal: "environment" },
                width: { ideal: 1280 },
                height: { ideal: 720 },
                ...constraints
            },
            audio: false
        });

        if (token !== this.startToken) {
            stream.getTracks().forEach(track => {
                try { track.stop(); } catch (e) {}
            });
            return null;
        }

        this.stream = stream;
        this.videoElement = videoElement;
        videoElement.srcObject = stream;

        try {
            await videoElement.play();
        } catch (err) {
            if (token !== this.startToken) return null;

            if (err?.name !== "AbortError" && err?.name !== "DOMException") {
                throw err;
            }
            return null;
        }

        if (token !== this.startToken) {
            await this._cleanup();
            return null;
        }

        return stream;
    }

    async stop() {
        this.startToken++;
        await this._cleanup();
    }

    captureFrame(videoElement = null) {
        const video = videoElement || this.videoElement;
        if (!video || !video.videoWidth || !video.videoHeight) return null;

        this.canvas.width = video.videoWidth;
        this.canvas.height = video.videoHeight;

        const ctx = this.canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, this.canvas.width, this.canvas.height);

        return {
            canvas: this.canvas,
            ctx,
            dataUrl: this.canvas.toDataURL("image/jpeg", 0.92),
            width: this.canvas.width,
            height: this.canvas.height
        };
    }
}
class PhoneCaptureController {
    constructor(cameraManager) {
        this.cameraManager = cameraManager;
        this.activeBlock = null; // вместо previewId
    }

    async start(block) {
        this.setStatus(block, "Запуск сканера", "secondary")
        if (!block) throw Error("Expected scanner block")

        const video = block.querySelector(".camera-feed");
        if (!video) throw Error(`Expected scanner video, got ${video}`);
        try {
            await this.cameraManager.start(video);
            this.activeBlock = block;
            this.setStatus(block, "Камера активна", "success", "camera-video-fill");
        } catch (err) {
            console.error(err);
            this.setStatus(block, "Не удалось открыть камеру", "danger", "exclamation-triangle-fill");
        }
    }

    async stop(block = null) {
        const target = block || this.activeBlock;

        if (target) {
            const video = target.querySelector(".phone-video");
            if (video) video.srcObject = null;

            this.setStatus(target, "Камера не запущена", "secondary", "camera-video");
        }

        this.activeBlock = null;
        return this.cameraManager.stop();
    }

    capture(block) {
        const video = block.querySelector(".phone-video");
        const img = block.querySelector(".phone-preview");
        const previewWrapper = block.querySelector(".preview-wrapper");
        const hiddenInput = block.querySelector(".captured-input");

        const frame = this.cameraManager.captureFrame(video);

        if (!frame || !img || !hiddenInput) {
            alert("Камера ещё не готова");
            return;
        }

        img.src = frame.dataUrl;
        hiddenInput.value = frame.dataUrl;
        previewWrapper?.classList.remove("d-none");
    }

    loadFile(input, block) {
        const file = input?.files?.[0];
        const img = block.querySelector(".phone-preview");
        const previewWrapper = block.querySelector(".preview-wrapper");
        const hiddenInput = block.querySelector(".captured-input");

        if (!file || !img || !hiddenInput) return;

        const reader = new FileReader();
        reader.onload = e => {
            img.src = e.target.result;
            hiddenInput.value = e.target.result;
            previewWrapper?.classList.remove("d-none");
        };
        reader.readAsDataURL(file);
    }

    reset(block) {
        const img = block.querySelector(".phone-preview");
        const fileInput = block.querySelector(".file-input");
        const hiddenInput = block.querySelector(".captured-input");
        const previewWrapper = block.querySelector(".preview-wrapper");

        if (img) img.src = "";
        if (fileInput) fileInput.value = "";
        if (hiddenInput) hiddenInput.value = "";
        previewWrapper?.classList.add("d-none");
    }

    setStatus(block, text, type = "secondary", icon = "camera-video") {
        const status = block.querySelector(".camera-status");
        if (!status) return;
        status.innerHTML = `<i class="bi bi-${icon} me-1"></i> ${text}`;
        status.className = `camera-status alert alert-${type} py-2 px-3 fw-medium mb-2 rounded-4 border-0 shadow-sm`;
    }

    initTabs(root = document) {
        // старт активной вкладки
        const activePane = root.querySelector(".tab-pane.active");
        const activeBlock = activePane?.querySelector(".phone-capture-block");

        if (activeBlock) {
            this.start(activeBlock);
        }

        root.querySelectorAll('[data-bs-toggle="tab"]').forEach(tabBtn => {
            tabBtn.addEventListener("shown.bs.tab", async event => {
                const targetSelector = event.target.getAttribute("data-bs-target");
                const targetPane = document.querySelector(targetSelector);
                if (!targetPane) return;

                const block = targetPane.querySelector(".phone-capture-block");
                if (!block) return;

                await this.stop();
                await this.start(block);
            });
        });
    }
}

class OcrScannerController {
    constructor(cameraManager) {
        this.cameraManager = cameraManager;
        this.root = null;
        this.video = null;
        this.overlayCanvas = null;
        this.overlayCtx = null;
        this.statusEl = null;
        this.serverHintEl = null;
        this.whatToScanEl = null;
        this.successCard = null;
        this.successData = null;
        this.successDescription = null;

        this.cvReady = false;
        this.motionInterval = null;
        this.lastFrame = null;
        this.isProcessing = false;
        this.isStopped = true;
        this.success = {};
        this.readEndpoint = null;
    }

    mount(rootElement) {
        this.root = rootElement;
        this.bindElements();
    }

    bindElements() {
        if (!this.root) return;

        this.video = this.root.querySelector(".camera-feed");
        this.overlayCanvas = this.root.querySelector(".scanner-overlay");
        this.statusEl = this.root.querySelector(".camera-status");
        this.serverHintEl = this.root.querySelector(".scanner-server-hint");
        this.whatToScanEl = this.root.querySelector(".scanner-what-to-scan");
        this.successCard = this.root.querySelector(".scanner-success");
        this.successData = this.root.querySelector(".scanner-success-data");
        this.successDescription = this.root.querySelector(".scanner-success-description");
        this.overlayCtx = this.overlayCanvas?.getContext("2d") || null;
    }

    async ensureOpenCvReady() {
        if (this.cvReady) return;
        if (typeof cv !== "undefined") {
            this.cvReady = true;
            return;
        }

        await new Promise((resolve, reject) => {
            let waited = 0;
            const interval = setInterval(() => {
                if (typeof cv !== "undefined") {
                    clearInterval(interval);
                    this.cvReady = true;
                    resolve();
                }
                waited += 100;
                if (waited > 10000) {
                    clearInterval(interval);
                    reject(new Error("OpenCV not loaded"));
                }
            }, 100);
        });
    }


    async start(rootElement, readEndpoint) {
        if (!rootElement)
            throw Error("Expected root element")
        this.mount(rootElement);
        this.readEndpoint = readEndpoint;
        if (!this.video) return;

        this.isStopped = false;
        if (this.success[readEndpoint]) {
            this.showSuccess(this.success[readEndpoint]);
            return;
        } else {
            this.readEndpoint = readEndpoint;

            if (this.statusEl) {
                this.statusEl.classList.remove("d-none");
            }
            if (this.successCard) {
                this.successCard.classList.add("d-none");
            }
            if (this.successData) {
                this.successData.innerHTML = "";
            }
            if (this.successDescription) {
                this.successDescription.textContent = "";
            }
            this.updateHint("");
            this.clearOverlay();
        }
        this.updateStatus("Запуск сканера", "secondary")
        await this.cameraManager.start(this.video);
        await new Promise(resolve => {
            if (this.video.readyState >= 2 && this.video.videoWidth > 0) {
                resolve();
                return;
            }

            const onLoaded = () => {
                this.video.removeEventListener("loadedmetadata", onLoaded);
                resolve();
            };

            this.video.addEventListener("loadedmetadata", onLoaded, { once: true });
        });

        if (this.overlayCanvas) {
            this.overlayCanvas.width = this.video.videoWidth || 1280;
            this.overlayCanvas.height = this.video.videoHeight || 720;
        }

        this.startLoop();
    }

    async stop() {
        this.isStopped = true;
        this.lastFrame = null;
        this.stopLoop();
        this.clearOverlay();
        await this.cameraManager.stop();
        if (this.video) this.video.srcObject = null;
        this.updateStatus("Сканер зупинений", "secondary", "camera-video");
    }

    startLoop() {
        this.stopLoop();

        this.motionInterval = setInterval(() => this.detectMotionAndScan(), 800);
    }

    stopLoop() {
        if (this.motionInterval) clearInterval(this.motionInterval);
        this.motionInterval = null;
    }

    updateStatus(text, type = "secondary", icon = "camera-video") {
        if (!this.statusEl) return;
        this.statusEl.innerHTML = `<i class="bi bi-${icon} me-1"></i> ${text}`;
        this.statusEl.className = `alert alert-${type} py-2 px-3 fw-medium mb-2 rounded-4 border-0 shadow-sm`;
    }

    updateHint(text = "") {
        if (this.serverHintEl) this.serverHintEl.textContent = text;
    }

    updateWhatToScan(text = "") {
        if (this.whatToScanEl) this.whatToScanEl.textContent = text;
    }

    clearOverlay() {
        if (!this.overlayCtx || !this.overlayCanvas) return;
        this.overlayCtx.clearRect(0, 0, this.overlayCanvas.width, this.overlayCanvas.height);
    }
    isFrameStable(canvas) {
        const ctx = canvas.getContext("2d");
        const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);

        let sum = 0;

        for (let i = 0; i < imgData.data.length; i += 4) {
            sum += imgData.data[i]; // просто яркость
        }

        const avg = sum / (imgData.data.length / 4);

        return avg > 40 && avg < 220; // отсечь темноту и пересвет
    }
    async detectMotionAndScan() {
        if (!this.video || !this.overlayCanvas || this.isStopped) return;

        const frame = this.cameraManager.captureFrame(this.video);
        if (!frame) return;
        try {
            await this.ensureOpenCvReady();
        } catch (e) {
            console.warn(e);
            return;
        }
        if (!this.isFrameStable(frame.canvas))
            return;
        let textBoxes;
        for (let i = 0; i < 2; ++i) {
            textBoxes = this.detectTextLikeRegionsOpenCv(frame.canvas);
            if (!textBoxes.length) {
                this.updateStatus("Наведіть камеру на текст", "secondary", "camera-video");
                return;
            }
        }
        this.drawFrame(textBoxes);
        this.updateStatus("Текстовая область найдена", "primary", "upc-scan");
        await this.processCurrentFrame(frame);
    }

    drawFrame(textBoxes = []) {
        if (!this.overlayCtx || !this.overlayCanvas) return;

        const w = this.overlayCanvas.width;
        const h = this.overlayCanvas.height;

        this.overlayCtx.clearRect(0, 0, w, h);

        this.overlayCtx.lineWidth = 2;
        this.overlayCtx.strokeStyle = "#00ff66";

        for (const box of textBoxes) {
            const padX = Math.round(box.width * 0.08);
            const padY = Math.round(box.height * 0.25);

            const x = Math.max(0, box.x - padX);
            const y = Math.max(0, box.y - padY);
            const width = Math.min(w - x, box.width + padX * 2);
            const height = Math.min(h - y, box.height + padY * 2);

            this.overlayCtx.strokeRect(x, y, width, height);
        }
    }
    detectPhoneRect(canvas) {
        if (typeof cv === "undefined") return null;

        const src = cv.imread(canvas);
        const gray = new cv.Mat();
        const blurred = new cv.Mat();
        const edges = new cv.Mat();
        const contours = new cv.MatVector();
        const hierarchy = new cv.Mat();

        try {
            cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
            cv.GaussianBlur(gray, blurred, new cv.Size(5, 5), 0);
            cv.Canny(blurred, edges, 50, 150);

            const kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(3, 3));
            cv.dilate(edges, edges, kernel);
            kernel.delete();

            cv.findContours(edges, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);

            let best = null;
            const frameArea = src.cols * src.rows;

            for (let i = 0; i < contours.size(); i++) {
                const cnt = contours.get(i);
                const peri = cv.arcLength(cnt, true);
                const approx = new cv.Mat();

                cv.approxPolyDP(cnt, approx, 0.02 * peri, true);

                if (approx.rows !== 4 || !cv.isContourConvex(approx)) {
                    approx.delete();
                    cnt.delete();
                    continue;
                }

                const rect = cv.boundingRect(approx);
                const area = rect.width * rect.height;
                const ratio = rect.width / Math.max(rect.height, 1);

                const minAreaOk = area > frameArea * 0.12;
                const maxAreaOk = area < frameArea * 0.95;

                const portraitOk = ratio > 0.45 && ratio < 0.8;
                const landscapeOk = ratio > 1.25 && ratio < 2.2;

                const margin = 10;
                const insideFrame =
                    rect.x > margin &&
                    rect.y > margin &&
                    rect.x + rect.width < src.cols - margin &&
                    rect.y + rect.height < src.rows - margin;

                if (minAreaOk && maxAreaOk && insideFrame && (portraitOk || landscapeOk)) {
                    if (!best || area > best.area) {
                        best = {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height,
                            area,
                            ratio
                        };
                    }
                }

                approx.delete();
                cnt.delete();
            }

            return best;
        } finally {
            src.delete();
            gray.delete();
            blurred.delete();
            edges.delete();
            contours.delete();
            hierarchy.delete();
        }
    }
    detectTextLikeRegionsOpenCv(canvas) {
        if (typeof cv === "undefined") return [];

        const src = cv.imread(canvas);
        const gray = new cv.Mat();
        const blurred = new cv.Mat();
        const grad = new cv.Mat();
        const binary = new cv.Mat();
        const kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(9, 3));
        const contours = new cv.MatVector();
        const hierarchy = new cv.Mat();

        try {
            cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
            cv.GaussianBlur(gray, blurred, new cv.Size(3, 3), 0);

            cv.Sobel(blurred, grad, cv.CV_8U, 1, 0, 3, 1, 0, cv.BORDER_DEFAULT);
            cv.threshold(grad, binary, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU);
            cv.morphologyEx(binary, binary, cv.MORPH_CLOSE, kernel);

            cv.findContours(binary, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);

            const boxes = [];

            for (let i = 0; i < contours.size(); i++) {
                const cnt = contours.get(i);
                const rect = cv.boundingRect(cnt);

                const w = rect.width;
                const h = rect.height;
                const area = w * h;

                if (w < 30 || h < 8) {
                    cnt.delete();
                    continue;
                }

                if (area < 500 || area > 40000) {
                    cnt.delete();
                    continue;
                }

                const aspect = w / Math.max(h, 1);
                if (aspect < 2.0 || aspect > 20.0) {
                    cnt.delete();
                    continue;
                }

                const contourArea = cv.contourArea(cnt);
                const fillRatio = contourArea / area;

                if (fillRatio < 0.1 || fillRatio > 0.8) {
                    cnt.delete();
                    continue;
                }

                boxes.push({
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height
                });

                cnt.delete();
            }

            return boxes;
        } finally {
            src.delete();
            gray.delete();
            blurred.delete();
            grad.delete();
            binary.delete();
            kernel.delete();
            contours.delete();
            hierarchy.delete();
        }
    }

    async processCurrentFrame(frame) {
        if (this.isProcessing || !this.video || this.isStopped) return;

        this.isProcessing = true;

        try {
            const base64 = frame.dataUrl;
            const response = await fetch(`/inspector/report/${window.CURRENT_ORDER_ID}/ocr/${this.readEndpoint}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    img: base64
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            await this.handleServerResult(data);
        } catch (err) {
            console.error(err);
            this.updateHint("Ошибка OCR или ответа сервера");
        } finally {
            this.isProcessing = false;
        }
    }

    async handleServerResult(data) {
        if (!data || this.isStopped) return;

        const isSuccess = data.success === true || data.status === "success";

        if (isSuccess) {
            this.success[this.readEndpoint] = data;
            this.showSuccess(data);
            await this.stop();
        } else if (data.hint)
            this.updateHint(data.hint);
    }

    showSuccess(data) {
        if (this.successCard) this.successCard.classList.remove("d-none");
        if (this.statusEl) this.statusEl.classList.add("d-none");
        this.updateStatus("Успіх", "success")
        if (this.successDescription) {
            this.successDescription.textContent = data.description || "Дані успішно зчитані";
        }
        if (this.successData) {
            if (typeof data.hint === "object") {
                this.successData.innerHTML = Object.entries(data.hint)
                    .map(([k, v]) => `<div><strong>${k}:</strong> ${Array.isArray(v) ? v.join(", ") : v}</div>`)
                    .join("");
            } else {
                this.successData.textContent = data.hint || "";
            }
        }
    }

    setSteps(steps) {
        this.scannerSteps = Array.isArray(steps) ? steps : [];
    }

    setCurrentStep(index) {
        this.currentStep = index;
    }

    getCurrentScannerStep() {
        return this.scannerSteps[this.currentStep] || null;
    }
}
class ReportApp {
    constructor() {
        this.cameraManager = new CameraManager();
        this.phoneCapture = new PhoneCaptureController(this.cameraManager);
        this.ocrScanner = new OcrScannerController(this.cameraManager);

        this.currentMode = null;
        this.currentStep = 0;
        this.steps = [];
    }

    async initSteps() {
        this.steps = Array.from(document.querySelectorAll(".report-step"));
        await this.showStep(this.currentStep);
    }

    async showStep(index) {
        const scanner = document.querySelector("#universal-scanner")
        await this.phoneCapture.stop();
        await this.ocrScanner.stop();

        this.steps.forEach((step, i) => {
            const isActive = i === index;
            step.classList.toggle("d-none", !isActive);
            step.classList.toggle("active", isActive);
        });

        this.currentStep = index;

        const step = this.steps[index];
        if (!step) return;

        const scannerMount = step.querySelector(".scanner-mount");

        if (scannerMount) {
            scannerMount.appendChild(scanner);
        }

        const mode = step.dataset.scannerMode;
        if (!mode) throw Error(`Scanner mode is ${mode}`);
        if (mode === 'photo') {
            await this.phoneCapture.start(scanner);
        } else {
            await this.ocrScanner.start(scanner, step.dataset.scanner);
        }

    }

    async nextStep() {
        if (this.currentStep < this.steps.length - 1) {
            await this.showStep(this.currentStep + 1);
        }
    }

    async prevStep() {
        if (this.currentStep > 0) {
            await this.showStep(this.currentStep - 1);
        }
    }

    async init() {
        await this.initSteps();

        document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tabBtn => {
            tabBtn.addEventListener("shown.bs.tab", async event => {
                const activeStep = this.steps[this.currentStep];
                if (!activeStep) return;

                // если на шаге есть OCR-блок — это не photo-step
                if (activeStep.querySelector('[data-scanner="ocr"]')) return;

                const targetSelector = event.target.getAttribute("data-bs-target");
                const targetPane = document.querySelector(targetSelector);
                if (!targetPane) return;

                const phoneBlock = targetPane.querySelector(".phone-capture-block");
                if (!phoneBlock) return;

                await this.phoneCapture.stop();
                await this.cameraManager.stop();

                this.currentMode = "photo";
                await this.phoneCapture.start(phoneBlock);
            });
        });

        const form = document.querySelector("form");
        if (form) {
            form.addEventListener("submit", async () => {
                await this.cameraManager.stop();
            });
        }

    }
}

const reportApp = new ReportApp();

window.capturePhonePhoto = function(btn) {
    const step = btn.closest(".phone-capture-step");
    if (!step) return;

    reportApp.phoneCapture.capture(step);
};

window.loadPhonePhoto = function(input) {
    const step = input.closest(".phone-capture-step");
    if (!step) return;

    reportApp.phoneCapture.loadFile(input, step);
};

window.resetPhonePhoto = function(btn) {
    const step = btn.closest(".phone-capture-step");
    if (!step) return;

    reportApp.phoneCapture.reset(step);
};

window.nextStep = async function() {
    await reportApp.nextStep();
};

window.prevStep = async function() {
    await reportApp.prevStep();
};

document.addEventListener("DOMContentLoaded", async () => {
    await reportApp.init();
});