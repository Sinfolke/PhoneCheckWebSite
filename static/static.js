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

        // === НОВЫЙ КОД: ПОИСК ПО АДРЕСУ ===
        // Проверяем, загрузился ли плагин поиска
        if (L.Control.Geocoder) {
            L.Control.geocoder({
                defaultMarkGeocode: false, // Отключаем стандартный маркер плагина
                placeholder: "Поиск адреса (например: Полтава, Центр)..." // Текст в строке поиска
            })
            .on('markgeocode', function(e) {
                const center = e.geocode.center; // Получаем координаты найденного места
                const bbox = e.geocode.bbox;     // Получаем границы места для масштабирования

                // 1. Приближаем карту к найденному адресу
                map.fitBounds(bbox);

                // 2. Переносим наш синий маркер на этот адрес
                marker.setLatLng(center);

                // 3. Записываем новые координаты в скрытые input'ы формы
                updateCoordinates(center.lat, center.lng);
            })
            .addTo(map); // Добавляем кнопку поиска на карту
        }
    }
});