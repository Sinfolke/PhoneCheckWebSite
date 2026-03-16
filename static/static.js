document.addEventListener("DOMContentLoaded", function() {
    const buyBtn = document.querySelector(".buy-btn");
    if (buyBtn) {
        buyBtn.addEventListener("click", () => {
            alert("Здесь можно вызвать API для покупки или перейти к оплате!");
            // fetch("/buy", { method: "POST", body: JSON.stringify({item: 'phonecheck'}) })
        });
    }
});