// ═══════════════════════════════════════════════════
// VYNE × RENTCOVER (XCover API) — Integration Service
// ═══════════════════════════════════════════════════
// 1. Sign up at covergenius.com/rentalcover
// 2. Get your credentials from your Cover Genius integration manager
// 3. Replace the three values below — everything else is wired up

const RENTCOVER_CONFIG = {
  PARTNER_ID:  'YOUR_PARTNER_ID',       // e.g. 'VYNE_NASHVILLE'
  API_KEY:     'YOUR_API_KEY',          // from Cover Genius
  API_SECRET:  'YOUR_API_SECRET',       // from Cover Genius
  SANDBOX:     true,                    // ← flip to false when you go live
};

// ── API base URLs ──
const BASE_URL = RENTCOVER_CONFIG.SANDBOX
  ? 'https://api.sandbox.covergenius.com/api/v2'
  : 'https://api.covergenius.com/api/v2';

// ── Insurance tiers displayed to customer ──
// These map to XCover product codes — update slugs once Cover Genius gives you yours
const INSURANCE_TIERS = [
  {
    id:       'basic',
    name:     'Basic Protection',
    slug:     'RENTAL_BASIC',           // ← replace with real XCover product slug
    price:    14,                       // per day — update from your Cover Genius quote
    coverage: '$1,000',
    features: ['Collision damage', 'Theft protection', '$1,000 excess covered'],
    badge:    null,
  },
  {
    id:       'standard',
    name:     'Standard Protection',
    slug:     'RENTAL_STANDARD',        // ← replace
    price:    24,
    coverage: '$3,000',
    features: ['Collision & theft', '$3,000 excess covered', 'Towing included', '24/7 claims support'],
    badge:    'Most Popular',
  },
  {
    id:       'premium',
    name:     'Full Coverage',
    slug:     'RENTAL_PREMIUM',         // ← replace
    price:    39,
    coverage: 'Unlimited',
    features: ['Zero excess', 'Unlimited coverage', 'Personal belongings', 'Emergency travel', 'Roadside assistance'],
    badge:    'Best Value',
  },
];

// ═══════════════════════════════════════
// STEP 1 — Get a quote from XCover
// Called when customer reaches insurance step
// ═══════════════════════════════════════
async function rentcover_getQuote({ vehicleValue, pickupDate, returnDate, driverAge, currency = 'USD' }) {
  // If no credentials yet — return mock data so UI still works
  if (RENTCOVER_CONFIG.API_KEY === 'YOUR_API_KEY') {
    console.warn('[RentCover] Using mock data — add real credentials to go live');
    return { success: true, mock: true, tiers: INSURANCE_TIERS };
  }

  try {
    const response = await fetch(`${BASE_URL}/quotes/`, {
      method: 'POST',
      headers: {
        'Content-Type':  'application/json',
        'X-Api-Key':     RENTCOVER_CONFIG.API_KEY,
        'X-Partner-Id':  RENTCOVER_CONFIG.PARTNER_ID,
        'X-Signature':   await rentcover_sign({ vehicleValue, pickupDate, returnDate }),
      },
      body: JSON.stringify({
        partner_id:     RENTCOVER_CONFIG.PARTNER_ID,
        currency:       currency,
        pickup_date:    pickupDate,    // 'YYYY-MM-DD'
        return_date:    returnDate,    // 'YYYY-MM-DD'
        vehicle_value:  vehicleValue,
        driver_age:     driverAge,
        location:       'US-TN',
        products: INSURANCE_TIERS.map(t => t.slug),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || 'Quote failed');
    return { success: true, mock: false, data };
  } catch (err) {
    console.error('[RentCover] Quote error:', err);
    return { success: false, error: err.message };
  }
}

// ═══════════════════════════════════════
// STEP 2 — Issue a policy after payment
// Called after Stripe deposit succeeds
// ═══════════════════════════════════════
async function rentcover_issuePolicy({
  quoteId, productSlug,
  customerName, customerEmail, customerPhone,
  pickupDate, returnDate,
  vehicleMake, vehicleModel, vehicleYear,
  bookingRef,
}) {
  // Mock mode — no credentials yet
  if (RENTCOVER_CONFIG.API_KEY === 'YOUR_API_KEY') {
    console.warn('[RentCover] Mock policy issued — add credentials to go live');
    return {
      success:    true,
      mock:       true,
      policyId:   'MOCK-' + Math.random().toString(36).substring(2, 10).toUpperCase(),
      policyUrl:  '#',
    };
  }

  try {
    const response = await fetch(`${BASE_URL}/policies/`, {
      method: 'POST',
      headers: {
        'Content-Type':  'application/json',
        'X-Api-Key':     RENTCOVER_CONFIG.API_KEY,
        'X-Partner-Id':  RENTCOVER_CONFIG.PARTNER_ID,
        'X-Signature':   await rentcover_sign({ bookingRef, productSlug }),
      },
      body: JSON.stringify({
        partner_id:       RENTCOVER_CONFIG.PARTNER_ID,
        quote_id:         quoteId,
        product_slug:     productSlug,
        booking_ref:      bookingRef,
        pickup_date:      pickupDate,
        return_date:      returnDate,
        vehicle: {
          make:  vehicleMake,
          model: vehicleModel,
          year:  vehicleYear,
        },
        customer: {
          name:  customerName,
          email: customerEmail,
          phone: customerPhone,
        },
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || 'Policy issue failed');
    return {
      success:   true,
      mock:      false,
      policyId:  data.policy_id,
      policyUrl: data.policy_document_url,
    };
  } catch (err) {
    console.error('[RentCover] Policy error:', err);
    return { success: false, error: err.message };
  }
}

// ═══════════════════════════════════════
// STEP 3 — Cancel a policy
// Called if booking is cancelled
// ═══════════════════════════════════════
async function rentcover_cancelPolicy(policyId) {
  if (RENTCOVER_CONFIG.API_KEY === 'YOUR_API_KEY') {
    return { success: true, mock: true };
  }
  try {
    const response = await fetch(`${BASE_URL}/policies/${policyId}/cancel/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Api-Key':    RENTCOVER_CONFIG.API_KEY,
        'X-Partner-Id': RENTCOVER_CONFIG.PARTNER_ID,
      },
    });
    return { success: response.ok };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

// ── HMAC signature helper (XCover requires signed requests) ──
async function rentcover_sign(payload) {
  const msg = JSON.stringify(payload) + RENTCOVER_CONFIG.API_SECRET;
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey('raw', enc.encode(RENTCOVER_CONFIG.API_SECRET), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(JSON.stringify(payload)));
  return Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2,'0')).join('');
}

// Export for use in booking flow
if (typeof module !== 'undefined') {
  module.exports = { rentcover_getQuote, rentcover_issuePolicy, rentcover_cancelPolicy, INSURANCE_TIERS, RENTCOVER_CONFIG };
}
