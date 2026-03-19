document.addEventListener("DOMContentLoaded", function() {
    const loginBtn = document.querySelector(".login-btn");
    const registerBtn = document.querySelector(".register-btn");
    if (loginBtn) {
        loginBtn.addEventListener("click", () => {

        });
    }
});
document.addEventListener("DOMContentLoaded", function() {

    const mapContainer = document.getElementById('map');

    if (mapContainer) {
        const poltavaCenter = [49.5895, 34.5513];
        const map = L.map('map').setView(poltavaCenter, 13);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);

        const marker = L.marker(poltavaCenter, { draggable: true }).addTo(map);

        function updateCoordinates(lat, lng) {
            document.getElementById('lat').value = lat;
            document.getElementById('lng').value = lng;
        }

        // Обновляем координаты, если маркер перетащили руками
        marker.on('dragend', function(e) {
            const position = marker.getLatLng();
            updateCoordinates(position.lat, position.lng);
        });

        // Обновляем координаты и переносим маркер, если просто кликнули по карте
        map.on('click', function(e) {
            marker.setLatLng(e.latlng);
            updateCoordinates(e.latlng.lat, e.latlng.lng);
        });

    // === НОВЫЙ КОД: ПОИСК ПО АДРЕСУ (С АВТОДОПОЛНЕНИЕМ И ФИЛЬТРОМ) ===
        // Проверяем, загрузился ли плагин поиска
        if (L.Control.Geocoder) {

            // Настраиваем провайдера (базу данных) для поиска
            const geocoderProvider = L.Control.Geocoder.nominatim({
                geocodingQueryParams: {
                    countrycodes: 'ua', // Жестко ограничиваем поиск только Украиной
                    "accept-language": "ru,uk" // Просим отдавать названия на русском/украинском
                }
            });

            L.Control.geocoder({
                geocoder: geocoderProvider, // Подключаем наши настройки (Украина)
                defaultMarkGeocode: false,
                placeholder: "Cоборності 50",
                suggestMinLength: 3, // Начинать автопоиск после ввода 3-х символов
                suggestTimeout: 500  // Ждать 500 мс после последнего нажатия клавиши (защита от бана OSM)
            })
            .on('markgeocode', function(e) {
                const center = e.geocode.center;
                const bbox = e.geocode.bbox;

                // 1. Приближаем карту к найденному адресу
                map.fitBounds(bbox);

                // 2. Переносим наш синий маркер на этот адрес
                marker.setLatLng(center);

                // 3. Записываем новые координаты в скрытые input'ы формы
                updateCoordinates(center.lat, center.lng);
            })
            .addTo(map);
        }
    }
});