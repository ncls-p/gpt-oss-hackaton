document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("btn‑changer");
    const texte = document.getElementById("texte");

    btn.addEventListener("click", function () {
        const colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f1c40f"];
        const randomColor = colors[Math.floor(Math.random() * colors.length)];
        texte.style.color = randomColor;
    });
});