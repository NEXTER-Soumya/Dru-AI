const BREED_MODEL_URL = '/static/models/cattle_breed_model.onnx';
const BREED_CLASSES_URL = '/static/models/cattle_breed_classes.json';
const MAX_BREED_IMAGE_PIXELS = 20_000_000;
let breedInferenceResources;

function createResizeWeights(sourceLength, destinationLength) {
    const scale = sourceLength / destinationLength;
    const filterScale = Math.max(scale, 1);

    return Array.from({ length: destinationLength }, (_, outputIndex) => {
        const center = (outputIndex + 0.5) * scale;
        const first = Math.max(0, Math.floor(center - filterScale));
        const last = Math.min(sourceLength, Math.ceil(center + filterScale));
        const weights = [];
        let total = 0;

        for (let sourceIndex = first; sourceIndex < last; sourceIndex += 1) {
            const distance = Math.abs((sourceIndex + 0.5 - center) / filterScale);
            const weight = Math.max(0, 1 - distance);
            if (weight > 0) {
                weights.push([sourceIndex, weight]);
                total += weight;
            }
        }
        return weights.map(([index, weight]) => [index, weight / total]);
    });
}

function resizeImageLikePillow(sourcePixels, sourceWidth, sourceHeight) {
    // Match torchvision's antialiased bilinear resize with separable filtering.
    const size = 224;
    const horizontalWeights = createResizeWeights(sourceWidth, size);
    const horizontalPixels = new Uint8Array(size * sourceHeight * 3);

    for (let y = 0; y < sourceHeight; y += 1) {
        for (let x = 0; x < size; x += 1) {
            for (let channel = 0; channel < 3; channel += 1) {
                let value = 0;
                for (const [sourceX, weight] of horizontalWeights[x]) {
                    value += sourcePixels[(y * sourceWidth + sourceX) * 4 + channel] * weight;
                }
                horizontalPixels[(y * size + x) * 3 + channel] =
                    Math.min(255, Math.max(0, Math.round(value)));
            }
        }
    }

    const verticalWeights = createResizeWeights(sourceHeight, size);
    const resizedPixels = new Uint8Array(size * size * 3);
    for (let y = 0; y < size; y += 1) {
        for (let x = 0; x < size; x += 1) {
            for (let channel = 0; channel < 3; channel += 1) {
                let value = 0;
                for (const [sourceY, weight] of verticalWeights[y]) {
                    value += horizontalPixels[(sourceY * size + x) * 3 + channel] * weight;
                }
                resizedPixels[(y * size + x) * 3 + channel] =
                    Math.min(255, Math.max(0, Math.round(value)));
            }
        }
    }
    return resizedPixels;
}

function loadBreedInferenceResources() {
    if (!breedInferenceResources) {
        breedInferenceResources = Promise.all([
            window.ort.InferenceSession.create(BREED_MODEL_URL, {
                executionProviders: ['wasm'],
                graphOptimizationLevel: 'all',
            }),
            fetch(BREED_CLASSES_URL).then(response => {
                if (!response.ok) {
                    throw new Error('Could not load the breed labels.');
                }
                return response.json();
            }),
        ]).catch(error => {
            breedInferenceResources = null;
            throw error;
        });
    }
    return breedInferenceResources;
}

async function predictBreedInBrowser(file) {
    if (!window.ort) {
        throw new Error('The browser inference runtime could not be loaded.');
    }

    let bitmap;
    try {
        bitmap = await createImageBitmap(file);
        if (bitmap.width * bitmap.height > MAX_BREED_IMAGE_PIXELS) {
            throw new Error('Image resolution must be 20 megapixels or less.');
        }

        const sourceCanvas = document.createElement('canvas');
        sourceCanvas.width = bitmap.width;
        sourceCanvas.height = bitmap.height;
        const sourceContext = sourceCanvas.getContext('2d', { willReadFrequently: true });
        if (!sourceContext) {
            throw new Error('Your browser could not read this image for analysis.');
        }
        sourceContext.drawImage(bitmap, 0, 0);
        const sourcePixels = sourceContext.getImageData(
            0,
            0,
            bitmap.width,
            bitmap.height,
        ).data;
        const pixels = resizeImageLikePillow(sourcePixels, bitmap.width, bitmap.height);
        sourceCanvas.width = 0;
        sourceCanvas.height = 0;
        const input = new Float32Array(3 * 224 * 224);
        const means = [0.485, 0.456, 0.406];
        const standardDeviations = [0.229, 0.224, 0.225];

        for (let pixel = 0; pixel < 224 * 224; pixel += 1) {
            for (let channel = 0; channel < 3; channel += 1) {
                input[channel * 224 * 224 + pixel] =
                    (pixels[pixel * 3 + channel] / 255 - means[channel]) /
                    standardDeviations[channel];
            }
        }

        const [session, classes] = await loadBreedInferenceResources();
        if (!Array.isArray(classes) || classes.length !== 50) {
            throw new Error('The breed model labels are invalid.');
        }
        const inputName = session.inputNames[0];
        const outputName = session.outputNames[0];
        const inputTensor = new window.ort.Tensor('float32', input, [1, 3, 224, 224]);
        const outputs = await session.run({ [inputName]: inputTensor });
        const logits = outputs[outputName]?.data;
        if (!logits || logits.length !== classes.length) {
            throw new Error('The breed model returned an invalid result.');
        }

        let maxIndex = 0;
        for (let index = 1; index < logits.length; index += 1) {
            if (logits[index] > logits[maxIndex]) maxIndex = index;
        }
        const maximum = logits[maxIndex];
        let total = 0;
        for (const logit of logits) total += Math.exp(logit - maximum);

        return {
            breed: classes[maxIndex],
            confidence: Math.exp(logits[maxIndex] - maximum) / total * 100,
        };
    } catch (error) {
        if (error instanceof Error) throw error;
        throw new Error('The image could not be analyzed in this browser.');
    } finally {
        if (bitmap) bitmap.close();
    }
}
