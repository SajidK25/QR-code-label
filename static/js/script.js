document.addEventListener('DOMContentLoaded', () => {
    const manufacturerSelect = document.getElementById('manufacturer');
    const brandInput = document.getElementById('brand');
    const itemNoInput = document.getElementById('item-no');
    const skuInput = document.getElementById('sku');
    const udiInput = document.getElementById('udi');
    const descriptionInput = document.getElementById('description');
    const serialInput = document.getElementById('serial');
    const quantityInput = document.getElementById('quantity');

    // Auto-populate fields when UDI is scanned
    udiInput.addEventListener('input', () => {
        const barcode = udiInput.value.trim();
        if (barcode.length > 10) {
            fetch("/product-info/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ barcode: barcode })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error(data.error);
                    alert("Error: " + data.error);
                } else {
                    brandInput.value = data.product_name;
                    skuInput.value = data.product_sku;
                    itemNoInput.value = data.product_sku.slice(-5);
                    descriptionInput.value = data.product_name;
                    serialInput.value = barcode.slice(-7);
                    quantityInput.value = 1;
                }
            })
            .catch(error => console.error("Fetch error:", error));
        }
    });
});

