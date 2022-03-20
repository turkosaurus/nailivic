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
            if (templates.loterias[i].c == '') {
                colorC.innerHTML = '-'

            } else {
                colorC.innerHTML = templates.loterias[i].c
            }
        }
        console.log(templates.loterias[i]);
    }
}

updateNames(templateData);

item.addEventListener('change', () => { updateNames(templateData)}, false);