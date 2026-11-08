// Non-blocking browser geolocation & live temperature fetch
// Gracefully enhances the scan metadata if available; otherwise silent fallback.
(function() {
    const locInput = document.getElementById('scan-location-name');
    const tempInput = document.getElementById('scan-ambient-temp');
    if (!locInput || !tempInput) return;

    if (!('geolocation' in navigator)) return;

    navigator.geolocation.getCurrentPosition(
        async function(pos) {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            try {
                // Fetch live temperature from Open-Meteo (public, no key required)
                const weatherPromise = fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m`)
                    .then(r => r.ok ? r.json() : null)
                    .catch(() => null);

                // Reverse geocode location name via OpenStreetMap Nominatim
                const geoPromise = fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`)
                    .then(r => r.ok ? r.json() : null)
                    .catch(() => null);

                const [weatherData, geoData] = await Promise.all([weatherPromise, geoPromise]);

                if (weatherData && weatherData.current && typeof weatherData.current.temperature_2m === 'number') {
                    tempInput.value = weatherData.current.temperature_2m.toFixed(1);
                }

                if (geoData && geoData.address) {
                    const addr = geoData.address;
                    const name = addr.city || addr.town || addr.municipality || addr.county || addr.state || 'Local Market';
                    locInput.value = name;
                }
            } catch (err) {
                // Silently fall back to standard seasonal baseline
            }
        },
        function(err) {
            // Permission denied or unavailable - silently fall back to seasonal month
        },
        { timeout: 6000, maximumAge: 300000 }
    );
})();

