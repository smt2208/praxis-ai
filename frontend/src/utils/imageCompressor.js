/**
 * frontend/src/utils/imageCompressor.js
 *
 * Utility to compress image files before sending them to the backend.
 *
 * Strategy:
 *  - Images ≤ SIZE_THRESHOLD_MB are passed through untouched (fast path).
 *  - Larger images are drawn onto a Canvas capped at MAX_DIMENSION px on the
 *    longest side, then re-encoded as JPEG at JPEG_QUALITY.
 *  - Always returns a base64 data-URI string (same shape as FileReader output).
 *
 * Usage:
 *   import { compressImage } from '../utils/imageCompressor';
 *   const b64 = await compressImage(file);
 */

const SIZE_THRESHOLD_BYTES = 1 * 1024 * 1024; // 1 MB — compress anything above this
const MAX_DIMENSION = 1280;                     // px — longest side cap after compression
const JPEG_QUALITY = 0.82;                      // 0–1 JPEG quality (82% is visually lossless)
const OUTPUT_MIME = 'image/jpeg';

/**
 * Compress an image File if it exceeds the size threshold.
 *
 * @param {File} file - The image file selected by the user.
 * @returns {Promise<string>} - Base64 data-URI of the (possibly compressed) image.
 */
export async function compressImage(file) {
  if (!file || !file.type.startsWith('image/')) {
    throw new Error('Not a valid image file.');
  }

  // Fast path — small image, return as-is
  if (file.size <= SIZE_THRESHOLD_BYTES) {
    return _readAsDataURL(file);
  }

  return new Promise((resolve, reject) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      try {
        const { width, height } = _scaledDimensions(img.naturalWidth, img.naturalHeight);

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        const compressed = canvas.toDataURL(OUTPUT_MIME, JPEG_QUALITY);

        // Safety: if Canvas somehow produced a larger output, return original
        const compressedBytes = _dataURIBytes(compressed);
        if (compressedBytes >= file.size) {
          _readAsDataURL(file).then(resolve).catch(reject);
        } else {
          const ratio = ((1 - compressedBytes / file.size) * 100).toFixed(1);
          console.debug(
            `[imageCompressor] ${file.name}: ${_kb(file.size)} KB → ${_kb(compressedBytes)} KB (−${ratio}%)`
          );
          resolve(compressed);
        }
      } catch (err) {
        reject(err);
      }
    };

    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      // Fallback: return uncompressed
      _readAsDataURL(file).then(resolve).catch(reject);
    };

    img.src = objectUrl;
  });
}

/**
 * Compress multiple images in parallel.
 *
 * @param {File[]} files
 * @returns {Promise<string[]>} - Array of base64 data-URIs.
 */
export async function compressImages(files) {
  return Promise.all(files.map((f) => compressImage(f)));
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function _scaledDimensions(w, h) {
  if (w <= MAX_DIMENSION && h <= MAX_DIMENSION) return { width: w, height: h };
  const scale = MAX_DIMENSION / Math.max(w, h);
  return { width: Math.round(w * scale), height: Math.round(h * scale) };
}

function _readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/** Estimate byte size of a base64 data-URI string (approximate). */
function _dataURIBytes(dataURI) {
  const base64 = dataURI.split(',')[1] || '';
  return Math.ceil((base64.length * 3) / 4);
}

function _kb(bytes) {
  return (bytes / 1024).toFixed(1);
}
