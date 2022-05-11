const item = document.getElementById("item");

function updateNames(templateData) {

    const templates = JSON.parse(templateData);

    const itemSelection = document.getElementById("item");
    const colorA = document.getElementById("colorA");
    const colorB = document.getElementById("colorB");
    const colorC = document.getElementById("colorC");

    for (let i in templates.loterias) {
        if (itemSelection.value == templates.loterias[i].nombre) {
            colorA.innerHTML = templates.loterias[i].a
            colorB.innerHTML = templates.loterias[i].b

            // Change the ColorC heading to "-"
            if (templates.loterias[i].c == '') {
                colorC.innerHTML = '-';

                // Unselect all ColorC radios
                for (let i in templates.colors) {
                    if (templates.colors[i].sku <= 7) { // don't include extended colors
                        let selection = document.getElementById(`${templates.colors[i].name}c`);
                        selection.checked = false;
                    }
                }
            } else {
                colorC.innerHTML = templates.loterias[i].c
            }
        }
    }
}

updateNames(templateData);

item.addEventListener('change', () => { updateNames(templateData)}, false);