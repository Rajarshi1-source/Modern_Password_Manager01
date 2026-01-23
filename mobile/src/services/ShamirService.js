/**
 * Shamir Service - Mobile
 * ========================
 * 
 * Client-side Shamir's Secret Sharing implementation for React Native.
 * Used for splitting and reconstructing secrets locally before server sync.
 */

// BigInt polyfill may be needed for older React Native versions

class ShamirService {
    constructor() {
        // Use a large prime for finite field arithmetic
        // This is a 256-bit prime
        this.prime = BigInt('0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141');
    }

    /**
     * Split a secret into n shares where k are required to reconstruct
     * @param {string} secret - The secret to split
     * @param {number} k - Threshold (minimum shares needed)
     * @param {number} n - Total number of shares
     * @returns {Array<{index: number, value: string}>} - Array of shares
     */
    splitSecret(secret, k, n) {
        if (k > n) {
            throw new Error('Threshold k cannot exceed total shares n');
        }
        if (k < 2) {
            throw new Error('Threshold must be at least 2');
        }

        // Convert secret to BigInt
        const secretBytes = this.stringToBytes(secret);
        const secretInt = this.bytesToBigInt(secretBytes);

        // Generate random polynomial coefficients
        // a_0 = secret, a_1...a_{k-1} are random
        const coefficients = [secretInt];
        for (let i = 1; i < k; i++) {
            coefficients.push(this.randomBigInt());
        }

        // Evaluate polynomial at n points (1 to n)
        const shares = [];
        for (let x = 1; x <= n; x++) {
            const y = this.evaluatePolynomial(coefficients, BigInt(x));
            shares.push({
                index: x,
                value: this.bigIntToHex(y)
            });
        }

        return shares;
    }

    /**
     * Reconstruct secret from k or more shares using Lagrange interpolation
     * @param {Array<{index: number, value: string}>} shares - Shares to use
     * @returns {string} - Reconstructed secret
     */
    reconstructSecret(shares) {
        if (shares.length < 2) {
            throw new Error('Need at least 2 shares to reconstruct');
        }

        // Convert shares to BigInt points
        const points = shares.map(s => ({
            x: BigInt(s.index),
            y: this.hexToBigInt(s.value)
        }));

        // Lagrange interpolation at x = 0
        let secret = BigInt(0);

        for (let i = 0; i < points.length; i++) {
            let numerator = BigInt(1);
            let denominator = BigInt(1);

            for (let j = 0; j < points.length; j++) {
                if (i !== j) {
                    numerator = this.mod(numerator * (BigInt(0) - points[j].x), this.prime);
                    denominator = this.mod(denominator * (points[i].x - points[j].x), this.prime);
                }
            }

            // Compute Lagrange basis polynomial
            const lagrange = this.mod(
                points[i].y * numerator * this.modInverse(denominator, this.prime),
                this.prime
            );
            secret = this.mod(secret + lagrange, this.prime);
        }

        // Convert back to string
        const secretBytes = this.bigIntToBytes(secret);
        return this.bytesToString(secretBytes);
    }

    /**
     * Verify a share is valid (basic check)
     * @param {Object} share - Share to verify
     * @param {string} expectedHash - Expected hash of reconstructed secret
     * @returns {boolean}
     */
    verifyShare(share, expectedHash) {
        try {
            // Basic format check
            if (!share.index || !share.value) return false;
            if (share.index < 1) return false;
            if (!/^[0-9a-fA-F]+$/.test(share.value)) return false;
            return true;
        } catch (e) {
            return false;
        }
    }

    // =========================================================================
    // Mathematical Operations
    // =========================================================================

    /**
     * Evaluate polynomial at point x
     */
    evaluatePolynomial(coefficients, x) {
        let result = BigInt(0);
        let power = BigInt(1);

        for (const coef of coefficients) {
            result = this.mod(result + coef * power, this.prime);
            power = this.mod(power * x, this.prime);
        }

        return result;
    }

    /**
     * Modular arithmetic
     */
    mod(a, m) {
        return ((a % m) + m) % m;
    }

    /**
     * Modular inverse using extended Euclidean algorithm
     */
    modInverse(a, m) {
        a = this.mod(a, m);
        
        let [old_r, r] = [a, m];
        let [old_s, s] = [BigInt(1), BigInt(0)];

        while (r !== BigInt(0)) {
            const quotient = old_r / r;
            [old_r, r] = [r, old_r - quotient * r];
            [old_s, s] = [s, old_s - quotient * s];
        }

        return this.mod(old_s, m);
    }

    /**
     * Generate random BigInt
     */
    randomBigInt() {
        const bytes = new Uint8Array(32);
        for (let i = 0; i < bytes.length; i++) {
            bytes[i] = Math.floor(Math.random() * 256);
        }
        return this.mod(this.bytesToBigInt(bytes), this.prime);
    }

    // =========================================================================
    // Conversion Utilities
    // =========================================================================

    stringToBytes(str) {
        const encoder = new TextEncoder();
        return encoder.encode(str);
    }

    bytesToString(bytes) {
        const decoder = new TextDecoder();
        return decoder.decode(bytes);
    }

    bytesToBigInt(bytes) {
        let result = BigInt(0);
        for (let i = 0; i < bytes.length; i++) {
            result = (result << BigInt(8)) | BigInt(bytes[i]);
        }
        return result;
    }

    bigIntToBytes(bigint) {
        const hex = bigint.toString(16).padStart(2, '0');
        const paddedHex = hex.length % 2 ? '0' + hex : hex;
        const bytes = new Uint8Array(paddedHex.length / 2);
        for (let i = 0; i < bytes.length; i++) {
            bytes[i] = parseInt(paddedHex.substr(i * 2, 2), 16);
        }
        return bytes;
    }

    bigIntToHex(bigint) {
        return bigint.toString(16).padStart(64, '0');
    }

    hexToBigInt(hex) {
        return BigInt('0x' + hex);
    }

    /**
     * Hash a secret for verification
     */
    async hashSecret(secret) {
        const encoder = new TextEncoder();
        const data = encoder.encode(secret);
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }
}

// Export singleton instance
const shamirService = new ShamirService();
export default shamirService;
